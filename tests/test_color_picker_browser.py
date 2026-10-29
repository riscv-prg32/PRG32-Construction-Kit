"""Tools > Color Picker in a real browser: a colour as RGB24 and RGB565, in hex, decimal and binary.

The expected numbers are worked out by hand from the formats:
#FFCC00 is R=255, G=204, B=0, so RGB24 = 0xFFCC00 = 16763904 = 11111111 11001100 00000000, and
RGB565 keeps the top 5/6/5 bits: R=31, G=51, B=0, so 0xFE60 = 65120 = 11111 110011 00000. Shown back
in 8 bits (top bits repeated) that is #FFCF00. Nothing is sent to the server, and guests may use it.
"""

from __future__ import annotations

from test_accounts_browser import serious
from test_browser_offline import Recorder, browser, live_kit, wait_until  # noqa: F401 - fixtures


def out(page, name):
    return page.text_content(f'[data-out="{name}"]').strip()


def test_a_colour_in_both_formats_and_three_bases(browser, live_kit):  # noqa: F811
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    page.goto(live_kit + "/")
    page.click("#toolsMenu")
    page.click("text=Color Picker")
    wait_until(page, "!!window.PRG32Color && document.querySelector('[data-out=\"rgb565-hex\"]').textContent.length > 0")
    page.fill("#hexInput", "#FFCC00")
    assert out(page, "rgb24-hex").startswith("0xFFCC00") and out(page, "rgb24-dec") == "16763904"
    assert out(page, "rgb24-bin") == "11111111 11001100 00000000"
    assert out(page, "rgb565-hex") == "0xFE60" and out(page, "rgb565-dec") == "65120"
    assert out(page, "rgb565-bin") == "11111 110011 00000"
    assert out(page, "c") == "0xFE60 /* #FFCF00 */" and out(page, "nearest") == "PRG32_COLOR_YELLOW"
    assert page.input_value("#rNumber") == "255" and page.input_value("#gNumber") == "204"
    # The channels move the colour too; white is exactly the PRG32's white.
    for channel in ("r", "g", "b"):
        page.fill(f"#{channel}Number", "255")
    assert out(page, "rgb565-hex") == "0xFFFF" and out(page, "rgb24-hex").startswith("0xFFFFFF")
    assert out(page, "nearest").startswith("PRG32_COLOR_WHITE (")
    page.fill("#hexInput", "#12345")                        # five digits: refused, nothing changes
    assert "is-invalid" in page.get_attribute("#hexInput", "class") and out(page, "rgb565-hex") == "0xFFFF"
    assert page.evaluate("PRG32Color.rgb565(0, 0, 255)") == 0x001F
    assert page.evaluate("PRG32Color.rgb565ToRgb(0xF800)") == {"r": 255, "g": 0, "b": 0}
    assert [url for url in record.requests if "/api/" in url] == []
    assert record.csp_violations() == [] and record.third_party() == [] and serious(page) == []
    context.close()
