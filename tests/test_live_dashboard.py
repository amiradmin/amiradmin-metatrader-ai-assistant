from meta_trader_ai.decision_engine import build_decision
from meta_trader_ai.live_page import live_page_html
from meta_trader_ai.live_state import LiveStateStore
from meta_trader_ai.models import Bar, LivePosition, MarketSnapshot, StrategyConfig


def _bars() -> list[Bar]:
    bars: list[Bar] = []
    price = 2000.0
    for i in range(60):
        close = price + 0.5
        bars.append(
            Bar(
                time=1_700_000_000 + i * 900,
                open=price,
                high=close + 0.2,
                low=price - 0.2,
                close=close,
                tick_volume=100 + i,
            )
        )
        price = close
    return bars


def test_live_page_is_zero_dependency_polling_dashboard() -> None:
    html = live_page_html()

    assert "AMIR META TRADER AI" in html
    assert "Live Trading Dashboard" in html
    assert "fetch('/live/data'" in html
    assert 'id="chart"' in html
    assert "EA-managed open positions" in html
    assert "MARKET UNKNOWN" in html
    assert "ALGO UNKNOWN" in html
    assert "setInterval(refresh,3000)" in html
    assert "https://" not in html


def test_live_state_keeps_latest_mt5_snapshot_and_decision() -> None:
    bars = _bars()
    snapshot = MarketSnapshot(
        symbol="XAUUSD_o",
        timeframe="M15",
        bid=2029.9,
        ask=2030.1,
        point=0.01,
        spread_points=20,
        bars=bars,
        live_bar=Bar(
            time=bars[-1].time + 900,
            open=2030.0,
            high=2030.5,
            low=2029.8,
            close=2030.3,
            tick_volume=12,
        ),
        news_risk="LOW",
        account_mode="DEMO",
        account_balance=1000.0,
        account_equity=1005.0,
        market_session_open=True,
        terminal_trade_allowed=True,
        mql_trade_allowed=True,
        positions=[
            LivePosition(
                ticket=123456,
                side="BUY",
                volume=0.01,
                price_open=2028.0,
                stop_loss=2020.0,
                take_profit=2044.0,
                current_price=2030.0,
                profit=2.0,
            )
        ],
    )
    decision = build_decision(snapshot, StrategyConfig())
    store = LiveStateStore()

    empty = store.payload()
    assert empty["bridge_online"] is False
    assert empty["snapshot"] is None

    store.update(snapshot, decision)
    payload = store.payload()

    assert payload["bridge_online"] is True
    live = payload["snapshot"]
    assert live["account_equity"] == 1005.0
    assert live["market_session_open"] is True
    assert live["terminal_trade_allowed"] is True
    assert live["live_bar"]["close"] == 2030.3
    assert live["positions"][0]["ticket"] == 123456
    assert payload["decision"]["symbol"] == "XAUUSD_o"
