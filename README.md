# TDS Telegram Bot

This project implements a Telegram bot that answers data-analysis questions and replies with a JSON payload shaped like:

{"answer": ..., "log_url": "https://.../run.jsonl"}

## Setup

1. Copy .env.example to .env and fill in your tokens.
2. Install dependencies:
   pip install -r requirements.txt
3. Start the FastAPI app:
   uvicorn app:app --reload
4. Start the polling bot locally (optional):
   python telegram_bot.py

## Notes

- The bot uses the aipipe OpenAI-compatible API.
- Every interaction is appended to run.jsonl for public logging.
- The deployment URL should be set as TELEGRAM_WEBHOOK_URL and RUN_LOG_URL.
