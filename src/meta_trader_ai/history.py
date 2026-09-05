from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .models import HistoryBar, HistoryStatus, HistorySync


_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


class HistoryStore:
    def __init__(self, root: str | Path | None = None, max_bars: int = 20_000) -> None:
        self.root = Path(root or os.getenv("MTAI_HISTORY_DIR", ".mtai_data/history"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_bars = max_bars

    def _path(self, symbol: str, timeframe: str) -> Path:
        safe_symbol = _SAFE.sub("_", symbol)
        safe_tf = _SAFE.sub("_", timeframe)
        return self.root / f"{safe_symbol}_{safe_tf}.json"

    def load(self, symbol: str, timeframe: str) -> list[HistoryBar]:
        path = self._path(symbol, timeframe)
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [HistoryBar.model_validate(item) for item in payload.get("bars", [])]

    def save(self, sync: HistorySync) -> HistoryStatus:
        path = self._path(sync.symbol, sync.timeframe)
        merged = {bar.time: bar for bar in self.load(sync.symbol, sync.timeframe)}
        for bar in sync.bars:
            merged[bar.time] = bar
        bars = sorted(merged.values(), key=lambda item: item.time)[-self.max_bars :]
        payload = {
            "symbol": sync.symbol,
            "timeframe": sync.timeframe,
            "point": sync.point,
            "bars": [bar.model_dump(mode="json") for bar in bars],
        }
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(path)
        return self.status(sync.symbol, sync.timeframe)

    def point(self, symbol: str, timeframe: str) -> float | None:
        path = self._path(symbol, timeframe)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = payload.get("point")
        return float(value) if value is not None else None

    def status(self, symbol: str, timeframe: str) -> HistoryStatus:
        bars = self.load(symbol, timeframe)
        dates = sorted({bar.broker_date for bar in bars})
        return HistoryStatus(
            symbol=symbol,
            timeframe=timeframe,
            bars=len(bars),
            earliest_date=dates[0] if dates else None,
            latest_date=dates[-1] if dates else None,
            available_dates=dates,
        )
