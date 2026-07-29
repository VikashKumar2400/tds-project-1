import json
import os
from datetime import datetime

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "run.jsonl")

os.makedirs(LOG_DIR, exist_ok=True)


def log_event(event_type, data):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event_type,
        "data": data
    }

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")