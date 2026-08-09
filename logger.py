import json
from datetime import datetime

LOG_FILE = "run.jsonl"


def log_event(question, answer):
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "question": question,
        "answer": answer,
    }

    with open(LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")