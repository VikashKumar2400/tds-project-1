import json
from telegram import Update
from logger import log_event

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN
from agent import ask_llm


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! I'm your TDS Telegram Bot.\nSend me any question."
    )


def parse_model_json(text: str):
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return None


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    try:
        answer = ask_llm(user_message)
    except Exception as e:
        answer = str(e)

    log_event(user_message, answer)

    parsed_answer = parse_model_json(answer)
    if parsed_answer is not None:
        parsed_answer["log_url"] = "https://tds-telegram-bot-ihrg.onrender.com/run.jsonl"
        await update.message.reply_text(json.dumps(parsed_answer))
        return

    response = {
        "answer": answer,
        "log_url": "https://tds-telegram-bot-ihrg.onrender.com/run.jsonl"
    }

    await update.message.reply_text(json.dumps(response))


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("Telegram bot is running...")

    app.run_polling()


import asyncio

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main()