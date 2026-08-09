import os

from openai import OpenAI

from config import AIPIPE_API_KEY, MODEL


def _get_client() -> OpenAI:
    api_key = AIPIPE_API_KEY or os.getenv("AIPIPE_TOKEN")

    if not api_key:
        raise ValueError(
            "AIPIPE_API_KEY or AIPIPE_TOKEN must be set"
        )

    return OpenAI(
        base_url="https://aipipe.org/openai/v1",
        api_key=api_key,
    )


def ask_llm(prompt: str) -> str:
    client = _get_client()

    print("===== LLM REQUEST =====")
    print("MODEL:", MODEL)
    print("PROMPT:", prompt)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a careful data analyst.\n\n"
                        "Solve the user's question accurately.\n"
                        "The user's message specifies the exact JSON shape "
                        "that must be returned.\n\n"
                        "Return ONLY one valid JSON object.\n"
                        "Do not use Markdown.\n"
                        "Do not use ```json fences.\n"
                        "Do not add explanations.\n"
                        "Do not add fields that the user did not request.\n"
                        "Preserve the exact requested JSON structure."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        content = response.choices[0].message.content

        print("===== LLM RESPONSE =====")
        print(repr(content))
        print("========================")

        return content or ""

    except Exception as e:
        print("===== LLM ERROR =====")
        print(type(e).__name__)
        print(str(e))
        print("=====================")
        raise