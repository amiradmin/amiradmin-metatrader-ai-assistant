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
    RangeBacktestSummary,
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
    max_open_trades: int = 1


@dataclass
class _PendingTrade:
    exit_index: int
    risk_money: float
    trade: BacktestTrade


def _previous_day_context(history: list[HistoryBar], selected_date: str) -> DailyContext | None:
    return _previous_day_contexts(history).get(selected_date)


def _previous_day_contexts(history: list[HistoryBar]) -> dict[str, DailyContext]:
    """Return the prior available broker-day OHLC context for every date.

    The context follows trading days rather than calendar days, so Monday uses
    Friday when the broker has no weekend bars. This matters for pivot parity in
    a continuous multi-day replay.
    """
    by_date: dict[str, list[HistoryBar]] = {}
    for bar in history:
        by_date.setdefault(bar.broker_date, []).append(bar)

    dates = sorted(by_date)
    contexts: dict[str, DailyContext] = {}
    for index in range(1, len(dates)):
        previous = sorted(by_date[dates[index - 1]], key=lambda bar: bar.time)
        if not previous:
            continue
        contexts[dates[index]] = DailyContext(
            high=max(bar.high for bar in previous),
            low=min(bar.low for bar in previous),
            close=previous[-1].close,
        )
    return contexts


def _snapshot(
    history: list[HistoryBar],
    index: int,
    point: float,
    previous_day: DailyContext | None,
) -> MarketSnapshot | None:
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
    last_index: int,
    side: str,
    entry: float,
    stop: float,
    target: float,
    point: float,
    final_outcome: str = "DAY_CLOSE",
) -> tuple[int, float, str, float]:
    """Find the first future SL/TP hit without using that future in decisions.

    When both SL and TP are inside the same M15 candle, the conservative rule is
    SL first because intrabar ordering is unknown from OHLC alone.
    """
    stop_distance = abs(entry - stop)
    for j in range(entry_index, last_index + 1):
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

    final_bar = history[last_index]
    final_price = (
        final_bar.close
        if side == "BUY"
        else final_bar.close + max(0, final_bar.spread_points) * point
    )
    raw_r = (
        (final_price - entry) / stop_distance
        if side == "BUY"
        else (entry - final_price) / stop_distance
    )
    return last_index, final_price, final_outcome, raw_r


def _mark_to_market_r(
    pending: _PendingTrade,
    bar: HistoryBar,
    point: float,
) -> float:
    trade = pending.trade
    stop_distance = max(abs(trade.entry - trade.stop), point)
    if trade.side == "BUY":
        return (bar.close - trade.entry) / stop_distance
    ask_close = bar.close + max(0, bar.spread_points) * point
    return (trade.entry - ask_close) / stop_distance


