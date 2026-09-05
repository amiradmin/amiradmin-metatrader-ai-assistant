from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from meta_trader_ai.backtest_date import ReplaySettings, run_date_backtest, run_range_backtest
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


def test_history_store_default_supports_multi_year_bar_counts(tmp_path) -> None:
    store = HistoryStore(root=tmp_path)
    assert store.max_bars >= 100_000


def test_history_store_prunes_oldest_only_when_cap_is_reached(tmp_path) -> None:
    store = HistoryStore(root=tmp_path, max_bars=10)
    bars = make_history()[:12]
    store.save(HistorySync(symbol="XAUUSD_o", timeframe="M15", point=0.01, bars=bars))
    loaded = store.load("XAUUSD_o", "M15")
    assert len(loaded) == 10
    assert loaded[0].time == bars[2].time
    assert loaded[-1].time == bars[-1].time


def test_history_store_migrates_legacy_json_without_losing_bars(tmp_path) -> None:
    bars = make_history()[:8]
    legacy = tmp_path / "XAUUSD_o_M15.json"
    legacy.write_text(
        json.dumps(
            {
                "symbol": "XAUUSD_o",
                "timeframe": "M15",
                "point": 0.01,
                "bars": [bar.model_dump(mode="json") for bar in bars],
            }
        ),
        encoding="utf-8",
    )

    store = HistoryStore(root=tmp_path)
    status = store.status("XAUUSD_o", "M15")

    assert status.bars == len(bars)
    assert store.point("XAUUSD_o", "M15") == 0.01
    assert not legacy.exists()
    assert (tmp_path / "XAUUSD_o_M15.json.migrated").exists()


def test_load_range_includes_indicator_preroll(tmp_path) -> None:
    store = HistoryStore(root=tmp_path)
    bars = make_history()
    store.save(HistorySync(symbol="XAUUSD_o", timeframe="M15", point=0.01, bars=bars))

    loaded = store.load_range(
        "XAUUSD_o",
        "M15",
        "2026-09-03",
        "2026-09-03",
        lookback_bars=20,
    )

    selected = [bar for bar in loaded if bar.broker_date == "2026-09-03"]
    preroll = [bar for bar in loaded if bar.broker_date < "2026-09-03"]
    assert selected
    assert len(preroll) == 20


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


def test_range_backtest_keeps_position_open_across_days() -> None:
    result = run_range_backtest(
        history=make_history(),
        point=0.01,
        start_date="2026-09-02",
        end_date="2026-09-04",
        symbol="XAUUSD_o",
        timeframe="M15",
        config=permissive_config(),
        settings=ReplaySettings(
            starting_balance=1000,
            risk_percent=0.5,
            reward_risk_ratio=2.0,
            min_stop_points=100_000,
            max_stop_points=100_000,
            max_open_trades=1,
        ),
    )

    assert result.trading_days == 3
    assert result.trades >= 1
    assert all(trade.outcome != "DAY_CLOSE" for trade in result.trades_detail)
    assert result.trades_detail[-1].outcome == "RANGE_CLOSE"
    assert result.trades_detail[-1].exit_time > result.trades_detail[-1].entry_time
    assert result.max_drawdown_percent >= 0
