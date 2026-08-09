import json
import re
from typing import Any


def _extract_json_object(text: str) -> Any:
    """
    Extract a JSON object from the LLM response.

    Handles:
    1. Pure JSON
    2. ```json ... ``` blocks
    3. JSON surrounded by extra text
    """

    if not text:
        return None

    cleaned = text.strip()

    # Remove markdown code fences
    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned
    )

    cleaned = cleaned.strip()

    # Try parsing the complete response
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON object from surrounding text
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start:end + 1]

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    return None


def build_reply_payload(
    user_prompt: str,
    model_reply: str,
    log_url: str
) -> dict:
    """
    Build the final response required by the TDS grader.

    The LLM is responsible for solving the question and
    determining the requested answer structure.

    The application is responsible for supplying the
    real public log URL.
    """

    parsed = _extract_json_object(model_reply)

    # If the model failed to return valid JSON
    if not isinstance(parsed, dict):
        return {
            "answer": model_reply.strip() if model_reply else "",
            "log_url": log_url
        }

    # ---------------------------------------------------------
    # Case 1:
    # Model already returned:
    #
    # {"answer": {...}, "log_url": "..."}
    #
    # Keep the answer but ALWAYS replace log_url.
    # ---------------------------------------------------------
    if "answer" in parsed:

        answer = parsed["answer"]

        return {
            "answer": answer,
            "log_url": log_url
        }

    # ---------------------------------------------------------
    # Case 2:
    # Model returned the requested object directly.
    #
    # Example:
    # {"value": 391}
    #
    # Convert it to the required grader format:
    #
    # {"answer": {"value": 391}, "log_url": "..."}
    # ---------------------------------------------------------

    return {
        "answer": parsed,
        "log_url": log_url
    }


def json_response(payload: dict) -> str:
    """
    Convert payload to compact JSON.
    """

    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":")
    )