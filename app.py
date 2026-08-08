from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import os

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


@app.post("/chat")
def chat(data: Prompt):
    answer = ask_llm(data.prompt)
    log_event(data.prompt, answer)

    response = {
        "answer": answer,
        "log_url": "https://tds-telegram-bot-ihrg.onrender.com/run.jsonl"
    }
    return response


@app.get("/run.jsonl")
def get_run_log():
    if not os.path.exists("run.jsonl"):
        open("run.jsonl", "a").close()

    return FileResponse(
        "run.jsonl",
        media_type="application/json",
        filename="run.jsonl"
    )