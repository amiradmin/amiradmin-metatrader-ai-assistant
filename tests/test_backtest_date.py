from __future__ import annotations

from datetime import datetime, timedelta, timezone

from meta_trader_ai.backtest_date import ReplaySettings, run_date_backtest
from meta_trader_ai.history import HistoryStore
from meta_trader_ai.models import HistoryBar, HistorySync, StrategyConfig


def make_history() -> list[HistoryBar]:
    bars: list[HistoryBar] = []
    start = datetime(2026, 9, 2, 0, 0, tzinfo=timezone.utc)
    price = 4400.0
    for i in range(240):
        ts = start + timedelta(minutes=15 * i)
        step = 0.8 if i % 9 else -0.3
        open_ = price
        close = price + step
        high = max(open_, close) + 0.6
        low = min(open_, close) - 0.6
        bars.append(
            HistoryBar(
                time=int(ts.timestamp()),
                broker_date=ts.date().isoformat(),
                open=open_,
                high=high,
                low=low,
                close=close,
                spread_points=20,
            )
        )
        price = close
    return bars


def permissive_config() -> StrategyConfig:
    cfg = StrategyConfig()
    for name in ("dynamic_levels", "static_levels", "fibonacci", "patterns", "pivots", "divergence"):
        factor = getattr(cfg, name)
        factor.min_score = 0
        factor.required = False
    cfg.decision.min_pass_count = 1
    cfg.decision.min_total_score = 0
    cfg.decision.min_side_edge = 0
    cfg.safety.max_spread_points = 100
    return cfg


def test_history_store_merges_by_timestamp(tmp_path) -> None:
    store = HistoryStore(root=tmp_path)
    bars = make_history()
    first = HistorySync(symbol="XAUUSD_o", timeframe="M15", point=0.01, bars=bars[:100])
    second = HistorySync(symbol="XAUUSD_o", timeframe="M15", point=0.01, bars=bars[80:])
    store.save(first)
    status = store.save(second)
    assert status.bars == len(bars)
    assert status.earliest_date == "2026-09-02"
    assert status.latest_date == "2026-09-04"


def test_date_backtest_returns_trade_summary() -> None:
    result = run_date_backtest(
        history=make_history(),
        point=0.01,
        selected_date="2026-09-03",
        symbol="XAUUSD_o",
        timeframe="M15",
        config=permissive_config(),
        settings=ReplaySettings(starting_balance=1000, risk_percent=0.5, reward_risk_ratio=2.0),
    )
    assert result.bars_available > 0
    assert result.evaluated_bars > 0
    assert result.signals >= result.trades
    assert result.trades == result.buy_trades + result.sell_trades
    assert result.ending_balance == round(result.starting_balance + result.estimated_pnl_money, 2)
