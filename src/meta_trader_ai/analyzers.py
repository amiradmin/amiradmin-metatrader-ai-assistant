from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .models import FactorName, MarketSnapshot


@dataclass(frozen=True)
class RawFactorScore:
    name: FactorName
    label: str
    buy: float
    sell: float
    buy_reason: str
    sell_reason: str


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    out = [values[0]]
    for value in values[1:]:
        out.append(alpha * value + (1.0 - alpha) * out[-1])
    return out


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float:
    if len(closes) < 2:
        return 0.0
    trs: list[float] = []
    for i in range(1, len(closes)):
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    return sum(trs[-period:]) / min(period, len(trs)) if trs else 0.0


def rsi(values: list[float], period: int = 14) -> list[float]:
    if len(values) < 2:
        return [50.0] * len(values)
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(values)):
        delta = values[i] - values[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    result = [50.0] * len(values)
    for i in range(period, len(values)):
        avg_gain = sum(gains[i - period + 1 : i + 1]) / period
        avg_loss = sum(losses[i - period + 1 : i + 1]) / period
        if avg_loss == 0:
            result[i] = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - 100.0 / (1.0 + rs)
    return result


def _series(snapshot: MarketSnapshot) -> tuple[list[float], list[float], list[float], list[float]]:
    bars = sorted(snapshot.bars, key=lambda b: b.time)
    return [b.open for b in bars], [b.high for b in bars], [b.low for b in bars], [b.close for b in bars]


def dynamic_levels(snapshot: MarketSnapshot) -> RawFactorScore:
    _, highs, lows, closes = _series(snapshot)
    e20 = ema(closes, 20)
    e50 = ema(closes, 50)
    a = max(atr(highs, lows, closes), snapshot.point * 10)
    price = closes[-1]
    slope = (e20[-1] - e20[-6]) / a if len(e20) >= 6 else 0.0
    distance = abs(price - e20[-1]) / a
    buy = 20.0
    sell = 20.0
    if e20[-1] > e50[-1]: buy += 35
    else: sell += 35
    if slope > 0.08: buy += min(25.0, 10.0 + slope * 15.0)
    elif slope < -0.08: sell += min(25.0, 10.0 + abs(slope) * 15.0)
    if distance <= 0.55:
        if price >= e20[-1]: buy += 20
        else: sell += 20
    elif distance > 1.8:
        buy -= 8; sell -= 8
    return RawFactorScore(FactorName.DYNAMIC, "Dynamic levels", clamp(buy), clamp(sell), f"EMA20 {'above' if e20[-1] > e50[-1] else 'below'} EMA50; slope={slope:+.2f} ATR; price/EMA20={distance:.2f} ATR", f"EMA20 {'below' if e20[-1] < e50[-1] else 'above'} EMA50; slope={slope:+.2f} ATR; price/EMA20={distance:.2f} ATR")


def static_levels(snapshot: MarketSnapshot) -> RawFactorScore:
    opens, highs, lows, closes = _series(snapshot)
    a = max(atr(highs, lows, closes), snapshot.point * 10)
    price = closes[-1]
    lookback = min(45, len(closes) - 2)
    support = min(lows[-lookback - 1 : -1])
    resistance = max(highs[-lookback - 1 : -1])
    d_support = abs(price - support) / a
    d_res = abs(resistance - price) / a
    buy = 25.0 + max(0.0, 35.0 - d_support * 18.0)
    sell = 25.0 + max(0.0, 35.0 - d_res * 18.0)
    impulse_buy = False
    impulse_sell = False
    for i in range(max(1, len(closes) - 14), len(closes) - 1):
        body = abs(closes[i] - opens[i])
        next_body = abs(closes[i + 1] - opens[i + 1])
        if closes[i] < opens[i] and closes[i + 1] > opens[i + 1] and next_body > body * 1.5:
            if lows[i] - 0.25 * a <= price <= opens[i] + 0.75 * a: impulse_buy = True
        if closes[i] > opens[i] and closes[i + 1] < opens[i + 1] and next_body > body * 1.5:
            if opens[i] - 0.75 * a <= price <= highs[i] + 0.25 * a: impulse_sell = True
    if impulse_buy: buy += 25
    if impulse_sell: sell += 25
    return RawFactorScore(FactorName.STATIC, "Static / order block", clamp(buy), clamp(sell), f"support distance={d_support:.2f} ATR; bullish OB proxy={'yes' if impulse_buy else 'no'}", f"resistance distance={d_res:.2f} ATR; bearish OB proxy={'yes' if impulse_sell else 'no'}")


def fibonacci(snapshot: MarketSnapshot) -> RawFactorScore:
    _, highs, lows, closes = _series(snapshot)
    window = min(60, len(closes))
    hh = max(highs[-window:]); ll = min(lows[-window:])
    span = max(hh - ll, snapshot.point * 10)
    price = closes[-1]
    e20 = ema(closes, 20)[-1]; e50 = ema(closes, 50)[-1]
    ratios = (0.382, 0.5, 0.618)
    if e20 >= e50:
        levels = [hh - span * r for r in ratios]
        proximity = min(abs(price - level) / span for level in levels)
        buy = 30 + max(0.0, 55.0 - proximity * 500.0)
        sell = 25 + max(0.0, 20.0 - abs(price - hh) / span * 60.0)
        reason_buy = f"uptrend retracement proximity={proximity:.3f} of swing range"
        reason_sell = f"countertrend; distance from swing high={abs(price-hh)/span:.3f}"
    else:
        levels = [ll + span * r for r in ratios]
        proximity = min(abs(price - level) / span for level in levels)
        sell = 30 + max(0.0, 55.0 - proximity * 500.0)
        buy = 25 + max(0.0, 20.0 - abs(price - ll) / span * 60.0)
        reason_sell = f"downtrend retracement proximity={proximity:.3f} of swing range"
        reason_buy = f"countertrend; distance from swing low={abs(price-ll)/span:.3f}"
    return RawFactorScore(FactorName.FIBONACCI, "Fibonacci", clamp(buy), clamp(sell), reason_buy, reason_sell)


def _turning_points(closes: list[float], radius: int = 2) -> list[tuple[int, float]]:
    points: list[tuple[int, float]] = []
    for i in range(radius, len(closes) - radius):
        chunk = closes[i - radius : i + radius + 1]
        if closes[i] == max(chunk) or closes[i] == min(chunk): points.append((i, closes[i]))
    return points


def patterns(snapshot: MarketSnapshot) -> RawFactorScore:
    opens, highs, lows, closes = _series(snapshot)
    b0 = len(closes) - 1; b1 = len(closes) - 2
    buy = 25.0; sell = 25.0
    reasons_buy: list[str] = []; reasons_sell: list[str] = []
    bullish_engulf = closes[b0] > opens[b0] and closes[b1] < opens[b1] and closes[b0] >= opens[b1] and opens[b0] <= closes[b1]
    bearish_engulf = closes[b0] < opens[b0] and closes[b1] > opens[b1] and opens[b0] >= closes[b1] and closes[b0] <= opens[b1]
    body = max(abs(closes[b0] - opens[b0]), snapshot.point)
    lower_wick = min(opens[b0], closes[b0]) - lows[b0]
    upper_wick = highs[b0] - max(opens[b0], closes[b0])
    bullish_pin = lower_wick >= body * 2.0 and upper_wick <= body
    bearish_pin = upper_wick >= body * 2.0 and lower_wick <= body
    if bullish_engulf: buy += 35; reasons_buy.append("bullish engulfing")
    if bearish_engulf: sell += 35; reasons_sell.append("bearish engulfing")
    if bullish_pin: buy += 25; reasons_buy.append("bullish pin/rejection")
    if bearish_pin: sell += 25; reasons_sell.append("bearish pin/rejection")
    turns = _turning_points(closes[-50:])
    if len(turns) >= 4:
        vals = [p[1] for p in turns[-4:]]
        ab = vals[1] - vals[0]; cd = vals[3] - vals[2]
        if abs(ab) > snapshot.point and abs(abs(cd / ab) - 1.0) <= 0.25:
            if cd > 0: buy += 18; reasons_buy.append("AB=CD symmetry")
            else: sell += 18; reasons_sell.append("AB=CD symmetry")
    return RawFactorScore(FactorName.PATTERNS, "Patterns / harmonic", clamp(buy), clamp(sell), ", ".join(reasons_buy) or "no strong bullish pattern", ", ".join(reasons_sell) or "no strong bearish pattern")


def pivots(snapshot: MarketSnapshot) -> RawFactorScore:
    _, highs, lows, closes = _series(snapshot)
    if snapshot.previous_day is not None:
        h, l, c = snapshot.previous_day.high, snapshot.previous_day.low, snapshot.previous_day.close
    else:
        window = min(96, len(closes) - 1)
        h, l, c = max(highs[-window - 1 : -1]), min(lows[-window - 1 : -1]), closes[-2]
    p = (h + l + c) / 3.0; r1 = 2.0 * p - l; s1 = 2.0 * p - h
    range_ = max(h - l, snapshot.point * 10); price = closes[-1]
    near_p = abs(price - p) / range_; near_s1 = abs(price - s1) / range_; near_r1 = abs(price - r1) / range_
    buy = 25.0; sell = 25.0
    if price >= p: buy += 20
    else: sell += 20
    buy += max(0.0, 35.0 - near_s1 * 180.0)
    sell += max(0.0, 35.0 - near_r1 * 180.0)
    if near_p < 0.05:
        buy += 8 if closes[-1] > closes[-2] else 0
        sell += 8 if closes[-1] < closes[-2] else 0
    return RawFactorScore(FactorName.PIVOTS, "Pivots", clamp(buy), clamp(sell), f"price {'above' if price >= p else 'below'} pivot; S1 distance={near_s1:.3f}", f"price {'below' if price < p else 'above'} pivot; R1 distance={near_r1:.3f}")


def divergence(snapshot: MarketSnapshot) -> RawFactorScore:
    _, highs, lows, closes = _series(snapshot)
    rsis = rsi(closes, 14); current_rsi = rsis[-1]
    buy = 25.0; sell = 25.0
    reasons_buy = [f"RSI={current_rsi:.1f}"]; reasons_sell = [f"RSI={current_rsi:.1f}"]
    if current_rsi <= 35: buy += 30
    elif current_rsi >= 65: sell += 30
    elif current_rsi > 55: buy += 10
    elif current_rsi < 45: sell += 10
    turns_low: list[int] = []; turns_high: list[int] = []
    start = max(2, len(closes) - 40)
    for i in range(start, len(closes) - 2):
        if lows[i] < lows[i - 1] and lows[i] <= lows[i + 1]: turns_low.append(i)
        if highs[i] > highs[i - 1] and highs[i] >= highs[i + 1]: turns_high.append(i)
    if len(turns_low) >= 2:
        a, b = turns_low[-2], turns_low[-1]
        if lows[b] < lows[a] and rsis[b] > rsis[a] + 2: buy += 35; reasons_buy.append("bullish RSI divergence")
    if len(turns_high) >= 2:
        a, b = turns_high[-2], turns_high[-1]
        if highs[b] > highs[a] and rsis[b] < rsis[a] - 2: sell += 35; reasons_sell.append("bearish RSI divergence")
    fast = ema(closes, 12); slow = ema(closes, 26)
    macd = [f - s for f, s in zip(fast, slow)]; signal = ema(macd, 9)
    hist = macd[-1] - signal[-1]; scale = max(atr(highs, lows, closes), snapshot.point * 10); hist_n = hist / scale
    if hist_n > 0.02: buy += min(15, hist_n * 80)
    elif hist_n < -0.02: sell += min(15, abs(hist_n) * 80)
    reasons_buy.append(f"MACD hist={hist_n:+.3f} ATR"); reasons_sell.append(f"MACD hist={hist_n:+.3f} ATR")
    buy = clamp(buy if isfinite(buy) else 0.0); sell = clamp(sell if isfinite(sell) else 0.0)
    return RawFactorScore(FactorName.DIVERGENCE, "Divergence / momentum", buy, sell, "; ".join(reasons_buy), "; ".join(reasons_sell))


def analyze_all(snapshot: MarketSnapshot) -> list[RawFactorScore]:
    return [dynamic_levels(snapshot), static_levels(snapshot), fibonacci(snapshot), patterns(snapshot), pivots(snapshot), divergence(snapshot)]
