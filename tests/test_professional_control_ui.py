from meta_trader_ai.control_extensions import inject_forex_factory_control
from meta_trader_ai.control_page import control_page_html


def test_professional_control_center_wraps_existing_functionality() -> None:
    html = inject_forex_factory_control(control_page_html())

    assert 'class="control-hero"' in html
    assert "Bridge Control Center" in html
    assert "AMIR META TRADER AI" in html
    assert 'class="command-nav"' in html
    assert 'href="#factors"' in html
    assert 'href="#execution-gates"' in html
    assert 'href="#signal-overlays"' in html
    assert 'href="#news-calendar"' in html
    assert 'href="#historical-replay"' in html
    assert "professional control UX runtime" in html
    assert "primary-actions" in html
    assert "ninja-note" in html


def test_professional_control_center_preserves_runtime_controls() -> None:
    html = inject_forex_factory_control(control_page_html())

    for control_id in (
        "factors",
        "saveBtn",
        "researchPresetBtn",
        "researchRegimeBtn",
        "ninjaPresetBtn",
        "pdfModeBtn",
        "forex_factory_enabled",
        "recommendBtn",
        "runLonaPeriod",
        "runBt",
    ):
        assert f'id="{control_id}"' in html

    assert "/strategy/config" in html
    assert "/news/sources" in html
    assert "/news/status" in html
    assert "mixed-bidi tooltip runtime" in html


def test_historical_workspace_is_single_day_report_in_ui() -> None:
    html = inject_forex_factory_control(control_page_html())

    assert "single-day historical report UX" in html
    assert "Historical daily report" in html
    assert "Report date" in html
    assert "Generate daily report" in html
    assert "endField.style.display='none'" in html
    assert "end.value=start.value" in html
    assert 'id="btStartDate"' in html
    assert 'id="btEndDate"' in html
