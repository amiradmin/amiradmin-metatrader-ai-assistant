from meta_trader_ai.control_page import control_page_html


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
