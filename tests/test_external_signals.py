from meta_trader_ai.external_signals import ExternalSignalHub
from meta_trader_ai.models import Bar, MarketSnapshot, StrategyConfig


def snapshot_with_volume() -> MarketSnapshot:
    bars = []
    price = 2000.0
    for i in range(80):
        o = price
        c = o + (0.8 if i % 4 else -0.25)
        bars.append(
            Bar(
                time=1_700_000_000 + i * 900,
                open=o,
                high=max(o, c) + 0.4,
                low=min(o, c) - 0.4,
                close=c,
                tick_volume=100 + i,
            )
        )
        price = c
    return MarketSnapshot(
        symbol="XAUUSD_o",
        timeframe="M15",
        bid=price - 0.1,
        ask=price + 0.1,
        point=0.01,
        spread_points=20,
        bars=bars,
        news_risk="LOW",
        account_mode="DEMO",
    )


def test_signal_sources_are_off_by_default() -> None:
    config = StrategyConfig()
    overlays = ExternalSignalHub().collect(snapshot_with_volume(), config)

    assert overlays == []
    assert config.integrations.myfxbook_enabled is False
    assert config.integrations.order_flow_enabled is False
    assert config.integrations.cot_enabled is False


def test_order_flow_can_be_inserted_independently_without_network() -> None:
    config = StrategyConfig()
    config.integrations.order_flow_enabled = True
    overlays = ExternalSignalHub().collect(snapshot_with_volume(), config)

    assert len(overlays) == 1
    overlay = overlays[0]
    assert overlay.source == "order_flow"
    assert overlay.available is True
    assert overlay.buy_modifier >= 0
    assert overlay.sell_modifier >= 0
    assert "tick-volume" in overlay.reason


def test_myfxbook_status_reports_missing_credentials(monkeypatch) -> None:
    monkeypatch.delenv("MYFXBOOK_SESSION", raising=False)
    monkeypatch.delenv("MYFXBOOK_EMAIL", raising=False)
    monkeypatch.delenv("MYFXBOOK_PASSWORD", raising=False)
    config = StrategyConfig()
    config.integrations.myfxbook_enabled = True

    status = ExternalSignalHub().status(config)

    assert status["myfxbook"]["enabled"] is True
    assert status["myfxbook"]["configured"] is False
    assert status["order_flow"]["configured"] is True
    assert status["cot"]["configured"] is True
