import json
import re
from typing import Any


def _extract_json_object(text: str) -> Any:
    """
    Extract a JSON object from an LLM response.
    """

    if not text:
        return None

    cleaned = text.strip()

    # Remove markdown code fences.
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

    # Try the complete response.
    try:

        return json.loads(cleaned)

    except json.JSONDecodeError:
        pass

    # Try extracting {...}.
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if (
        start != -1
        and end != -1
        and end > start
    ):

        candidate = cleaned[
            start:end + 1
        ]

        try:

            return json.loads(candidate)

        except json.JSONDecodeError:

            return None

    return None


def _requested_log_url(user_prompt: str) -> bool:
    """
    Determine whether the incoming question explicitly requests
    a log_url field.
    """

    return bool(
        re.search(
            r'["\']log_url["\']',
            user_prompt,
            flags=re.IGNORECASE,
        )
    )


def build_reply_payload(
    user_prompt: str,
    model_reply: str,
    log_url: str,
) -> dict:

    parsed = _extract_json_object(
        model_reply
    )

    # --------------------------------------------------------
    # Invalid model response.
    # --------------------------------------------------------

    if not isinstance(parsed, dict):

        if _requested_log_url(
            user_prompt
        ):

            return {
                "answer": (
                    model_reply.strip()
                    if model_reply
                    else ""
                ),
                "log_url": log_url,
            }

        return {
            "error": (
                model_reply.strip()
                if model_reply
                else ""
            )
        }

    # --------------------------------------------------------
    # User explicitly requested log_url.
    # --------------------------------------------------------

    if _requested_log_url(
        user_prompt
    ):

        # Model already produced wrapper.
        if (
            "answer" in parsed
            and "log_url" in parsed
        ):

            return {
                "answer": parsed["answer"],
                "log_url": log_url,
            }

        # Model produced:
        #
        # {"sd": 2.0}
        #
        # but user requested:
        #
        # {"answer":{"sd":...},"log_url":"..."}
        #

        if "answer" in parsed:

            return {
                "answer": parsed["answer"],
                "log_url": log_url,
            }

        return {
            "answer": parsed,
            "log_url": log_url,
        }

    # --------------------------------------------------------
    # User did NOT request log_url.
    #
    # Return exact requested object.
    # --------------------------------------------------------

    # If LLM accidentally added the wrapper, remove it.
    if (
        "answer" in parsed
        and "log_url" in parsed
    ):

        return parsed["answer"]

    return parsed


def json_response(
    payload: dict,
) -> str:

    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )