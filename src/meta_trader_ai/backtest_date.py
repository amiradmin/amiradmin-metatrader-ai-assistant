from __future__ import annotations

from dataclasses import dataclass

from .analyzers import atr
from .decision_engine import build_decision
from .models import (
    BacktestSummary,
    BacktestTrade,
    Bar,
    DailyContext,
    Decision,
    HistoryBar,
    MarketSnapshot,
    StrategyConfig,
)


@dataclass(frozen=True)
class ReplaySettings:
    starting_balance: float = 1000.0
    risk_percent: float = 0.5
    reward_risk_ratio: float = 2.0
    atr_multiplier: float = 1.5
    min_stop_points: int = 150
    max_stop_points: int = 1200
    lookback_bars: int = 120


def _previous_day_context(history: list[HistoryBar], selected_date: str) -> DailyContext | None:
    prior_dates = sorted({bar.broker_date for bar in history if bar.broker_date < selected_date})
    if not prior_dates:
        return None
    day = prior_dates[-1]
    bars = [bar for bar in history if bar.broker_date == day]
    if not bars:
        return None
    bars.sort(key=lambda bar: bar.time)
    return DailyContext(high=max(bar.high for bar in bars), low=min(bar.low for bar in bars), close=bars[-1].close)


def _snapshot(history: list[HistoryBar], index: int, point: float, previous_day: DailyContext | None) -> MarketSnapshot | None:
    start = max(0, index - 119)
    window = history[start : index + 1]
    if len(window) < 60:
        return None
    last = window[-1]
    spread = max(0, last.spread_points)
    bid = last.close
    ask = bid + spread * point
    return MarketSnapshot(
        symbol="",
        timeframe="M15",
        bid=bid,
        ask=max(ask, bid + point),
        point=point,
        spread_points=spread,
        bars=[Bar(time=b.time, open=b.open, high=b.high, low=b.low, close=b.close) for b in window],
        previous_day=previous_day,
        news_risk="UNKNOWN",
        account_mode="DEMO",
    )


def _trade_exit(
    history: list[HistoryBar],
    entry_index: int,
    last_day_index: int,
    side: str,
    entry: float,
    stop: float,
    target: float,
    point: float,
) -> tuple[int, float, str, float]:
    stop_distance = abs(entry - stop)
    for j in range(entry_index, last_day_index + 1):
        bar = history[j]
        spread = max(0, bar.spread_points) * point
        if side == "BUY":
            stop_hit = bar.low <= stop
            target_hit = bar.high >= target
            if stop_hit and target_hit:
                return j, stop, "SL", -1.0
            if stop_hit:
                return j, stop, "SL", -1.0
            if target_hit:
                return j, target, "TP", abs(target - entry) / stop_distance
        else:
            ask_high = bar.high + spread
            ask_low = bar.low + spread
            stop_hit = ask_high >= stop
            target_hit = ask_low <= target
            if stop_hit and target_hit:
                return j, stop, "SL", -1.0
            if stop_hit:
                return j, stop, "SL", -1.0
            if target_hit:
                return j, target, "TP", abs(entry - target) / stop_distance

    final_bar = history[last_day_index]
    final_price = final_bar.close if side == "BUY" else final_bar.close + max(0, final_bar.spread_points) * point
    raw_r = (final_price - entry) / stop_distance if side == "BUY" else (entry - final_price) / stop_distance
    return last_day_index, final_price, "DAY_CLOSE", raw_r


def run_date_backtest(
    *,
    history: list[HistoryBar],
    point: float,
    selected_date: str,
    symbol: str,
    timeframe: str,
    config: StrategyConfig,
    settings: ReplaySettings,
) -> BacktestSummary:
    bars = sorted(history, key=lambda bar: bar.time)
    day_indices = [i for i, bar in enumerate(bars) if bar.broker_date == selected_date]
    if not day_indices:
        raise ValueError(f"No synced bars for {selected_date}")

    first_day_index = day_indices[0]
    last_day_index = day_indices[-1]
    previous_day = _previous_day_context(bars, selected_date)

    balance = settings.starting_balance
    start_balance = balance
    cumulative_r = 0.0
    peak_r = 0.0
    max_drawdown_r = 0.0
    trades: list[BacktestTrade] = []
    evaluated = 0
    buy_signals = 0
    sell_signals = 0
    signal_count = 0
    blocked_until = first_day_index - 1

    i = first_day_index
    while i <= last_day_index:
        snap = _snapshot(bars, i, point, previous_day)
        if snap is None:
            i += 1
            continue
        snap.symbol = symbol
        snap.timeframe = timeframe
        evaluated += 1
        decision = build_decision(snap, config)
        if decision.decision == Decision.BUY:
            buy_signals += 1
            signal_count += 1
        elif decision.decision == Decision.SELL:
            sell_signals += 1
            signal_count += 1

        if i <= blocked_until or not decision.trade_allowed or decision.decision not in (Decision.BUY, Decision.SELL):
            i += 1
            continue
        if i + 1 > last_day_index:
            break

        side = decision.decision.value
        entry_index = i + 1
        entry_bar = bars[entry_index]
        spread = max(0, entry_bar.spread_points) * point
        entry = entry_bar.open + spread if side == "BUY" else entry_bar.open

        window = bars[max(0, i - settings.lookback_bars + 1) : i + 1]
        highs = [bar.high for bar in window]
        lows = [bar.low for bar in window]
        closes = [bar.close for bar in window]
        atr_value = atr(highs, lows, closes, 14)
        stop_points = max(float(settings.min_stop_points), atr_value * settings.atr_multiplier / point)
        if settings.max_stop_points > 0:
            stop_points = min(stop_points, float(settings.max_stop_points))
        stop_distance = max(stop_points * point, point)
        if side == "BUY":
            stop = entry - stop_distance
            target = entry + stop_distance * settings.reward_risk_ratio
        else:
            stop = entry + stop_distance
            target = entry - stop_distance * settings.reward_risk_ratio

        exit_index, exit_price, outcome, r_multiple = _trade_exit(
            bars, entry_index, last_day_index, side, entry, stop, target, point
        )
        risk_money = balance * settings.risk_percent / 100.0
        pnl_money = risk_money * r_multiple
        balance += pnl_money
        cumulative_r += r_multiple
        peak_r = max(peak_r, cumulative_r)
        max_drawdown_r = max(max_drawdown_r, peak_r - cumulative_r)

        trades.append(
            BacktestTrade(
                signal_time=bars[i].time,
                entry_time=entry_bar.time,
                exit_time=bars[exit_index].time,
                side=side,
                entry=round(entry, 6),
                stop=round(stop, 6),
                target=round(target, 6),
                exit=round(exit_price, 6),
                outcome=outcome,
                r_multiple=round(r_multiple, 4),
                pnl_money=round(pnl_money, 2),
                buy_score=decision.buy_score,
                sell_score=decision.sell_score,
                passed_count=decision.passed_count,
            )
        )
        blocked_until = exit_index
        i = max(i + 1, exit_index + 1)

    r_values = [trade.r_multiple for trade in trades]
    wins = sum(1 for value in r_values if value > 0)
    losses = sum(1 for value in r_values if value < 0)
    flat = sum(1 for value in r_values if value == 0)
    trade_count = len(trades)
    net_r = sum(r_values)
    expectancy = net_r / trade_count if trade_count else 0.0
    win_rate = wins / trade_count * 100.0 if trade_count else 0.0

    return BacktestSummary(
        date=selected_date,
        symbol=symbol,
        timeframe=timeframe,
        bars_available=len(day_indices),
        evaluated_bars=evaluated,
        signals=signal_count,
        buy_signals=buy_signals,
        sell_signals=sell_signals,
        trades=trade_count,
        buy_trades=sum(1 for trade in trades if trade.side == "BUY"),
        sell_trades=sum(1 for trade in trades if trade.side == "SELL"),
        wins=wins,
        losses=losses,
        flat=flat,
        win_rate=round(win_rate, 2),
        expectancy_r=round(expectancy, 4),
        net_r=round(net_r, 4),
        max_drawdown_r=round(max_drawdown_r, 4),
        estimated_pnl_money=round(balance - start_balance, 2),
        starting_balance=round(start_balance, 2),
        ending_balance=round(balance, 2),
        risk_percent=settings.risk_percent,
        reward_risk_ratio=settings.reward_risk_ratio,
        trades_detail=trades,
    )