def _run_window(
    *,
    history: list[HistoryBar],
    point: float,
    start_date: str,
    end_date: str,
    symbol: str,
    timeframe: str,
    config: StrategyConfig,
    settings: ReplaySettings,
    final_outcome: str,
) -> dict[str, object]:
    if not 1 <= settings.max_open_trades <= 5:
        raise ValueError("max_open_trades must be between 1 and 5")
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")

    bars = sorted(history, key=lambda bar: bar.time)
    selected_indices = [
        i for i, bar in enumerate(bars) if start_date <= bar.broker_date <= end_date
    ]
    if not selected_indices:
        raise ValueError(f"No synced bars for {start_date} to {end_date}")

    first_index = selected_indices[0]
    last_index = selected_indices[-1]
    selected_dates = sorted(
        {bar.broker_date for bar in bars[first_index : last_index + 1]}
    )
    previous_days = _previous_day_contexts(bars)

    balance = settings.starting_balance
    start_balance = balance
    peak_equity = start_balance
    max_drawdown_percent = 0.0
    open_trades: list[_PendingTrade] = []
    closed_trades: list[BacktestTrade] = []
    evaluated = 0
    buy_signals = 0
    sell_signals = 0
    signal_count = 0

    def settle_through(index: int) -> None:
        nonlocal balance, open_trades
        due = sorted(
            (pending for pending in open_trades if pending.exit_index <= index),
            key=lambda pending: (pending.exit_index, pending.trade.entry_time),
        )
        if not due:
            return
        due_ids = {id(pending) for pending in due}
        open_trades = [pending for pending in open_trades if id(pending) not in due_ids]
        for pending in due:
            balance += pending.trade.pnl_money
            closed_trades.append(pending.trade)

    def update_equity_drawdown(index: int) -> None:
        nonlocal peak_equity, max_drawdown_percent
        bar = bars[index]
        unrealized = sum(
            pending.risk_money * _mark_to_market_r(pending, bar, point)
            for pending in open_trades
        )
        equity = balance + unrealized
        peak_equity = max(peak_equity, equity)
        if peak_equity > 0:
            max_drawdown_percent = max(
                max_drawdown_percent,
                (peak_equity - equity) / peak_equity * 100.0,
            )

    for i in range(first_index, last_index + 1):
        # Trades created from the previous completed bar enter on this bar's
        # open and may finish during this bar. Settle them before the close-bar
        # decision, then mark the remaining positions to market at this close.
        settle_through(i)
        update_equity_drawdown(i)

        previous_day = previous_days.get(bars[i].broker_date)
        snap = _snapshot(bars, i, point, previous_day)
        if snap is None:
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

        if not decision.trade_allowed or decision.decision not in (
            Decision.BUY,
            Decision.SELL,
        ):
            continue
        if len(open_trades) >= settings.max_open_trades:
            continue
        if i + 1 > last_index:
            continue

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
        stop_points = max(
            float(settings.min_stop_points),
            atr_value * settings.atr_multiplier / point,
        )
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
            bars,
            entry_index,
            last_index,
            side,
            entry,
            stop,
            target,
            point,
            final_outcome=final_outcome,
        )

        # Risk is fixed at entry from realized balance. This avoids using future
        # unrealized equity to size a trade and matches the deterministic replay
        # policy used by the existing daily backtester.
        risk_money = balance * settings.risk_percent / 100.0
        pnl_money = risk_money * r_multiple
        trade = BacktestTrade(
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
        open_trades.append(
            _PendingTrade(
                exit_index=exit_index,
                risk_money=risk_money,
                trade=trade,
            )
        )

    settle_through(last_index)
    # Include the final realized balance in the percentage drawdown series.
    peak_equity = max(peak_equity, balance)
    if peak_equity > 0:
        max_drawdown_percent = max(
            max_drawdown_percent,
            (peak_equity - balance) / peak_equity * 100.0,
        )

    trades = sorted(closed_trades, key=lambda trade: (trade.entry_time, trade.exit_time))
    exit_order = sorted(
        closed_trades, key=lambda trade: (trade.exit_time, trade.entry_time)
    )

    cumulative_r = 0.0
    peak_r = 0.0
    max_drawdown_r = 0.0
    for trade in exit_order:
        cumulative_r += trade.r_multiple
        peak_r = max(peak_r, cumulative_r)
        max_drawdown_r = max(max_drawdown_r, peak_r - cumulative_r)

    r_values = [trade.r_multiple for trade in trades]
    wins = sum(1 for value in r_values if value > 0)
    losses = sum(1 for value in r_values if value < 0)
    flat = sum(1 for value in r_values if value == 0)
    trade_count = len(trades)
    net_r = sum(r_values)
    expectancy = net_r / trade_count if trade_count else 0.0
    win_rate = wins / trade_count * 100.0 if trade_count else 0.0

    gross_profit = sum(trade.pnl_money for trade in trades if trade.pnl_money > 0)
    gross_loss = abs(sum(trade.pnl_money for trade in trades if trade.pnl_money < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
    pnl_money = balance - start_balance
    total_return = pnl_money / start_balance * 100.0 if start_balance else 0.0

    return {
        "start_date": start_date,
        "end_date": end_date,
        "selected_dates": selected_dates,
        "bars_available": len(selected_indices),
        "evaluated_bars": evaluated,
        "signals": signal_count,
        "buy_signals": buy_signals,
        "sell_signals": sell_signals,
        "trades": trades,
        "trade_count": trade_count,
        "buy_trades": sum(1 for trade in trades if trade.side == "BUY"),
        "sell_trades": sum(1 for trade in trades if trade.side == "SELL"),
        "wins": wins,
        "losses": losses,
        "flat": flat,
        "win_rate": win_rate,
        "expectancy_r": expectancy,
        "net_r": net_r,
        "profit_factor": profit_factor,
        "max_drawdown_r": max_drawdown_r,
        "max_drawdown_percent": max_drawdown_percent,
        "pnl_money": pnl_money,
        "total_return_percent": total_return,
        "starting_balance": start_balance,
        "ending_balance": balance,
    }


def run_range_backtest(
    *,
    history: list[HistoryBar],
    point: float,
    start_date: str,
    end_date: str,
    symbol: str,
    timeframe: str,
    config: StrategyConfig,
    settings: ReplaySettings,
) -> RangeBacktestSummary:
    """Replay one continuous range; positions are not closed at midnight."""
    result = _run_window(
        history=history,
        point=point,
        start_date=start_date,
        end_date=end_date,
        symbol=symbol,
        timeframe=timeframe,
        config=config,
        settings=settings,
        final_outcome="RANGE_CLOSE",
    )
    return RangeBacktestSummary(
        start_date=start_date,
        end_date=end_date,
        symbol=symbol,
        timeframe=timeframe,
        trading_days=len(result["selected_dates"]),
        bars_available=result["bars_available"],
        evaluated_bars=result["evaluated_bars"],
        signals=result["signals"],
        buy_signals=result["buy_signals"],
        sell_signals=result["sell_signals"],
        trades=result["trade_count"],
        buy_trades=result["buy_trades"],
        sell_trades=result["sell_trades"],
        wins=result["wins"],
        losses=result["losses"],
        flat=result["flat"],
        win_rate=round(result["win_rate"], 2),
        expectancy_r=round(result["expectancy_r"], 4),
        net_r=round(result["net_r"], 4),
        profit_factor=(
            round(result["profit_factor"], 4)
            if result["profit_factor"] is not None
            else None
        ),
        max_drawdown_r=round(result["max_drawdown_r"], 4),
        max_drawdown_percent=round(result["max_drawdown_percent"], 4),
        estimated_pnl_money=round(result["pnl_money"], 2),
        total_return_percent=round(result["total_return_percent"], 4),
        starting_balance=round(result["starting_balance"], 2),
        ending_balance=round(result["ending_balance"], 2),
        risk_percent=settings.risk_percent,
        reward_risk_ratio=settings.reward_risk_ratio,
        max_open_trades=settings.max_open_trades,
        trades_detail=result["trades"],
    )


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
    result = _run_window(
        history=history,
        point=point,
        start_date=selected_date,
        end_date=selected_date,
        symbol=symbol,
        timeframe=timeframe,
        config=config,
        settings=settings,
        final_outcome="DAY_CLOSE",
    )
    return BacktestSummary(
        date=selected_date,
        symbol=symbol,
        timeframe=timeframe,
        bars_available=result["bars_available"],
        evaluated_bars=result["evaluated_bars"],
        signals=result["signals"],
        buy_signals=result["buy_signals"],
        sell_signals=result["sell_signals"],
        trades=result["trade_count"],
        buy_trades=result["buy_trades"],
        sell_trades=result["sell_trades"],
        wins=result["wins"],
        losses=result["losses"],
        flat=result["flat"],
        win_rate=round(result["win_rate"], 2),
        expectancy_r=round(result["expectancy_r"], 4),
        net_r=round(result["net_r"], 4),
        max_drawdown_r=round(result["max_drawdown_r"], 4),
        estimated_pnl_money=round(result["pnl_money"], 2),
        starting_balance=round(result["starting_balance"], 2),
        ending_balance=round(result["ending_balance"], 2),
        risk_percent=settings.risk_percent,
        reward_risk_ratio=settings.reward_risk_ratio,
        max_open_trades=settings.max_open_trades,
        trades_detail=result["trades"],
    )
