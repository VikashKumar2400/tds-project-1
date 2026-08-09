import json
import os
import requests
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent import ask_llm
from bot_utils import build_reply_payload
from config import BOT_TOKEN, RUN_LOG_URL, TELEGRAM_WEBHOOK_URL
from logger import log_event

app = FastAPI(title="TDS Telegram Bot")


class Prompt(BaseModel):
    prompt: str


@app.get("/")
def home():
    return {"status": "running", "project": "TDS Telegram Bot"}


@app.on_event("startup")
def set_telegram_webhook():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN is missing")
        return
    if not TELEGRAM_WEBHOOK_URL:
        print("ERROR: TELEGRAM_WEBHOOK_URL is missing")
        return

    telegram_api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    try:
        response = requests.post(telegram_api_url, json={"url": TELEGRAM_WEBHOOK_URL}, timeout=10)
        print("Telegram webhook setup:")
        print(response.text)
    except Exception as e:
        print("Webhook setup failed:")
        print(str(e))


@app.post("/chat")
def chat(data: Prompt):
    try:
        answer = ask_llm(data.prompt)
    except Exception as e:
        answer = str(e)

    log_event(data.prompt, answer)
    payload = build_reply_payload(data.prompt, answer, RUN_LOG_URL)
    return payload


@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return {"ok": True}

    if "message" not in payload:
        return {"ok": True}

    message = payload["message"]
    if "text" not in message:
        return {"ok": True}

    user_message = message["text"]
    chat_id = message["chat"]["id"]

    try:
        answer = ask_llm(user_message)
    except Exception as e:
        answer = str(e)

    log_event(user_message, answer)
    payload = build_reply_payload(user_message, answer, RUN_LOG_URL)
    reply_text = json.dumps(payload, ensure_ascii=False)

    telegram_api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(telegram_api_url, json={"chat_id": chat_id, "text": reply_text}, timeout=20)
        print("Telegram response:")
        print(response.text)
    except Exception as e:
        print("Failed to send Telegram message:", str(e))

    return {"ok": True}


@app.get("/run.jsonl")
def get_run_log():
    if not os.path.exists("run.jsonl"):
        open("run.jsonl", "a", encoding="utf-8").close()

    return FileResponse("run.jsonl", media_type="application/jsonl", filename="run.jsonl")