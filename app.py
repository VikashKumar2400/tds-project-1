from fastapi import FastAPI
from pydantic import BaseModel

from logger import log_event
from agent import ask_llm

app = FastAPI()


class Prompt(BaseModel):
    prompt: str


@app.get("/")
def home():
    return {
        "status": "running",
        "project": "TDS Telegram Bot"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(data: Prompt):

    log_event("prompt", data.prompt)

    answer = ask_llm(data.prompt)

    log_event("response", answer)

    return {
        "response": answer
    }