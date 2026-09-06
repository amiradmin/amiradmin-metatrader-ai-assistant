from meta_trader_ai.control_extensions import inject_forex_factory_control
from meta_trader_ai.control_page import control_page_html


def test_control_tooltips_render_rtl_with_isolated_ltr_runs() -> None:
    html = inject_forex_factory_control(control_page_html())

    assert "mixed-bidi tooltip runtime" in html
    assert ".tipbox{" in html
    assert ".tipbox bdi{" in html
    assert "direction:rtl" in html
    assert "unicode-bidi:isolate" in html
    assert "text-align:right" in html
    assert "width:360px" in html
    assert "content:none!important" in html
    assert "document.createElement('bdi')" in html
    assert "isolate.dir='ltr'" in html
    assert "MutationObserver" in html
