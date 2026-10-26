"""Backgrounds in a real browser (docs/backgrounds.md): like Sprite Lab, a tab of the project's IDE.

Signed in: the menu item opens the tab; a student edits a tile, paints the map, saves, finds the
background in the project tree and gets its C. As a guest: the same, kept in the browser.
"""

from __future__ import annotations

from test_accounts_browser import serious
from test_browser_offline import Recorder, browser, live_kit, sign_in, wait_until  # noqa: F401 - fixtures
from test_i18n_browser import api


def click(page, selector, x, y, columns, rows):
    box = page.locator(selector).bounding_box()
    page.mouse.click(box["x"] + (x + 0.5) * box["width"] / columns, box["y"] + (y + 0.5) * box["height"] / rows)


def paint_and_save(page):
    wait_until(page, "!!window.PRG32Backgrounds && !!document.querySelector('#backgroundsTool canvas')")
    page.click('#tilePalette .tile-entry[data-tile="1"]')
    click(page, "#tileCanvas", 3, 3, 8, 8)                    # a pixel of the brick: off, it was on
    # The map shows 40x25 tiles of 16 screen pixels (canvas 640x400): paint cells (0, 0) and (5, 2).
    click(page, "#backgroundCanvas", 0, 0, 40, 25)
    click(page, "#backgroundCanvas", 5, 2, 40, 25)
    page.fill("#backgroundName", "level one")
    page.click("#saveBackground")
    wait_until(page, "!!document.querySelector('#backgroundId').value")
    return page.input_value("#backgroundId")


def test_a_background_is_drawn_saved_and_converted(browser, live_kit):  # noqa: F811
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    sign_in(page, live_kit)
    project = api(page, "/api/projects", "POST", {"title": "Tiles"})
    page.goto(f"{live_kit}/ide/{project['id']}")
    wait_until(page, "document.querySelector('#ide').dataset.ready === 'true'")
    page.click('[data-ide-tool="backgrounds"]')
    asset_id = paint_and_save(page)
    saved = api(page, f"/api/assets/{asset_id}")
    assert saved["kind"] == "background" and saved["name"] == "level one"
    assert saved["data"]["layers"][0][0][0] == 1 and saved["data"]["layers"][0][2][5] == 1
    assert saved["data"]["tiles"][0]["rows"][3] == 0b11101111              # row 3 was 255: pixel 3 turned off
    wait_until(page, "!!document.querySelector('[data-id=\"background-" + asset_id + "\"], [data-node=\"background-" + asset_id + "\"]') "
                     "|| document.querySelector('.ide-tree').textContent.includes('level one')")
    page.click("#convertBackground")
    wait_until(page, "document.querySelector('#backgroundC').textContent.includes('void level_one_load(void)')")
    assert record.csp_violations() == [] and serious(page) == []
    context.close()


def test_a_guest_keeps_backgrounds_in_the_browser(browser, live_kit):  # noqa: F811
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    page.goto(live_kit + "/")
    wait_until(page, "window.Kit && Kit.guest === true && !!window.PRG32GuestApi")
    project = api(page, "/api/projects", "POST", {"title": "Guest tiles"})
    page.goto(f"{live_kit}/ide/{project['id']}#backgrounds")
    asset_id = paint_and_save(page)
    assert asset_id.startswith("guest-bg-")
    page.reload()
    wait_until(page, "!!window.PRG32Backgrounds")
    listed = api(page, f"/api/assets?kind=background&project_id={project['id']}")
    assert [item["name"] for item in listed["assets"]] == ["level one"]
    page.evaluate(f"PRG32Backgrounds.open('{asset_id}')")
    page.click("#convertBackground")
    wait_until(page, "document.querySelector('#backgroundC').textContent.includes('prg32_playfield_put')")
    stored = api(page, f"/api/assets/{asset_id}")
    assert stored["data"]["layers"][0][2][5] == 1
    kept = [url for url in record.requests if "/api/" in url and "/api/guest/" not in url and "/api/examples" not in url]
    assert kept == []
    context.close()
