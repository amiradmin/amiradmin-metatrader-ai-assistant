from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Literal
from urllib.request import Request, urlopen

from .models import MarketSnapshot


NewsRisk = Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]


@dataclass(frozen=True)
class NewsAssessment:
    source: str
    available: bool
    risk: NewsRisk
    reason: str
    observed_at: str
    next_event: dict[str, Any] | None = None


class NewsSourceStore:
    """Persist live news-source toggles independently from strategy thresholds."""

    def __init__(self, path: str | Path | None = None) -> None:
        default = os.getenv("MTAI_NEWS_SOURCES", "data/news_sources.json")
        self.path = Path(path or default)
        self._lock = RLock()

    def load(self) -> dict[str, bool]:
        with self._lock:
            if not self.path.exists():
                return {"forex_factory_enabled": False}
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                return {"forex_factory_enabled": False}
            return {"forex_factory_enabled": bool(payload.get("forex_factory_enabled", False))}

    def save(self, payload: dict[str, Any]) -> dict[str, bool]:
        value = {"forex_factory_enabled": bool(payload.get("forex_factory_enabled", False))}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(self.path)
        return value


class ForexFactoryCalendar:
    """Live USD economic-calendar risk for XAUUSD using Forex Factory weekly JSON.

    The calendar is deliberately fail-open at the trading-policy layer: a fetch
    failure returns UNKNOWN. Existing SafetyConfig.block_unknown_news determines
    whether UNKNOWN should block. The current project default keeps UNKNOWN
    non-blocking while HIGH remains blockable.
    """

    FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    CACHE_TTL_SECONDS = 300

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] | None = None
        self._events_expires_at = 0.0
        self._last: NewsAssessment | None = None

    @staticmethod
    def _now_utc() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _currencies_for_symbol(symbol: str) -> set[str]:
        clean = symbol.upper().split("_")[0]
        if "XAU" in clean or "GOLD" in clean:
            return {"USD"}
        known = {"USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF", "CNY"}
        found = {code for code in known if code in clean}
        return found or {"USD"}

    def _download_events(self) -> list[dict[str, Any]]:
        if self._events is not None and self._events_expires_at > time.monotonic():
            return self._events

        request = Request(
            self.FEED_URL,
            headers={
                "Accept": "application/json",
                "User-Agent": "MetaTraderAI/0.3.6",
            },
        )
        with urlopen(request, timeout=2.0) as response:  # noqa: S310 - fixed trusted endpoint
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Forex Factory weekly export did not return a list")
        events = [item for item in payload if isinstance(item, dict)]
        self._events = events
        self._events_expires_at = time.monotonic() + self.CACHE_TTL_SECONDS
        return events

    def _make(
        self,
        *,
        available: bool,
        risk: NewsRisk,
        reason: str,
        now: datetime,
        next_event: dict[str, Any] | None = None,
    ) -> NewsAssessment:
        assessment = NewsAssessment(
            source="forex_factory",
            available=available,
            risk=risk,
            reason=reason,
            observed_at=now.isoformat(),
            next_event=next_event,
        )
        self._last = assessment
        return assessment

    def assess(
        self,
        snapshot: MarketSnapshot,
        *,
        now: datetime | None = None,
        events: list[dict[str, Any]] | None = None,
    ) -> NewsAssessment:
        now_utc = (now or self._now_utc()).astimezone(timezone.utc)
        currencies = self._currencies_for_symbol(snapshot.symbol)

        try:
            rows = events if events is not None else self._download_events()
        except Exception as exc:
            return self._make(
                available=False,
                risk="UNKNOWN",
                reason=f"Forex Factory calendar unavailable: {type(exc).__name__}",
                now=now_utc,
            )

        relevant: list[tuple[float, str, str, datetime, dict[str, Any]]] = []
        for row in rows:
            country = str(row.get("country", "")).upper().strip()
            impact = str(row.get("impact", "")).strip().title()
            if country not in currencies or impact not in {"High", "Medium"}:
                continue
            event_time = self._parse_time(row.get("date"))
            if event_time is None:
                continue
            minutes = (event_time - now_utc).total_seconds() / 60.0
            relevant.append((minutes, impact, str(row.get("title", "event")), event_time, row))

        if not relevant:
            return self._make(
                available=True,
                risk="LOW",
                reason=f"Forex Factory: no High/Medium {','.join(sorted(currencies))} event in weekly feed",
                now=now_utc,
            )

        relevant.sort(key=lambda item: abs(item[0]))
        selected_risk: NewsRisk = "LOW"
        selected: tuple[float, str, str, datetime, dict[str, Any]] | None = None

        for item in relevant:
            minutes, impact, _, _, _ = item
            risk: NewsRisk = "LOW"
            if impact == "High" and -15.0 <= minutes <= 30.0:
                risk = "HIGH"
            elif impact == "High" and 30.0 < minutes <= 60.0:
                risk = "MEDIUM"
            elif impact == "Medium" and -10.0 <= minutes <= 20.0:
                risk = "MEDIUM"

            if risk == "HIGH":
                selected_risk = risk
                selected = item
                break
            if risk == "MEDIUM" and selected_risk == "LOW":
                selected_risk = risk
                selected = item

        if selected is None:
            upcoming = [item for item in relevant if item[0] > 0]
            nearest = min(upcoming, key=lambda item: item[0]) if upcoming else relevant[0]
            minutes, impact, title, event_time, row = nearest
            direction = "in" if minutes >= 0 else "ago"
            distance = abs(minutes)
            return self._make(
                available=True,
                risk="LOW",
                reason=(
                    f"Forex Factory LOW; nearest {row.get('country', '')} {impact} event "
                    f"'{title}' {direction} {distance:.0f}m"
                ),
                now=now_utc,
                next_event={
                    "title": title,
                    "country": row.get("country"),
                    "impact": impact,
                    "date": event_time.isoformat(),
                    "minutes": round(minutes, 1),
                },
            )

        minutes, impact, title, event_time, row = selected
        timing = f"in {minutes:.0f}m" if minutes >= 0 else f"{abs(minutes):.0f}m ago"
        return self._make(
            available=True,
            risk=selected_risk,
            reason=(
                f"Forex Factory {selected_risk}: {row.get('country', '')} {impact} "
                f"'{title}' {timing}"
            ),
            now=now_utc,
            next_event={
                "title": title,
                "country": row.get("country"),
                "impact": impact,
                "date": event_time.isoformat(),
                "minutes": round(minutes, 1),
            },
        )

    def status(self, enabled: bool) -> dict[str, Any]:
        result: dict[str, Any] = {
            "source": "forex_factory",
            "enabled": enabled,
            "configured": True,
            "feed": self.FEED_URL,
            "cache_seconds": self.CACHE_TTL_SECONDS,
            "policy": (
                "XAU/GOLD watches USD events; High is HIGH from 30m before to 15m after; "
                "High 30-60m ahead and Medium near release become MEDIUM"
            ),
        }
        if self._last is not None:
            result["last"] = asdict(self._last)
        return result
