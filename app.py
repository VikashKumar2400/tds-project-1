from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import os

from agent import ask_llm

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
    return {"response": answer}


@app.get("/run.jsonl")
def get_run_log():
    if not os.path.exists("run.jsonl"):
        open("run.jsonl", "a").close()

    return FileResponse(
        "run.jsonl",
        media_type="application/json",
        filename="run.jsonl"
    )