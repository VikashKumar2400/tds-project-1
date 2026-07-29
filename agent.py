from google import genai
from config import GEMINI_API_KEY, MODEL

client = genai.Client(api_key=GEMINI_API_KEY)


def ask_llm(prompt: str) -> str:
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )
        return response.text

    except Exception as e:
        return f"Error: {e}"