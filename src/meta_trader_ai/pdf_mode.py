from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from statistics import fmean

from .models import Decision, MarketSnapshot


class PdfRegime(StrEnum):
    STRONG_UPTREND = "STRONG_UPTREND"
    WEAK_UPTREND = "WEAK_UPTREND"
    STRONG_DOWNTREND = "STRONG_DOWNTREND"
    WEAK_DOWNTREND = "WEAK_DOWNTREND"
    RANGE = "RANGE"
    SPIKE_UP = "SPIKE_UP"
    SPIKE_DOWN = "SPIKE_DOWN"
    UNKNOWN = "UNKNOWN"


class PdfRangeZone(StrEnum):
    LOWER_EDGE = "LOWER_EDGE"
    MIDDLE = "MIDDLE"
    UPPER_EDGE = "UPPER_EDGE"
    OUTSIDE = "OUTSIDE"
    UNAVAILABLE = "UNAVAILABLE"


class PdfBreakout(StrEnum):
    NONE = "NONE"
    VALID_UP = "VALID_UP"
    VALID_DOWN = "VALID_DOWN"
    FAKE_UP = "FAKE_UP"
    FAKE_DOWN = "FAKE_DOWN"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class PdfModeSettings:
    range_lookback: int = 24
    trend_lookback: int = 20
    range_edge_fraction: float = 0.20
    touch_tolerance_atr: float = 0.20
    breakout_step_bars: int = 5
    breakout_body_multiple: float = 1.50
    weak_efficiency_min: float = 0.25
    strong_efficiency_min: float = 0.45
    weak_move_atr_min: float = 1.00
    strong_move_atr_min: float = 2.00
    spike_body_atr_min: float = 1.80


@dataclass(frozen=True, slots=True)
class PdfModeEvaluation:
    status: str
    allowed: bool
    reason: str | None
    regime: PdfRegime
    range_zone: PdfRangeZone
    breakout: PdfBreakout
    lower_touch_count: int
    upper_touch_count: int
    efficiency_ratio: float
    net_move_atr: float


def _true_ranges(snapshot: MarketSnapshot) -> list[float]:
    bars = snapshot.bars
    result: list[float] = []
    for previous, current in zip(bars, bars[1:]):
        result.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return result


def _atr(snapshot: MarketSnapshot, period: int = 14) -> float:
    values = _true_ranges(snapshot)[-period:]
    return max(fmean(values) if values else 0.0, 1e-12)


def _trend_metrics(snapshot: MarketSnapshot, lookback: int, atr: float) -> tuple[float, float]:
    closes = [bar.close for bar in snapshot.bars[-(lookback + 1) :]]
    if len(closes) < 3:
        return 0.0, 0.0
    net_move = closes[-1] - closes[0]
    travelled = sum(abs(current - previous) for previous, current in zip(closes, closes[1:]))
    efficiency = abs(net_move) / travelled if travelled > 1e-12 else 0.0
    return efficiency, net_move / atr


def _classify_regime(
    snapshot: MarketSnapshot,
    settings: PdfModeSettings,
    atr: float,
) -> tuple[PdfRegime, float, float]:
    efficiency, net_move_atr = _trend_metrics(snapshot, settings.trend_lookback, atr)
    latest = snapshot.bars[-1]
    latest_body = latest.close - latest.open
    if abs(latest_body) / atr >= settings.spike_body_atr_min:
        return (
            PdfRegime.SPIKE_UP if latest_body > 0 else PdfRegime.SPIKE_DOWN,
            efficiency,
            net_move_atr,
        )

    strong = (
        efficiency >= settings.strong_efficiency_min
        and abs(net_move_atr) >= settings.strong_move_atr_min
    )
    weak = (
        efficiency >= settings.weak_efficiency_min
        and abs(net_move_atr) >= settings.weak_move_atr_min
    )
    if strong and net_move_atr > 0:
        return PdfRegime.STRONG_UPTREND, efficiency, net_move_atr
    if strong and net_move_atr < 0:
        return PdfRegime.STRONG_DOWNTREND, efficiency, net_move_atr
    if weak and net_move_atr > 0:
        return PdfRegime.WEAK_UPTREND, efficiency, net_move_atr
    if weak and net_move_atr < 0:
        return PdfRegime.WEAK_DOWNTREND, efficiency, net_move_atr
    return PdfRegime.RANGE, efficiency, net_move_atr


def _range_context(
    snapshot: MarketSnapshot,
    settings: PdfModeSettings,
    atr: float,
) -> tuple[PdfRangeZone, PdfBreakout, int, int]:
    lookback = max(8, settings.range_lookback)
    if len(snapshot.bars) < lookback + 1:
        return PdfRangeZone.UNAVAILABLE, PdfBreakout.UNAVAILABLE, 0, 0

    prior = snapshot.bars[-(lookback + 1) : -1]
    latest = snapshot.bars[-1]
    range_high = max(bar.high for bar in prior)
    range_low = min(bar.low for bar in prior)
    width = range_high - range_low
    if width <= 1e-12:
        return PdfRangeZone.UNAVAILABLE, PdfBreakout.UNAVAILABLE, 0, 0

    if latest.close < range_low or latest.close > range_high:
        zone = PdfRangeZone.OUTSIDE
    else:
        position = (latest.close - range_low) / width
        edge = min(0.45, max(0.05, settings.range_edge_fraction))
        if position <= edge:
            zone = PdfRangeZone.LOWER_EDGE
        elif position >= 1.0 - edge:
            zone = PdfRangeZone.UPPER_EDGE
        else:
            zone = PdfRangeZone.MIDDLE

    tolerance = max(atr * settings.touch_tolerance_atr, width * 0.01)
    lower_touches = sum(abs(bar.low - range_low) <= tolerance for bar in prior)
    upper_touches = sum(abs(bar.high - range_high) <= tolerance for bar in prior)

    body_sample = [abs(bar.close - bar.open) for bar in prior[-max(2, settings.breakout_step_bars) :]]
    step_body = max(fmean(body_sample) if body_sample else atr, 1e-12)
    latest_body = abs(latest.close - latest.open)
    latest_range = max(latest.high - latest.low, 1e-12)
    large_body = latest_body >= settings.breakout_body_multiple * step_body

    if latest.high > range_high:
        beyond_fraction = max(0.0, latest.high - max(latest.low, range_high)) / latest_range
        valid = large_body and beyond_fraction > 0.50 and latest.close > range_high
        breakout = PdfBreakout.VALID_UP if valid else PdfBreakout.FAKE_UP
    elif latest.low < range_low:
        beyond_fraction = max(0.0, min(latest.high, range_low) - latest.low) / latest_range
        valid = large_body and beyond_fraction > 0.50 and latest.close < range_low
        breakout = PdfBreakout.VALID_DOWN if valid else PdfBreakout.FAKE_DOWN
    else:
        breakout = PdfBreakout.NONE

    return zone, breakout, lower_touches, upper_touches


