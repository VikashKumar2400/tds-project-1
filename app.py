from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import json

from agent import ask_llm
from logger import log_event

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
        parsed["log_url"] = "https://tds-telegram-bot-ihrg.onrender.com/run.jsonl"
        return parsed

    return {
        "answer": answer,
        "log_url": "https://tds-telegram-bot-ihrg.onrender.com/run.jsonl"
    }


@app.get("/run.jsonl")
def get_run_log():
    if not os.path.exists("run.jsonl"):
        open("run.jsonl", "a").close()

    return FileResponse(
        "run.jsonl",
        media_type="application/json",
        filename="run.jsonl"
    )