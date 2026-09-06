from meta_trader_ai.control_extensions import inject_forex_factory_control
from meta_trader_ai.control_page import control_page_html


def test_control_tooltips_handle_mixed_rtl_ltr_text() -> None:
    html = inject_forex_factory_control(control_page_html())

    assert "unicode-bidi:plaintext" in html
    assert "direction:rtl" in html
    assert "text-align:start" in html
    assert "overflow-wrap:anywhere" in html
    assert "width:320px" in html
