import json
import re
from typing import Any


def _extract_json_object(text: str) -> Any:
    """
    Extract the first valid JSON object from the model response.
    """

    if not text:
        return None

    cleaned = text.strip()

    # Remove Markdown fences if the model accidentally adds them.
    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    )

    cleaned = cleaned.strip()

    # First try the complete response.
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Then try extracting the JSON object.
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start:end + 1]

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    return None


def _question_requires_log_url(user_prompt: str) -> bool:
    """
    Determine whether the user's requested JSON shape explicitly contains
    a log_url field.

    Example:

    {"value": <number>}
        -> False

    {"answer": {"sd": <number>}, "log_url": "..."}
        -> True
    """

    return "log_url" in user_prompt


def build_reply_payload(
    user_prompt: str,
    model_reply: str,
    log_url: str,
) -> dict:
    """
    Build the exact JSON object expected by the question.

    IMPORTANT:
    We do NOT automatically wrap bare JSON objects.

    If the user asks for:
        {"value": 391}

    return:
        {"value": 391}

    If the user asks for:
        {"answer": {"sd": 2.0}, "log_url": "..."}

    return:
        {"answer": {"sd": 2.0}, "log_url": "..."}
    """

    parsed = _extract_json_object(model_reply)

    # If model failed to produce JSON, provide a valid JSON fallback.
    if not isinstance(parsed, dict):
        if _question_requires_log_url(user_prompt):
            return {
                "answer": model_reply.strip() if model_reply else "",
                "log_url": log_url,
            }

        return {
            "error": model_reply.strip() if model_reply else ""
        }

    needs_log_url = _question_requires_log_url(user_prompt)

    # ---------------------------------------------------------
    # CASE 1:
    # User explicitly requested log_url.
    # ---------------------------------------------------------
    if needs_log_url:

        # If model returned:
        #
        # {"answer": {...}, "log_url": "..."}
        #
        # preserve the answer and replace log_url with our real URL.
        if "answer" in parsed:
            return {
                "answer": parsed["answer"],
                "log_url": log_url,
            }

        # If model returned the inner object directly:
        #
        # {"sd": 2.0}
        #
        # wrap it because the user's requested schema contains
        # "answer" and "log_url".
        return {
            "answer": parsed,
            "log_url": log_url,
        }

    # ---------------------------------------------------------
    # CASE 2:
    # User did NOT request log_url.
    #
    # Return the model's object EXACTLY as requested.
    # ---------------------------------------------------------

    # If the model incorrectly added the wrapper even though the
    # user did not request it, unwrap it.
    if set(parsed.keys()) == {"answer", "log_url"}:
        return parsed["answer"]

    return parsed


def json_response(payload: dict) -> str:
    """
    Convert payload to compact JSON.
    """

    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )