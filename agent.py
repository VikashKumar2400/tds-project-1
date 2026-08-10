import json
import os
import re
from typing import List, Dict, Optional

import requests
from openai import OpenAI

from config import AIPIPE_API_KEY, MODEL


def _get_client() -> OpenAI:
    api_key = AIPIPE_API_KEY or os.getenv("AIPIPE_TOKEN")

    if not api_key:
        raise ValueError("AIPIPE_API_KEY or AIPIPE_TOKEN must be set")

    return OpenAI(
        base_url="https://aipipe.org/openai/v1",
        api_key=api_key,
    )


SYSTEM_PROMPT = """
You are a careful data analyst and reasoning agent.

Your job is to answer the user's data-analysis question accurately.

IMPORTANT OUTPUT RULES:

1. The user's message specifies the exact JSON shape that must be returned.
2. Follow that JSON shape exactly.
3. Return ONLY one valid JSON object.
4. Do not use Markdown.
5. Do not use ```json fences.
6. Do not add explanations.
7. Do not add fields that the user did not request.
8. Do not automatically add "answer" or "log_url".
9. If the requested shape is {"value": ...}, return {"value": ...}.
10. If the requested shape is
    {"answer": {"sd": ...}, "log_url": "..."},
    return that exact structure.
11. Preserve list order.
12. Preserve nested object structure.
13. Use exact numbers when the question asks for exact integers.
14. Apply requested rounding.
15. For population standard deviation, divide by N, not N-1.
16. For multi-turn questions, use the previous conversation messages supplied
    to you as context.
17. Never mention your reasoning in the final output.
18. The final response must be valid JSON.

When external data is supplied in the prompt, use that data.
When a URL and its fetched content are supplied in the prompt, use the
fetched content rather than guessing.
"""


def _extract_urls(text: str) -> List[str]:
    """
    Extract HTTP/HTTPS URLs from the user's message.
    """
    return re.findall(r'https?://[^\s<>"\']+', text)


def _fetch_url(url: str) -> Optional[str]:
    """
    Fetch a public URL and return its content.

    This is intentionally limited to normal HTTP/HTTPS GET requests.
    """
    try:
        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": "TDS-Data-Analyst-Bot/1.0"
            },
        )

        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()

        # JSON/API response
        if "json" in content_type:
            try:
                data = response.json()
                return json.dumps(data, ensure_ascii=False)
            except Exception:
                return response.text[:30000]

        # Text/CSV/HTML/etc.
        return response.text[:30000]

    except Exception as e:
        return f"URL_FETCH_ERROR: {type(e).__name__}: {str(e)}"


def _get_external_data(prompt: str) -> str:
    """
    Fetch publicly referenced URLs from the question.

    This allows tests such as:
    Fetch https://api.github.com/repos/octocat/Hello-World
    """
    urls = _extract_urls(prompt)

    if not urls:
        return ""

    parts = []

    for url in urls[:5]:
        content = _fetch_url(url)

        parts.append(
            f"""
EXTERNAL DATA FROM URL:
{url}

CONTENT:
{content}
"""
        )

    return "\n".join(parts)


def ask_llm(
    prompt: str,
    history: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Ask the LLM to solve the current question.

    history contains previous user/assistant messages for multi-turn
    conversations.
    """

    client = _get_client()

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    # Add previous conversation history.
    if history:
        messages.extend(history[-20:])

    # Fetch publicly referenced URLs.
    external_data = _get_external_data(prompt)

    current_prompt = prompt

    if external_data:
        current_prompt += """

IMPORTANT:
The following external data was fetched from URLs explicitly referenced
by the user. Use it to answer the question.

""" + external_data

    messages.append(
        {
            "role": "user",
            "content": current_prompt,
        }
    )

    print("===== LLM REQUEST =====")
    print("MODEL:", MODEL)
    print("PROMPT:", current_prompt)

    try:
        response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        )

        content = response.choices[0].message.content or ""

        print("===== LLM RESPONSE =====")
        print(repr(content))
        print("========================")

        return content.strip()

    except Exception as e:
        print("===== LLM ERROR =====")
        print(type(e).__name__)
        print(str(e))
        print("=====================")
        raise