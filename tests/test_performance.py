from datetime import datetime, timezone

from meta_trader_ai.models import TradeOutcome
from meta_trader_ai.performance import PerformanceStore


def test_expectancy_and_drawdown(tmp_path) -> None:
    store = PerformanceStore(tmp_path / "outcomes.jsonl")
    for i, r in enumerate([2.0, -1.0, 2.0, -1.0]):
        store.append(TradeOutcome(signal_id=f"s{i}", symbol="XAUUSD_o", side="BUY", pnl_money=r * 10, r_multiple=r, closed_at=datetime.now(timezone.utc)))
    summary = store.summary()
    assert summary.trades == 4
    assert summary.expectancy_r == 0.5
    assert summary.win_rate == 50.0
    assert summary.max_drawdown_r == 1.0
