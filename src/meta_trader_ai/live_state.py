from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock

from .models import DecisionResponse, MarketSnapshot


class LiveStateStore:
    """Keep the most recent MT5 snapshot and decision for the live dashboard."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._snapshot: MarketSnapshot | None = None
        self._decision: DecisionResponse | None = None
        self._received_at: datetime | None = None

    def update(self, snapshot: MarketSnapshot, decision: DecisionResponse) -> None:
        with self._lock:
            self._snapshot = snapshot.model_copy(deep=True)
            self._decision = decision.model_copy(deep=True)
            self._received_at = datetime.now(timezone.utc)

    def payload(self, stale_after_seconds: float = 45.0) -> dict[str, object]:
        with self._lock:
            snapshot = self._snapshot.model_copy(deep=True) if self._snapshot else None
            decision = self._decision.model_copy(deep=True) if self._decision else None
            received_at = self._received_at

        if snapshot is None or decision is None or received_at is None:
            return {
                "bridge_online": False,
                "age_seconds": None,
                "received_at": None,
                "snapshot": None,
                "decision": None,
            }

        now = datetime.now(timezone.utc)
        age_seconds = max(0.0, (now - received_at).total_seconds())
        return {
            "bridge_online": age_seconds <= stale_after_seconds,
            "age_seconds": round(age_seconds, 2),
            "received_at": received_at.isoformat(),
            "snapshot": snapshot.model_dump(mode="json"),
            "decision": decision.model_dump(mode="json"),
        }
