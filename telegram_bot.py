import asyncio
import json

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agent import ask_llm
from config import BOT_TOKEN, RUN_LOG_URL
from logger import log_event
from bot_utils import build_reply_payload


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! I'm your TDS Telegram Bot.\nSend me any question."
    )


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text or ""

    try:
        answer = ask_llm(user_message)
    except Exception as e:
        answer = str(e)

    log_event(user_message, answer)

    payload = build_reply_payload(user_message, answer, RUN_LOG_URL)
    await update.message.reply_text(json.dumps(payload, ensure_ascii=False))


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("Telegram bot is running...")
    app.run_polling()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main()