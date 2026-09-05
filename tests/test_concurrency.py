from __future__ import annotations

from datetime import datetime, timedelta, timezone

from meta_trader_ai.backtest_date import ReplaySettings, run_date_backtest
from meta_trader_ai.models import HistoryBar, StrategyConfig
from meta_trader_ai.training import TrainingRequest


def _history() -> list[HistoryBar]:
    bars: list[HistoryBar] = []
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    price = 4400.0
    for i in range(96 * 3):
        ts = start + timedelta(minutes=15 * i)
        open_ = price
        close = open_ + 0.02
        bars.append(HistoryBar(
            time=int(ts.timestamp()),
            broker_date=ts.date().isoformat(),
            open=open_,
            high=close + 0.03,
            low=open_ - 0.03,
            close=close,
            spread_points=2,
        ))
        price = close
    return bars


def _permissive() -> StrategyConfig:
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


def test_backtest_can_accumulate_multiple_open_positions() -> None:
    common = dict(
        history=_history(),
        point=0.01,
        selected_date="2026-09-02",
        symbol="XAUUSD_o",
        timeframe="M15",
        config=_permissive(),
    )
    one = run_date_backtest(**common, settings=ReplaySettings(max_open_trades=1))
    five = run_date_backtest(**common, settings=ReplaySettings(max_open_trades=5))
    assert one.max_open_trades == 1
    assert five.max_open_trades == 5
    assert five.trades >= one.trades
    assert five.trades > 1


def test_training_request_carries_fixed_concurrency_scenario() -> None:
    req = TrainingRequest(start_date="2026-01-01", end_date="2026-09-01", max_open_trades=5)
    assert req.max_open_trades == 5
