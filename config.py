import os

from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = (
    os.getenv("BOT_TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN")
)


AIPIPE_API_KEY = (
    os.getenv("AIPIPE_API_KEY")
    or os.getenv("AIPIPE_TOKEN")
)


MODEL = os.getenv(
    "MODEL",
    "gpt-5-mini",
)


TELEGRAM_WEBHOOK_URL = os.getenv(
    "TELEGRAM_WEBHOOK_URL",
    "https://tds-telegram-bot-ihrg.onrender.com/telegram-webhook",
)


RUN_LOG_URL = os.getenv(
    "RUN_LOG_URL",
    "https://tds-telegram-bot-ihrg.onrender.com/run.jsonl",
)