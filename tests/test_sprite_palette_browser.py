"""Sprite Lab with a palette, in a real browser (docs/sprite_editor.md).

A student paints in direct colours, switches to indexed colours (the palette is made from the
colours used), paints with an entry, changes an entry's colour (every pixel of it changes), saves,
and after a reload finds the same palette; Convert to C gives the indexed sprite.
"""

from __future__ import annotations

from test_accounts_browser import serious
from test_browser_offline import Recorder, browser, live_kit, sign_in, wait_until  # noqa: F401 - fixtures
from test_i18n_browser import api


def click_cell(page, x, y, width=16):
    box = page.locator("#spriteCanvas").bounding_box()
    cell = box["width"] / width
    page.mouse.click(box["x"] + (x + 0.5) * cell, box["y"] + (y + 0.5) * cell)


def test_a_sprite_gets_a_palette_and_keeps_it(browser, live_kit):  # noqa: F811
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    sign_in(page, live_kit)
    project = api(page, "/api/projects", "POST", {"title": "Palette"})
    page.goto(f"{live_kit}/ide/{project['id']}#sprites")
    wait_until(page, "!!window.PRG32SpriteLab && !!document.querySelector('#spriteColorMode')")
    page.evaluate("document.querySelector('#paintColor').value = '#ff0000'")
    click_cell(page, 0, 0)
    page.evaluate("document.querySelector('#paintColor').value = '#00ff00'")
    click_cell(page, 1, 0)
    page.select_option("#spriteColorMode", "indexed")
    assert page.is_visible("#spritePalettePanel") and not page.is_visible("#spriteDirectPanel")
    entries = page.locator("#spritePalette .palette-entry")
    assert entries.count() == 3                                  # transparent, red, green
    assert "2 bits per pixel" in page.text_content("#spritePaletteInfo")
    # Paint with entry 2 (green), then make entry 1 blue: the red pixel turns blue.
    entries.nth(2).click()
    click_cell(page, 2, 0)
    entries.nth(1).click()
    page.evaluate("const i = document.querySelector('#paletteEntryColor'); i.value = '#0000ff'; i.dispatchEvent(new Event('input', {bubbles: true}))")
    page.click("#saveSprite")
    wait_until(page, "!!document.querySelector('#spriteId').value")
    sprite_id = page.input_value("#spriteId")
    saved = api(page, f"/api/sprites/{sprite_id}")
    assert saved["palette"]["colors"] == ["#000000", "#0000ff", "#00ff00"] and saved["palette"]["transparent_index"] == 0
    assert saved["palette"]["indices"][0][:4] == [1, 2, 2, 0] and saved["pixels"][0][:3] == ["#0000ff", "#00ff00", "#00ff00"]
    page.reload()
    wait_until(page, "!!window.PRG32SpriteLab")
    page.evaluate(f"PRG32SpriteLab.open('{sprite_id}')")
    wait_until(page, "document.querySelectorAll('#spritePalette .palette-entry').length === 3")
    assert page.input_value("#spriteColorMode") == "indexed"
    page.click("#convertSprite")
    wait_until(page, "document.querySelector('#spriteC').textContent.includes('prg32_indexed_sprite_t')")
    assert record.csp_violations() == [] and serious(page) == []
    context.close()
