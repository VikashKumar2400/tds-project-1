import json
import os
from datetime import datetime

LOG_FILE = "run.jsonl"

def log_event(question, answer):
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "question": question,
        "answer": answer
    }

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")