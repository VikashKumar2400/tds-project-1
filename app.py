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


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/")
def home():
    return {
        "status": "running",
        "project": "TDS Telegram Bot"
    }


# =========================================================
# JSON PARSER
# =========================================================

def parse_json_response(text: str):

    if not text:
        return None

    text = text.strip()

    # Remove markdown code fences if Gemini returns them
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


# =========================================================
# TELEGRAM WEBHOOK SETUP
# =========================================================

@app.on_event("startup")
def set_telegram_webhook():

    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN is missing")
        return

    if not TELEGRAM_WEBHOOK_URL:
        print("ERROR: TELEGRAM_WEBHOOK_URL is missing")
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

        print("Telegram webhook setup:")
        print(response.text)

    except Exception as e:

        print("Webhook setup failed:")
        print(str(e))


# =========================================================
# NORMAL API CHAT ENDPOINT
# =========================================================

@app.post("/chat")
def chat(data: Prompt):

    try:

        answer = ask_llm(data.prompt)

    except Exception as e:

        answer = str(e)

    log_event(
        data.prompt,
        answer
    )

    parsed = parse_json_response(answer)

    if isinstance(parsed, dict):

        # Add log_url only if the question asks for it
        if "log_url" in data.prompt.lower():

            parsed["log_url"] = RUN_LOG_URL

        return parsed

    return {
        "answer": answer,
        "log_url": RUN_LOG_URL
    }


# =========================================================
# TELEGRAM WEBHOOK
# =========================================================

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):

    try:

        payload = await request.json()

    except Exception:

        return {
            "ok": True
        }

    # Ignore non-message updates
    if "message" not in payload:

        return {
            "ok": True
        }

    message = payload["message"]

    # Ignore messages without text
    if "text" not in message:

        return {
            "ok": True
        }

    user_message = message["text"]

    chat_id = message["chat"]["id"]

    # =====================================================
    # ASK LLM
    # =====================================================

    try:

        answer = ask_llm(user_message)

    except Exception as e:

        answer = str(e)

    # =====================================================
    # LOG
    # =====================================================

    try:

        log_event(
            user_message,
            answer
        )

    except Exception as e:

        print("Logging error:", str(e))

    # =====================================================
    # PARSE LLM RESPONSE
    # =====================================================

    parsed_answer = parse_json_response(answer)

    if isinstance(parsed_answer, dict):

        # Only add log_url when the user requested it
        if "log_url" in user_message.lower():

            parsed_answer["log_url"] = RUN_LOG_URL

        reply_text = json.dumps(
            parsed_answer,
            separators=(",", ":"),
            ensure_ascii=False
        )

    else:

        reply_text = json.dumps(
            {
                "answer": answer,
                "log_url": RUN_LOG_URL
            },
            separators=(",", ":"),
            ensure_ascii=False
        )

    # =====================================================
    # SEND RESPONSE TO TELEGRAM
    # =====================================================

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

        print("Telegram response:")
        print(response.text)

    except Exception as e:

        print(
            "Failed to send Telegram message:",
            str(e)
        )

    return {
        "ok": True
    }


# =========================================================
# PUBLIC JSONL LOG
# =========================================================

@app.get("/run.jsonl")
def get_run_log():

    if not os.path.exists("run.jsonl"):

        open(
            "run.jsonl",
            "a",
            encoding="utf-8"
        ).close()

    return FileResponse(
        "run.jsonl",
        media_type="application/jsonl",
        filename="run.jsonl"
    )