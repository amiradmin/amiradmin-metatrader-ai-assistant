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
    assert "function attachTooltips()" in html
    assert 'className=\'tip\'' in html


def test_training_page_has_tooltips_and_cross_period_stability() -> None:
    html = training_page_html()

    assert "Cross-period stability" in html
    assert 'id="stabilityRows"' in html
    assert "const paramTips" in html
    assert "تعداد ترکیب‌های مختلف Threshold" in html
    assert "هدف دلاری روزانه برای مقایسه" in html
    assert "continuous" in html.lower()
