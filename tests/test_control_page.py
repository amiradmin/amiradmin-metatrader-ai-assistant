from meta_trader_ai.control_page import control_page_html
from meta_trader_ai.training_page import training_page_html


def test_control_page_exposes_cross_engine_comparison() -> None:
    html = control_page_html()

    assert "Our Model vs LONA" in html
    assert 'id="runLonaPeriod"' in html
    assert 'id="compareStatus"' in html
    assert "function renderComparison()" in html
    assert "function runLonaPeriod()" in html
    assert "Profit factor" in html
    assert "Max drawdown" in html
    assert "/backtest/range" in html
    assert "Continuous Stable-Baseline parity" in html
    assert "No daily forced close" in html
    assert "RANGE_CLOSE" in html


def test_control_page_has_persian_parameter_tooltips() -> None:
    html = control_page_html()

    assert "const paramTips" in html
    assert "حداقل تعداد فاکتورهایی" in html
    assert "حداکثر تعداد پوزیشن‌های هم‌زمان" in html
    assert "درصد Equity" in html
    assert "بازار کم‌روند یا کم‌تحرک" in html
    assert "فاصله EMA20 و EMA50" in html
    assert "function attachTooltips()" in html
    assert 'className=\'tip\'' in html


def test_control_page_has_one_click_research_candidate() -> None:
    html = control_page_html()

    assert 'id="researchPresetBtn"' in html
    assert "function applyResearchPreset()" in html
    assert "dynamic_levels:55" in html
    assert "static_levels:50" in html
    assert "setBound('min_pass_count',2)" in html
    assert "setBound('min_total_score',43)" in html
    assert "setBound('min_side_edge',7)" in html
    assert "setBound('max_open_trades',1)" in html
    assert "setBound('risk_percent',0.5)" in html
    assert "setBound('reward_risk_ratio',2)" in html
    assert 'id="risk_percent"' in html
    assert 'id="reward_risk_ratio"' in html


def test_control_page_has_regime_filter_research_preset() -> None:
    html = control_page_html()

    assert 'id="regime_filter_enabled"' in html
    assert 'id="regime_min_trend_atr"' in html
    assert 'id="regime_min_atr_ratio"' in html
    assert 'id="researchRegimeBtn"' in html
    assert "function applyResearchRegimePreset()" in html
    assert "setBound('regime_min_trend_atr',0.18)" in html
    assert "setBound('regime_min_atr_ratio',0.90)" in html


def test_control_page_has_ninja_aggressive_demo_preset() -> None:
    html = control_page_html()

    assert 'id="ninjaPresetBtn"' in html
    assert "Ninja · Aggressive DEMO" in html
    assert "function setNinjaPreset()" in html
    assert "function applyNinjaPreset()" in html
    assert "dynamic_levels:50" in html
    assert "static_levels:45" in html
    assert "fibonacci:40" in html
    assert "patterns:40" in html
    assert "pivots:35" in html
    assert "divergence:35" in html
    assert "setBound('min_total_score',40)" in html
    assert "setBound('min_side_edge',4)" in html
    assert "setBound('max_open_trades',3)" in html
    assert "setBound('risk_percent',2.0)" in html
    assert "setBound('reward_risk_ratio',2.5)" in html
    assert "cfg.safety.demo_only=true" in html
    assert "regime/workflow unchanged" in html


def test_control_page_has_independent_workflow_source_checkboxes() -> None:
    html = control_page_html()

    assert "Optional workflow signal overlays" in html
    assert 'id="myfxbook_enabled"' in html
    assert 'id="order_flow_enabled"' in html
    assert 'id="cot_enabled"' in html
    assert 'id="integrationStatus"' in html
    assert "cfg.integrations.myfxbook_enabled" in html
    assert "cfg.integrations.order_flow_enabled" in html
    assert "cfg.integrations.cot_enabled" in html
    assert "/integrations/status" in html
    assert "IN WORKFLOW" in html
    assert "Historical replay intentionally does not inject today's Myfxbook/COT data" in html


def test_training_page_has_tooltips_and_cross_period_stability() -> None:
    html = training_page_html()

    assert "Cross-period stability" in html
    assert 'id="stabilityRows"' in html
    assert "const paramTips" in html
    assert "تعداد ترکیب‌های مختلف Threshold" in html
    assert "هدف دلاری روزانه برای مقایسه" in html
    assert "continuous" in html.lower()
