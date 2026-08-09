import os

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


def ask_llm(prompt: str) -> str:
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a careful data analyst. Reply with only a JSON object "
                        "that matches the user's requested shape. If the user asks for "
                        "an answer field, return a JSON object with exactly an 'answer' "
                        "field and a 'log_url' field when appropriate."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        return f"Error: {e}"