def _prior_context_is_range(snapshot: MarketSnapshot, settings: PdfModeSettings) -> bool:
    """Return True only when the market before the latest bar was range-like.

    A rolling high in a healthy trend is not a range breakout. Breakout/fakeout
    rules from the PDF course are therefore actionable only when the completed
    bars immediately before the latest candle classify as RANGE.
    """

    if len(snapshot.bars) < max(settings.trend_lookback + 2, 20):
        return False
    prior_snapshot = snapshot.model_copy(update={"bars": snapshot.bars[:-1]})
    prior_atr = _atr(prior_snapshot)
    prior_regime, _, _ = _classify_regime(prior_snapshot, settings, prior_atr)
    return prior_regime == PdfRegime.RANGE


def evaluate_pdf_mode(
    snapshot: MarketSnapshot,
    candidate: Decision,
    settings: PdfModeSettings | None = None,
) -> PdfModeEvaluation:
    """Evaluate PDF workflow as a veto/confirmation layer only.

    It never creates BUY/SELL and never reverses an existing candidate. The
    ordinary six-factor engine still chooses direction; PDF Mode may only keep
    that direction or block it to WAIT.
    """

    settings = settings or PdfModeSettings()
    if len(snapshot.bars) < max(settings.range_lookback + 1, settings.trend_lookback + 1, 20):
        return PdfModeEvaluation(
            status="BLOCK" if candidate != Decision.WAIT else "OBSERVE",
            allowed=candidate == Decision.WAIT,
            reason="PDF mode: insufficient completed OHLC context." if candidate != Decision.WAIT else None,
            regime=PdfRegime.UNKNOWN,
            range_zone=PdfRangeZone.UNAVAILABLE,
            breakout=PdfBreakout.UNAVAILABLE,
            lower_touch_count=0,
            upper_touch_count=0,
            efficiency_ratio=0.0,
            net_move_atr=0.0,
        )

    atr = _atr(snapshot)
    regime, efficiency, net_move_atr = _classify_regime(snapshot, settings, atr)
    zone, breakout, lower_touches, upper_touches = _range_context(snapshot, settings, atr)
    breakout_context = _prior_context_is_range(snapshot, settings)

    allowed = True
    reason: str | None = None

    if candidate == Decision.SELL and regime in {PdfRegime.STRONG_UPTREND, PdfRegime.SPIKE_UP}:
        allowed = False
        reason = f"PDF trend priority blocked SELL against {regime.value}."
    elif candidate == Decision.BUY and regime in {PdfRegime.STRONG_DOWNTREND, PdfRegime.SPIKE_DOWN}:
        allowed = False
        reason = f"PDF trend priority blocked BUY against {regime.value}."
    elif breakout_context and breakout == PdfBreakout.VALID_UP and candidate == Decision.SELL:
        allowed = False
        reason = "PDF valid upside range breakout blocked SELL."
    elif breakout_context and breakout == PdfBreakout.VALID_DOWN and candidate == Decision.BUY:
        allowed = False
        reason = "PDF valid downside range breakout blocked BUY."
    elif breakout_context and breakout == PdfBreakout.FAKE_UP and candidate == Decision.BUY:
        allowed = False
        reason = "PDF fake upside range breakout blocked BUY."
    elif breakout_context and breakout == PdfBreakout.FAKE_DOWN and candidate == Decision.SELL:
        allowed = False
        reason = "PDF fake downside range breakout blocked SELL."
    elif regime == PdfRegime.RANGE and candidate != Decision.WAIT:
        if zone == PdfRangeZone.MIDDLE:
            allowed = False
            reason = "PDF range rule blocked entry in the middle of the range."
        elif candidate == Decision.BUY and zone != PdfRangeZone.LOWER_EDGE:
            allowed = False
            reason = "PDF range rule allows BUY only near the lower edge."
        elif candidate == Decision.SELL and zone != PdfRangeZone.UPPER_EDGE:
            allowed = False
            reason = "PDF range rule allows SELL only near the upper edge."

    status = "OBSERVE" if candidate == Decision.WAIT else ("CONFIRM" if allowed else "BLOCK")
    return PdfModeEvaluation(
        status=status,
        allowed=allowed,
        reason=reason,
        regime=regime,
        range_zone=zone,
        breakout=breakout,
        lower_touch_count=lower_touches,
        upper_touch_count=upper_touches,
        efficiency_ratio=efficiency,
        net_move_atr=net_move_atr,
    )