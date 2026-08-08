from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import json
import requests

from agent import ask_llm
from logger import log_event
from config import BOT_TOKEN, TELEGRAM_WEBHOOK_URL, RUN_LOG_URL

app = FastAPI(title="TDS Telegram Bot")


class Prompt(BaseModel):
    prompt: str


@app.get("/")
def home():
    return {
        "status": "running",
        "project": "TDS Telegram Bot"
    }


def parse_json_response(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


@app.post("/chat")
def chat(data: Prompt):
    answer = ask_llm(data.prompt)
    log_event(data.prompt, answer)

    parsed = parse_json_response(answer)
    if isinstance(parsed, dict):
        parsed["log_url"] = RUN_LOG_URL
        return parsed

    return {
        "answer": answer,
        "log_url": RUN_LOG_URL
    }


@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    payload = await request.json()

    if "message" not in payload or "text" not in payload["message"]:
        return {"ok": True}

    user_message = payload["message"]["text"]
    chat_id = payload["message"]["chat"]["id"]

    try:
        answer = ask_llm(user_message)
    except Exception as e:
        answer = str(e)

    log_event(user_message, answer)

    parsed_answer = parse_json_response(answer)
    if parsed_answer is not None:
        parsed_answer["log_url"] = RUN_LOG_URL
        reply_text = json.dumps(parsed_answer)
    else:
        reply_text = json.dumps({
            "answer": answer,
            "log_url": RUN_LOG_URL,
        })

    telegram_api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(telegram_api_url, json={
        "chat_id": chat_id,
        "text": reply_text,
    })

    return {"ok": True}


@app.get("/run.jsonl")
def get_run_log():
    if not os.path.exists("run.jsonl"):
        open("run.jsonl", "a").close()

    return FileResponse(
        "run.jsonl",
        media_type="application/json",
        filename="run.jsonl"
    )