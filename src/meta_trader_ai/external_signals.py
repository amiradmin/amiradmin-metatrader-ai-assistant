from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import MarketSnapshot, SignalOverlay, StrategyConfig


@dataclass
class _CacheItem:
    value: SignalOverlay
    expires_at: float


class ExternalSignalHub:
    """Optional, fail-open signal overlays for live /analyze calls.

    These sources are deliberately *modifiers*, not hard blockers. If a source is
    disabled, unconfigured, rate-limited, or temporarily unreachable, the base
    six-factor strategy continues unchanged. Historical backtests do not call
    this hub, which prevents today's sentiment/COT data from leaking into old bars.
    """

    MYFXBOOK_TTL_SECONDS = 300
    COT_TTL_SECONDS = 6 * 60 * 60

    def __init__(self) -> None:
        self._cache: dict[str, _CacheItem] = {}
        self._last: dict[str, SignalOverlay] = {}
        self._myfxbook_session: str | None = None
        self._myfxbook_session_expires_at = 0.0

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _json_get(url: str, params: dict[str, str], timeout: float = 1.5) -> Any:
        target = f"{url}?{urlencode(params)}"
        request = Request(
            target,
            headers={"Accept": "application/json", "User-Agent": "MetaTraderAI/0.2"},
        )
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed trusted endpoints
            return json.loads(response.read().decode("utf-8"))

    def _cached(self, key: str) -> SignalOverlay | None:
        item = self._cache.get(key)
        if item is not None and item.expires_at > time.monotonic():
            return item.value
        return None

    def _remember(self, key: str, overlay: SignalOverlay, ttl: int) -> SignalOverlay:
        self._cache[key] = _CacheItem(overlay, time.monotonic() + ttl)
        self._last[key] = overlay
        return overlay

    def _unavailable(self, source: str, reason: str, *, ttl: int = 30) -> SignalOverlay:
        overlay = SignalOverlay(
            source=source,
            available=False,
            buy_modifier=0.0,
            sell_modifier=0.0,
            reason=reason,
        )
        return self._remember(source, overlay, ttl)

    def _myfxbook_login(self) -> str | None:
        session = os.getenv("MYFXBOOK_SESSION", "").strip()
        if session:
            return session
        if self._myfxbook_session and self._myfxbook_session_expires_at > time.monotonic():
            return self._myfxbook_session
        email = os.getenv("MYFXBOOK_EMAIL", "").strip()
        password = os.getenv("MYFXBOOK_PASSWORD", "").strip()
        if not email or not password:
            return None
        payload = self._json_get(
            "https://www.myfxbook.com/api/login.json",
            {"email": email, "password": password},
        )
        if payload.get("error") or not payload.get("session"):
            return None
        self._myfxbook_session = str(payload["session"])
        # Myfxbook sessions currently have a much longer TTL, but refresh sooner
        # so a Bridge restart or IP change can recover cleanly.
        self._myfxbook_session_expires_at = time.monotonic() + 6 * 60 * 60
        return self._myfxbook_session

    def _myfxbook(self, snapshot: MarketSnapshot) -> SignalOverlay:
        cached = self._cached("myfxbook")
        if cached is not None:
            return cached
        try:
            session = self._myfxbook_login()
            if not session:
                return self._unavailable(
                    "myfxbook",
                    "missing MYFXBOOK_SESSION or MYFXBOOK_EMAIL/MYFXBOOK_PASSWORD",
                )
            payload = self._json_get(
                "https://www.myfxbook.com/api/get-community-outlook.json",
                {"session": session},
            )
            if payload.get("error"):
                return self._unavailable("myfxbook", str(payload.get("message") or "API error"))

            symbol_key = "XAUUSD" if "XAU" in snapshot.symbol.upper() else snapshot.symbol.upper().split("_")[0]
            row = next(
                (
                    item
                    for item in payload.get("symbols", [])
                    if str(item.get("name", "")).upper() == symbol_key
                ),
                None,
            )
            if row is None:
                return self._unavailable("myfxbook", f"{symbol_key} not present in community outlook")

            long_pct = float(row.get("longPercentage", 0.0))
            short_pct = float(row.get("shortPercentage", 0.0))
            imbalance = self._clamp((long_pct - short_pct) / 100.0, -1.0, 1.0)
            # Retail sentiment is used contrarian and softly: at the theoretical
            # 100/0 extreme it can add at most 5 points to the opposite side.
            buy_modifier = max(0.0, -imbalance) * 5.0
            sell_modifier = max(0.0, imbalance) * 5.0
            overlay = SignalOverlay(
                source="myfxbook",
                available=True,
                buy_modifier=round(buy_modifier, 2),
                sell_modifier=round(sell_modifier, 2),
                reason=(
                    f"retail {long_pct:.0f}% long / {short_pct:.0f}% short; "
                    "contrarian modifier"
                ),
            )
            return self._remember("myfxbook", overlay, self.MYFXBOOK_TTL_SECONDS)
        except Exception as exc:
            return self._unavailable("myfxbook", f"fetch failed: {type(exc).__name__}")

    def _cot(self, snapshot: MarketSnapshot) -> SignalOverlay:
        cached = self._cached("cot")
        if cached is not None:
            return cached
        if "XAU" not in snapshot.symbol.upper() and "GOLD" not in snapshot.symbol.upper():
            return self._unavailable("cot", "COT gold overlay only applies to XAU/GOLD symbols", ttl=300)
        try:
            rows = self._json_get(
                "https://publicreporting.cftc.gov/resource/72hh-3qpy.json",
                {
                    "$where": "market_and_exchange_names like 'GOLD%'",
                    "$order": "report_date_as_yyyy_mm_dd DESC",
                    "$limit": "5",
                },
            )
            if not rows:
                return self._unavailable("cot", "no Gold COT rows returned", ttl=300)
            row = rows[0]
            long_pos = float(row.get("m_money_positions_long_all", 0.0))
            short_pos = float(row.get("m_money_positions_short_all", 0.0))
            total = long_pos + short_pos
            if total <= 0:
                return self._unavailable("cot", "Managed Money positions unavailable", ttl=300)
            net_ratio = self._clamp((long_pos - short_pos) / total, -1.0, 1.0)
            # Weekly macro bias stays intentionally smaller than intraday factors.
            buy_modifier = max(0.0, net_ratio) * 4.0
            sell_modifier = max(0.0, -net_ratio) * 4.0
            report_date = str(row.get("report_date_as_yyyy_mm_dd", "unknown"))[:10]
            overlay = SignalOverlay(
                source="cot",
                available=True,
                buy_modifier=round(buy_modifier, 2),
                sell_modifier=round(sell_modifier, 2),
                reason=(
                    f"CFTC Managed Money long={long_pos:.0f} short={short_pos:.0f}; "
                    f"report={report_date}"
                ),
            )
            return self._remember("cot", overlay, self.COT_TTL_SECONDS)
        except Exception as exc:
            return self._unavailable("cot", f"fetch failed: {type(exc).__name__}", ttl=300)

    def _order_flow(self, snapshot: MarketSnapshot) -> SignalOverlay:
        bars = snapshot.bars[-60:]
        if len(bars) < 20:
            return SignalOverlay(
                source="order_flow",
                available=False,
                reason="not enough bars for order-flow proxy",
            )

        # Prefer MT5 tick volume when present. Older EA snapshots have no volume,
        # so use candle range as a deterministic activity proxy rather than
        # pretending we have centralized bid/ask tape for spot XAUUSD.
        real_volume = sum(max(0.0, float(getattr(bar, "tick_volume", 0.0))) for bar in bars)
        use_tick_volume = real_volume > 0
        weighted_price = 0.0
        total_activity = 0.0
        signed_activity = 0.0
        prices: list[tuple[float, float]] = []
        for bar in bars:
            typical = (bar.high + bar.low + bar.close) / 3.0
            volume = max(0.0, float(getattr(bar, "tick_volume", 0.0)))
            activity = volume if use_tick_volume else max(bar.high - bar.low, 1e-9)
            direction = 1.0 if bar.close > bar.open else -1.0 if bar.close < bar.open else 0.0
            weighted_price += typical * activity
            total_activity += activity
            signed_activity += direction * activity
            prices.append((typical, activity))
        if total_activity <= 0:
            return SignalOverlay(source="order_flow", available=False, reason="zero market activity")

        vwap = weighted_price / total_activity
        cvd_ratio = self._clamp(signed_activity / total_activity, -1.0, 1.0)
        closes = [bar.close for bar in bars]
        tr_values = [
            max(
                bars[i].high - bars[i].low,
                abs(bars[i].high - bars[i - 1].close),
                abs(bars[i].low - bars[i - 1].close),
            )
            for i in range(1, len(bars))
        ]
        atr = sum(tr_values[-14:]) / max(1, len(tr_values[-14:]))
        vwap_distance = 0.0 if atr <= 0 else self._clamp((closes[-1] - vwap) / atr, -2.0, 2.0)

        low_price = min(p for p, _ in prices)
        high_price = max(p for p, _ in prices)
        poc = vwap
        if high_price > low_price:
            buckets = [0.0] * 16
            for price, activity in prices:
                idx = min(15, int((price - low_price) / (high_price - low_price) * 16))
                buckets[idx] += activity
            poc_idx = max(range(16), key=buckets.__getitem__)
            poc = low_price + (poc_idx + 0.5) / 16.0 * (high_price - low_price)

        buy_modifier = max(0.0, cvd_ratio) * 3.5 + max(0.0, vwap_distance) * 1.0
        sell_modifier = max(0.0, -cvd_ratio) * 3.5 + max(0.0, -vwap_distance) * 1.0
        if closes[-1] > poc:
            buy_modifier += 0.5
        elif closes[-1] < poc:
            sell_modifier += 0.5
        buy_modifier = self._clamp(buy_modifier, 0.0, 5.0)
        sell_modifier = self._clamp(sell_modifier, 0.0, 5.0)
        mode = "MT5 tick-volume" if use_tick_volume else "OHLC activity proxy"
        return SignalOverlay(
            source="order_flow",
            available=True,
            buy_modifier=round(buy_modifier, 2),
            sell_modifier=round(sell_modifier, 2),
            reason=(
                f"{mode}; CVD proxy={cvd_ratio:+.2f}; close-VWAP={vwap_distance:+.2f} ATR; "
                f"POC={poc:.2f}"
            ),
        )

    def collect(self, snapshot: MarketSnapshot, config: StrategyConfig) -> list[SignalOverlay]:
        overlays: list[SignalOverlay] = []
        if config.integrations.order_flow_enabled:
            overlay = self._order_flow(snapshot)
            self._last["order_flow"] = overlay
            overlays.append(overlay)
        if config.integrations.myfxbook_enabled:
            overlays.append(self._myfxbook(snapshot))
        if config.integrations.cot_enabled:
            overlays.append(self._cot(snapshot))
        return overlays

    def status(self, config: StrategyConfig) -> dict[str, dict[str, Any]]:
        myfxbook_configured = bool(
            os.getenv("MYFXBOOK_SESSION", "").strip()
            or (
                os.getenv("MYFXBOOK_EMAIL", "").strip()
                and os.getenv("MYFXBOOK_PASSWORD", "").strip()
            )
        )
        result: dict[str, dict[str, Any]] = {
            "myfxbook": {
                "enabled": config.integrations.myfxbook_enabled,
                "configured": myfxbook_configured,
                "note": "set MYFXBOOK_SESSION or MYFXBOOK_EMAIL + MYFXBOOK_PASSWORD",
            },
            "order_flow": {
                "enabled": config.integrations.order_flow_enabled,
                "configured": True,
                "note": "uses MT5 tick volume when supplied; safe OHLC activity proxy otherwise",
            },
            "cot": {
                "enabled": config.integrations.cot_enabled,
                "configured": True,
                "note": "CFTC Disaggregated Futures Only, Gold Managed Money",
            },
        }
        for name, overlay in self._last.items():
            if name in result:
                result[name]["last"] = overlay.model_dump(mode="json")
        return result
