from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import meta_trader_ai.training as training
from meta_trader_ai.models import HistoryBar, StrategyConfig
from meta_trader_ai.training import TrainingRequest, train_thresholds


def make_days(count: int) -> list[HistoryBar]:
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    out: list[HistoryBar] = []
    for i in range(count):
        ts = start + timedelta(days=i)
        out.append(
            HistoryBar(
                time=int(ts.timestamp()),
                broker_date=ts.date().isoformat(),
                open=4400,
                high=4402,
                low=4398,
                close=4401,
                spread_points=20,
            )
        )
    return out


def fake_metrics(*, dates, config, starting_balance, **kwargs):
    # Deterministic synthetic objective: profiles around total_score=50 score best.
    distance = abs(config.decision.min_total_score - 50.0)
    objective = 1.0 - distance / 100.0
    trades = max(3, len(dates))
    expectancy = 0.25 - distance / 200.0
    pnl = len(dates) * expectancy * 2.0
    return {
        "trading_days": len(dates),
        "trades": trades,
        "signals": trades,
        "buy_trades": trades,
        "sell_trades": 0,
        "wins": trades,
        "losses": 0,
        "win_rate": 100.0,
        "net_r": expectancy * trades,
        "expectancy_r": expectancy,
        "avg_daily_r": expectancy,
        "max_drawdown_r": 0.5,
        "daily_r_std": 0.1,
        "profitable_days": len(dates),
        "profitable_days_percent": 100.0,
        "starting_balance": starting_balance,
        "ending_balance": starting_balance + pnl,
        "total_pnl": pnl,
        "avg_daily_pnl": pnl / len(dates),
        "objective": objective,
    }


def test_training_uses_chronological_60_20_20_split_and_preserves_safety(monkeypatch) -> None:
    monkeypatch.setattr(training, "_range_metrics", fake_metrics)
    history = make_days(20)
    base = StrategyConfig()
    request = TrainingRequest(
        start_date=history[0].broker_date,
        end_date=history[-1].broker_date,
        iterations=8,
    )

    result = train_thresholds(history=history, point=0.01, request=request, base_config=base)

    assert result["split"]["train_days"] == 12
    assert result["split"]["validation_days"] == 4
    assert result["split"]["holdout_days"] == 4
    candidate = StrategyConfig.model_validate(result["candidate"]["config"])
    assert candidate.safety == base.safety
    assert candidate.dynamic_levels.weight == base.dynamic_levels.weight
    assert result["candidates_evaluated"] >= 1


def test_training_requires_enough_trading_days() -> None:
    history = make_days(10)
    request = TrainingRequest(start_date=history[0].broker_date, end_date=history[-1].broker_date, iterations=8)
    with pytest.raises(ValueError, match="at least 15"):
        train_thresholds(history=history, point=0.01, request=request, base_config=StrategyConfig())
