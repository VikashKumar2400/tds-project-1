import json
import os
import requests

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent import ask_llm
from bot_utils import build_reply_payload
from config import (
    BOT_TOKEN,
    RUN_LOG_URL,
    TELEGRAM_WEBHOOK_URL,
)
from logger import log_event


app = FastAPI(
    title="TDS Telegram Bot"
)


# ============================================================
# Conversation state
# ============================================================

conversation_history = {}

MAX_HISTORY_MESSAGES = 12


# Telegram update IDs already processed.
processed_updates = set()

MAX_PROCESSED_UPDATES = 1000


def get_history(chat_id):

    return conversation_history.get(
        chat_id,
        [],
    )


def add_history(
    chat_id,
    role,
    content,
):

    if chat_id not in conversation_history:

        conversation_history[chat_id] = []

    conversation_history[
        chat_id
    ].append(
        {
            "role": role,
            "content": content,
        }
    )

    conversation_history[
        chat_id
    ] = conversation_history[
        chat_id
    ][-MAX_HISTORY_MESSAGES:]


# ============================================================
# Home
# ============================================================

@app.get("/")
def home():

    return {
        "status": "running",
        "project": "TDS Telegram Bot",
    }


# ============================================================
# Startup
# ============================================================

@app.on_event("startup")
def set_telegram_webhook():

    if not BOT_TOKEN:

        print(
            "ERROR: BOT_TOKEN is missing"
        )

        return

    if not TELEGRAM_WEBHOOK_URL:

        print(
            "ERROR: TELEGRAM_WEBHOOK_URL is missing"
        )

        return

    telegram_api_url = (
        "https://api.telegram.org/"
        f"bot{BOT_TOKEN}/setWebhook"
    )

    try:

        response = requests.post(
            telegram_api_url,
            json={
                "url": TELEGRAM_WEBHOOK_URL
            },
            timeout=10,
        )

        print(
            "Telegram webhook setup:"
        )

        print(
            response.text
        )

    except Exception as e:

        print(
            "Webhook setup failed:"
        )

        print(
            str(e)
        )


# ============================================================
# Manual /chat endpoint
# ============================================================

class Prompt(BaseModel):

    prompt: str


@app.post("/chat")
def chat(data: Prompt):

    try:

        answer = ask_llm(
            data.prompt
        )

    except Exception as e:

        print(
            "CHAT LLM ERROR:",
            repr(e),
        )

        answer = ""

    log_event(
        data.prompt,
        answer,
    )

    payload = build_reply_payload(
        data.prompt,
        answer,
        RUN_LOG_URL,
    )

    return payload


# ============================================================
# Telegram webhook
# ============================================================

@app.post("/telegram-webhook")
async def telegram_webhook(
    request: Request,
):

    try:

        update = await request.json()

    except Exception as e:

        print(
            "Invalid Telegram JSON:",
            repr(e),
        )

        return {
            "ok": True
        }

    print(
        "===== TELEGRAM UPDATE ====="
    )

    print(
        update
    )

    update_id = update.get(
        "update_id"
    )

    # --------------------------------------------------------
    # Avoid processing the same Telegram update twice.
    # --------------------------------------------------------

    if update_id is not None:

        if update_id in processed_updates:

            print(
                "Duplicate update ignored:",
                update_id,
            )

            return {
                "ok": True
            }

        processed_updates.add(
            update_id
        )

        # Keep memory bounded.
        if (
            len(processed_updates)
            > MAX_PROCESSED_UPDATES
        ):

            processed_updates.pop()


    # --------------------------------------------------------
    # Validate message.
    # --------------------------------------------------------

    if "message" not in update:

        return {
            "ok": True
        }

    message = update[
        "message"
    ]

    if "text" not in message:

        return {
            "ok": True
        }

    user_message = message[
        "text"
    ]

    chat_id = message[
        "chat"
    ]["id"]


    print(
        "===== CHAT ID ====="
    )

    print(
        chat_id
    )

    print(
        "===== USER MESSAGE ====="
    )

    print(
        user_message
    )


    # --------------------------------------------------------
    # Previous conversation.
    # --------------------------------------------------------

    history = get_history(
        chat_id
    )

    print(
        "===== HISTORY ====="
    )

    print(
        history
    )


    # --------------------------------------------------------
    # Ask LLM.
    # --------------------------------------------------------

    try:

        answer = ask_llm(
            user_message,
            history=history,
        )

    except Exception as e:

        print(
            "===== TELEGRAM LLM ERROR ====="
        )

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        print(
            "=============================="
        )

        answer = ""


    print(
        "===== RAW ANSWER ====="
    )

    print(
        repr(answer)
    )


    # --------------------------------------------------------
    # Save conversation.
    # --------------------------------------------------------

    add_history(
        chat_id,
        "user",
        user_message,
    )

    add_history(
        chat_id,
        "assistant",
        answer,
    )


    # --------------------------------------------------------
    # Log.
    # --------------------------------------------------------

    log_event(
        user_message,
        answer,
    )


    # --------------------------------------------------------
    # Build exact final JSON.
    # --------------------------------------------------------

    payload = build_reply_payload(
        user_message,
        answer,
        RUN_LOG_URL,
    )


    print(
        "===== FINAL PAYLOAD ====="
    )

    print(
        payload
    )


    reply_text = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )


    print(
        "===== TELEGRAM REPLY ====="
    )

    print(
        reply_text
    )


    # --------------------------------------------------------
    # Send Telegram response.
    # --------------------------------------------------------

    telegram_api_url = (
        "https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    try:

        response = requests.post(
            telegram_api_url,
            json={
                "chat_id": chat_id,
                "text": reply_text,
            },
            timeout=20,
        )

        print(
            "Telegram response:"
        )

        print(
            response.text
        )

    except Exception as e:

        print(
            "Failed to send Telegram message:"
        )

        print(
            str(e)
        )


    return {
        "ok": True
    }


# ============================================================
# Public JSONL log
# ============================================================

@app.get("/run.jsonl")
def get_run_log():

    if not os.path.exists(
        "run.jsonl"
    ):

        open(
            "run.jsonl",
            "a",
            encoding="utf-8",
        ).close()


    return FileResponse(
        "run.jsonl",
        media_type="application/jsonl",
        filename="run.jsonl",
    )