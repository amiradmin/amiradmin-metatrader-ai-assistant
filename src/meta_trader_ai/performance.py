from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock

from .models import PerformanceSummary, TradeOutcome


class PerformanceStore:
    def __init__(self, path: str | Path | None = None) -> None:
        default = os.getenv("MTAI_PERFORMANCE_FILE", "data/trade_outcomes.jsonl")
        self.path = Path(path or default)
        self._lock = RLock()

    def append(self, outcome: TradeOutcome) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(outcome.model_dump(mode="json"), sort_keys=True) + "\n")

    def load(self) -> list[TradeOutcome]:
        with self._lock:
            if not self.path.exists():
                return []
            results: list[TradeOutcome] = []
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(TradeOutcome.model_validate_json(line))
                except Exception:
                    continue
            return results

    def summary(self, window: int = 50) -> PerformanceSummary:
        trades = self.load()
        if not trades:
            return PerformanceSummary()
        recent = trades[-window:]
        rs = [t.r_multiple for t in recent]
        wins = [r for r in rs if r > 0]
        losses = [r for r in rs if r < 0]
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_win / gross_loss if gross_loss > 0 else (999.0 if gross_win > 0 else 0.0)
        expectancy = sum(rs) / len(rs)

        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        for r in rs:
            equity += r
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)

        previous_expectancy: float | None = None
        trend = "COLLECTING"
        if len(trades) >= 20:
            half = min(window, len(trades))
            prev_start = max(0, len(trades) - 2 * half)
            prev = trades[prev_start : len(trades) - half]
            if prev:
                previous_expectancy = sum(t.r_multiple for t in prev) / len(prev)
                delta = expectancy - previous_expectancy
                if delta > 0.05:
                    trend = "IMPROVING"
                elif delta < -0.05:
                    trend = "DEGRADING"
                else:
                    trend = "FLAT"
        return PerformanceSummary(
            trades=len(recent),
            win_rate=100.0 * len(wins) / len(recent),
            profit_factor=min(profit_factor, 999.0),
            expectancy_r=expectancy,
            max_drawdown_r=max_dd,
            previous_expectancy_r=previous_expectancy,
            trend=trend,
        )
