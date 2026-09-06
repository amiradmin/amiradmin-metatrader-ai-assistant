from meta_trader_ai import api as api_module
from meta_trader_ai.config_store import StrategyConfigStore
from meta_trader_ai.control_extensions import inject_forex_factory_control
from meta_trader_ai.control_page import control_page_html
from meta_trader_ai.decision_engine import build_decision
from meta_trader_ai.journal import DecisionJournal
from meta_trader_ai.models import Bar, Decision, MarketSnapshot, StrategyConfig
from meta_trader_ai.pdf_mode import PdfRegime, PdfRangeZone, evaluate_pdf_mode
from meta_trader_ai.performance import PerformanceStore


def trend_snapshot(up: bool = True) -> MarketSnapshot:
    bars: list[Bar] = []
    price = 2000.0
    for i in range(80):
        step = 1.0 if up else -1.0
        open_price = price
        close = open_price + step
        bars.append(
            Bar(
                time=1_700_000_000 + i * 900,
                open=open_price,
                high=max(open_price, close) + 0.25,
                low=min(open_price, close) - 0.25,
                close=close,
            )
        )
        price = close
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


def range_snapshot() -> MarketSnapshot:
    bars: list[Bar] = []
    for i in range(80):
        open_price = 2000.0 + (1.2 if i % 2 == 0 else -1.2)
        close = 2000.0 + (-1.0 if i % 2 == 0 else 1.0)
        bars.append(
            Bar(
                time=1_700_000_000 + i * 900,
                open=open_price,
                high=max(open_price, close) + 0.5,
                low=min(open_price, close) - 0.5,
                close=close,
            )
        )
    bars[-1] = Bar(
        time=bars[-1].time,
        open=1999.9,
        high=2000.3,
        low=1999.7,
        close=2000.0,
    )
    return MarketSnapshot(
        symbol="XAUUSD_o",
        timeframe="M15",
        bid=1999.9,
        ask=2000.1,
        point=0.01,
        spread_points=20,
        bars=bars,
        news_risk="LOW",
        account_mode="DEMO",
    )


def permissive_config(mode: str) -> StrategyConfig:
    config = StrategyConfig(strategy_mode=mode)
    for name in (
        "dynamic_levels",
        "static_levels",
        "fibonacci",
        "patterns",
        "pivots",
        "divergence",
    ):
        factor = getattr(config, name)
        factor.min_score = 0
        factor.required = False
    config.decision.min_pass_count = 1
    config.decision.min_total_score = 0
    config.decision.min_side_edge = 0
    config.safety.max_spread_points = 60
    config.safety.block_high_news = True
    config.safety.block_unknown_news = False
    config.safety.demo_only = True
    config.safety.regime_filter_enabled = False
    return config


def test_pdf_mode_blocks_countertrend_direction() -> None:
    evaluation = evaluate_pdf_mode(trend_snapshot(up=True), Decision.SELL)

    assert evaluation.regime == PdfRegime.STRONG_UPTREND
    assert evaluation.allowed is False
    assert evaluation.status == "BLOCK"
    assert "blocked SELL" in (evaluation.reason or "")


def test_pdf_mode_preserves_with_trend_direction() -> None:
    evaluation = evaluate_pdf_mode(trend_snapshot(up=True), Decision.BUY)

    assert evaluation.regime == PdfRegime.STRONG_UPTREND
    assert evaluation.allowed is True
    assert evaluation.status == "CONFIRM"


def test_pdf_mode_blocks_middle_of_range() -> None:
    evaluation = evaluate_pdf_mode(range_snapshot(), Decision.BUY)

    assert evaluation.regime == PdfRegime.RANGE
    assert evaluation.range_zone == PdfRangeZone.MIDDLE
    assert evaluation.allowed is False
    assert "middle of the range" in (evaluation.reason or "")


def test_decision_engine_reports_normal_and_pdf_modes() -> None:
    normal = build_decision(trend_snapshot(), StrategyConfig())
    pdf_config = StrategyConfig(strategy_mode="PDF")
    pdf = build_decision(trend_snapshot(), pdf_config)

    assert normal.strategy_mode == "NORMAL"
    assert normal.pdf_status == "DISABLED"
    assert pdf.strategy_mode == "PDF"
    assert pdf.pdf_status in {"CONFIRM", "BLOCK", "OBSERVE"}
    assert pdf.pdf_regime != "UNAVAILABLE"
    assert pdf.signal_id.endswith("_PDF")


def test_normal_mode_can_emit_buy_and_sell_as_trade_allowed() -> None:
    buy = build_decision(trend_snapshot(up=True), permissive_config("NORMAL"))
    sell = build_decision(trend_snapshot(up=False), permissive_config("NORMAL"))

    assert buy.decision == Decision.BUY
    assert buy.trade_allowed is True
    assert buy.pdf_status == "DISABLED"
    assert sell.decision == Decision.SELL
    assert sell.trade_allowed is True
    assert sell.pdf_status == "DISABLED"


def test_pdf_mode_can_emit_with_trend_buy_and_sell_as_trade_allowed() -> None:
    buy = build_decision(trend_snapshot(up=True), permissive_config("PDF"))
    sell = build_decision(trend_snapshot(up=False), permissive_config("PDF"))

    assert buy.decision == Decision.BUY
    assert buy.trade_allowed is True
    assert buy.pdf_status == "CONFIRM"
    assert buy.pdf_regime == "STRONG_UPTREND"
    assert sell.decision == Decision.SELL
    assert sell.trade_allowed is True
    assert sell.pdf_status == "CONFIRM"
    assert sell.pdf_regime == "STRONG_DOWNTREND"


def test_strategy_modes_use_distinct_signal_ids_for_same_bar() -> None:
    normal = build_decision(trend_snapshot(up=True), permissive_config("NORMAL"))
    pdf = build_decision(trend_snapshot(up=True), permissive_config("PDF"))

    assert normal.signal_id != pdf.signal_id
    assert normal.signal_id.endswith("_NORMAL")
    assert pdf.signal_id.endswith("_PDF")
    assert normal.risk_percent == pdf.risk_percent
    assert normal.reward_risk_ratio == pdf.reward_risk_ratio
    assert normal.max_open_trades == pdf.max_open_trades


def test_recommended_profile_preserves_pdf_strategy_mode(tmp_path, monkeypatch) -> None:
    config_store = StrategyConfigStore(tmp_path / "strategy.json")
    config_store.save(StrategyConfig(strategy_mode="PDF"))
    monkeypatch.setattr(api_module, "config_store", config_store)
    monkeypatch.setattr(api_module, "performance_store", PerformanceStore(tmp_path / "outcomes.jsonl"))
    monkeypatch.setattr(api_module, "decision_journal", DecisionJournal(tmp_path / "decisions.jsonl"))

    payload = api_module._recommended_payload()
    saved = api_module.apply_recommended_strategy()

    assert payload["config"]["strategy_mode"] == "PDF"
    assert saved.strategy_mode == "PDF"
    assert config_store.load().strategy_mode == "PDF"


def test_control_panel_injection_puts_pdf_toggle_beside_ninja() -> None:
    rendered = inject_forex_factory_control(control_page_html())

    ninja = rendered.index('id="ninjaPresetBtn"')
    pdf = rendered.index('id="pdfModeBtn"')
    assert ninja < pdf
    assert "PDF Mode: OFF" in rendered
    assert "cfg.strategy_mode" in rendered
    assert "PDF Mode toggle runtime" in rendered
