from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LonaReportStore:
    """Persist the latest independent LONA validation snapshot for the UI.

    The ChatGPT LONA connector is not the same process as the local FastAPI
    bridge, so results are imported into this small JSON store. This also keeps
    the panel useful when LONA is temporarily unavailable.
    """

    def __init__(self, path: str | Path = "data/lona_latest.json") -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "status": "NOT_RUN",
                "message": "No LONA validation has been imported yet.",
            }
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"status": "INVALID"}
        except (OSError, json.JSONDecodeError):
            return {
                "status": "INVALID",
                "message": "Could not read data/lona_latest.json",
            }

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return payload
