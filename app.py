from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import json
import re
import requests

from agent import ask_llm
from logger import log_event
from config import BOT_TOKEN, TELEGRAM_WEBHOOK_URL, RUN_LOG_URL


app = FastAPI(title="TDS Telegram Bot")


class Prompt(BaseModel):
    prompt: str


# --------------------------------
# HOME / HEALTH CHECK
# --------------------------------

@app.get("/")
def home():
    return {
        "status": "running",
        "project": "TDS Telegram Bot"
    }


# --------------------------------
# JSON PARSER
# --------------------------------

def parse_json_response(text: str):

    if not text:
        return None

    text = text.strip()

    # Remove ```json ... ``` if Gemini returns markdown
    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^```\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    text = text.strip()

    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        return None

    return None


# --------------------------------
# SET TELEGRAM WEBHOOK
# --------------------------------

@app.on_event("startup")
def set_telegram_webhook():

    if not TELEGRAM_WEBHOOK_URL:
        print("TELEGRAM_WEBHOOK_URL is not configured.")
        return

    telegram_api_url = (
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    )

    try:

        response = requests.post(
            telegram_api_url,
            json={
                "url": TELEGRAM_WEBHOOK_URL
            },
            timeout=10
        )

        print("Telegram webhook response:")
        print(response.text)

    except Exception as e:

        print("Failed to set Telegram webhook:")
        print(e)


# --------------------------------
# OPTIONAL HTTP CHAT ENDPOINT
# --------------------------------

@app.post("/chat")
def chat(data: Prompt):

    answer = ask_llm(data.prompt)

    log_event(
        data.prompt,
        answer
    )

    parsed = parse_json_response(answer)

    if isinstance(parsed, dict):

        # Only add log_url if the requested
        # schema contains log_url.
        if "log_url" in data.prompt:
            parsed["log_url"] = RUN_LOG_URL

        return parsed

    return {
        "answer": answer,
        "log_url": RUN_LOG_URL
    }


# --------------------------------
# TELEGRAM WEBHOOK
# --------------------------------

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):

    payload = await request.json()

    # Ignore updates that don't contain text messages
    if (
        "message" not in payload
        or "text" not in payload["message"]
    ):
        return {"ok": True}

    user_message = payload["message"]["text"]

    chat_id = payload["message"]["chat"]["id"]

    # --------------------------------
    # ASK LLM
    # --------------------------------

    try:

        answer = ask_llm(user_message)

    except Exception as e:

        answer = str(e)

    # --------------------------------
    # LOG
    # --------------------------------

    log_event(
        user_message,
        answer
    )

    # --------------------------------
    # PARSE JSON
    # --------------------------------

    parsed_answer = parse_json_response(answer)

    if isinstance(parsed_answer, dict):

        # Add log_url only when the
        # user's requested JSON contains it.
        if "log_url" in user_message:

            parsed_answer["log_url"] = RUN_LOG_URL

        reply_text = json.dumps(
            parsed_answer,
            separators=(",", ":")
        )

    else:

        reply_text = json.dumps(
            {
                "answer": answer,
                "log_url": RUN_LOG_URL
            },
            separators=(",", ":")
        )

    # --------------------------------
    # SEND TELEGRAM RESPONSE
    # --------------------------------

    telegram_api_url = (
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    )

    try:

        response = requests.post(
            telegram_api_url,
            json={
                "chat_id": chat_id,
                "text": reply_text
            },
            timeout=20
        )

        print("Telegram sendMessage response:")
        print(response.text)

    except Exception as e:

        print("Failed to send Telegram response:")
        print(e)

    return {"ok": True}


# --------------------------------
# PUBLIC JSONL LOG
# --------------------------------

@app.get("/run.jsonl")
def get_run_log():

    if not os.path.exists("run.jsonl"):
        open("run.jsonl", "a").close()

    return FileResponse(
        "run.jsonl",
        media_type="application/jsonl",
        filename="run.jsonl"
    )