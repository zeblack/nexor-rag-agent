import json
import os
from datetime import datetime, timezone


class StructuredLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

    def _log_path(self) -> str:
        date_str = datetime.now().strftime("%Y%m%d")
        return os.path.join(self.log_dir, f"upload_{date_str}.jsonl")

    def log(self, event: str, **fields):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **fields,
        }
        with open(self._log_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
