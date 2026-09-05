from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import Any


class DecisionJournal:
    """Stores explainable decisions so a closed trade can be joined to its signal."""

    def __init__(self, path: str | Path | None = None) -> None:
        default = os.getenv("MTAI_DECISION_JOURNAL", "data/decisions.jsonl")
        self.path = Path(path or default)
        self._lock = RLock()

    def append(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, sort_keys=True, default=str) + "\n")

    def find(self, signal_id: str) -> dict[str, Any] | None:
        with self._lock:
            if not self.path.exists():
                return None
            for line in reversed(self.path.read_text(encoding="utf-8").splitlines()):
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if row.get("signal_id") == signal_id:
                    return row
        return None
