from datetime import datetime, timedelta, timezone

from meta_trader_ai.control_extensions import inject_forex_factory_control
from meta_trader_ai.models import Bar, MarketSnapshot
from meta_trader_ai.news_calendar import ForexFactoryCalendar, NewsSourceStore


def snapshot() -> MarketSnapshot:
    bars = []
    price = 2000.0
    for i in range(60):
        o = price
        c = o + 0.2
        bars.append(
            Bar(
                time=1_700_000_000 + i * 900,
                open=o,
                high=c + 0.2,
                low=o - 0.2,
                close=c,
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
        news_risk="UNKNOWN",
        account_mode="DEMO",
    )


def event(now: datetime, minutes: int, impact: str, country: str = "USD") -> dict[str, str]:
    return {
        "title": f"Synthetic {impact} event",
        "country": country,
        "date": (now + timedelta(minutes=minutes)).isoformat(),
        "impact": impact,
        "forecast": "",
        "previous": "",
    }


def test_forex_factory_high_usd_event_blocks_window_classification() -> None:
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    assessment = ForexFactoryCalendar().assess(
        snapshot(),
        now=now,
        events=[event(now, 20, "High")],
    )

    assert assessment.available is True
    assert assessment.risk == "HIGH"
    assert "USD High" in assessment.reason
    assert "in 20m" in assessment.reason


def test_forex_factory_high_event_one_hour_warning_is_medium() -> None:
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    assessment = ForexFactoryCalendar().assess(
        snapshot(),
        now=now,
        events=[event(now, 45, "High")],
    )

    assert assessment.risk == "MEDIUM"


def test_xauusd_ignores_non_usd_calendar_events() -> None:
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    assessment = ForexFactoryCalendar().assess(
        snapshot(),
        now=now,
        events=[event(now, 10, "High", country="EUR")],
    )

    assert assessment.risk == "LOW"


def test_news_source_store_is_off_by_default_and_persists(tmp_path) -> None:
    store = NewsSourceStore(tmp_path / "news.json")
    assert store.load() == {"forex_factory_enabled": False}
    assert store.save({"forex_factory_enabled": True}) == {"forex_factory_enabled": True}
    assert store.load() == {"forex_factory_enabled": True}


def test_control_panel_injection_adds_forex_factory_checkbox() -> None:
    html = '<html><body><p class="actions"><button id="saveBtn">Save</button></p></body></html>'
    rendered = inject_forex_factory_control(html)

    assert 'id="forex_factory_enabled"' in rendered
    assert "Forex Factory calendar" in rendered
    assert "/news/sources" in rendered
    assert "/news/status" in rendered
