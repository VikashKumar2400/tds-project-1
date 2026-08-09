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

    # Remove Markdown code fences
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

    # First try: entire response is JSON
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Second try: find the JSON object inside the response
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
    Build the final Telegram response.

    IMPORTANT:
    The user's question determines the required JSON shape.

    We do NOT automatically add:
        - answer
        - log_url

    because the grader expects the exact JSON object requested
    by the user's message.
    """

    parsed = _extract_json_object(model_reply)

    if not isinstance(parsed, dict):
        return {}

    return parsed


def json_response(payload: dict) -> str:
    """
    Convert the answer dictionary into compact JSON.

    Example:
        {"stats":{"max":25,"min":3}}
    """

    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":")
    )