"""Guest games in the browser and conflict-safe autosave, in a real browser (ADR-0017).

- Without an account: games are kept in IndexedDB, survive a reload, export as files the
  dashboard imports, import back, and are deleted only after asking; the old single
  scratchpad becomes a guest game; no request carries a game to the server.
- After signing in: the dashboard moves the guest games into the account, and removes
  each one from the browser only after the server has it.
- The IDE autosaves; when two windows edit one project, the second gets a choice instead
  of overwriting the first, and "Keep mine as a copy" keeps both versions.
"""

from __future__ import annotations

import json

from test_browser_offline import Recorder, browser, live_kit, sign_in, wait_until  # noqa: F401 - fixtures
from test_ide_browser import END_OF_FILE, new_project, open_ide, press_until, project_json  # noqa: F401

GAME = {"blocks": {"languageVersion": 0, "blocks": [{"type": "prg32_on_start", "id": "g1", "x": 20, "y": 20}]}}


def guest_page(context, live_kit):  # noqa: F811 - the fixture, imported above
    page = context.new_page()
    page.goto(f"{live_kit}/static/offline.html?guest=1")
    wait_until(page, "!!window.PRG32Guest && !!PRG32Guest.current")
    return page


def add_block(page):
    page.evaluate("() => { const b = PRG32Blocks.getWorkspace().newBlock('prg32_on_start'); b.initSvg(); b.render(); }")
    wait_until(page, "!PRG32Guest.pending && PRG32GuestStore.list().then(rows => rows.some(row =>"
                     " JSON.stringify(row.blocks_json).includes('prg32_on_start')))")


def test_guest_games_stay_in_this_browser(browser, live_kit):  # noqa: F811
    context = browser.new_context(accept_downloads=True)
    record = Recorder(context, live_kit)
    page = record.watch(guest_page(context, live_kit))
    assert page.is_visible("#guestNotice") and page.is_hidden("#offlineNotice")
    page.fill("#guestTitle", "Space chase")
    add_block(page)
    page.reload()
    wait_until(page, "!!window.PRG32Guest && !!PRG32Guest.current")
    assert page.input_value("#guestTitle") == "Space chase"
    assert page.evaluate("PRG32Blocks.getWorkspace().getAllBlocks(false).length") >= 1
    wait_until(page, "document.getElementById('guestSpace').textContent.length > 0")
    # A second game, then export the first as a file and import it again.
    page.click("#guestNew")
    wait_until(page, "PRG32GuestStore.list().then(rows => rows.length === 2)")
    page.select_option("#guestProjects", label="Space chase")
    wait_until(page, "PRG32Guest.current.title === 'Space chase'")
    with page.expect_download() as download:
        page.click("#offlineExport")
    exported = json.loads(open(download.value.path()).read())
    assert exported["abi"] == "prg32-construction-kit-project-1.0" and exported["project"]["title"] == "Space chase"
    page.set_input_files("#offlineImport", download.value.path())
    wait_until(page, "PRG32GuestStore.list().then(rows => rows.length === 3)")
    # Deleting asks first; "no" keeps the game.
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.click("#guestDelete")
    page.wait_for_timeout(200)
    assert page.evaluate("PRG32GuestStore.list().then(rows => rows.length)") == 3
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("#guestDelete")
    wait_until(page, "PRG32GuestStore.list().then(rows => rows.length === 2)")
    # Nothing a guest does is sent to the server.
    assert not [url for url in record.requests if "/api/" in url]
    assert record.csp_violations() == []
    context.close()


def test_the_old_scratchpad_becomes_a_guest_game(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{live_kit}/static/offline-player.html")   # any page of the kit's origin
    page.evaluate("blocks => localStorage.setItem('prg32-offline-scratchpad', JSON.stringify(blocks))", GAME)
    page = guest_page(context, live_kit)
    assert page.evaluate("PRG32GuestStore.list().then(rows => rows.map(row => row.title))") == ["Offline sketch"]
    assert page.evaluate("localStorage.getItem('prg32-offline-scratchpad')") is None
    context.close()


def test_guest_games_move_into_the_account_after_sign_in(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    page = guest_page(context, live_kit)
    page.fill("#guestTitle", "Made as a guest")
    add_block(page)
    sign_in(page, live_kit)
    wait_until(page, "!document.getElementById('guestProjectsBanner').hidden")
    assert "1 game" in page.inner_text("#guestProjectsBanner")
    page.click("#moveGuestProjects")
    wait_until(page, "document.getElementById('guestProjectsBanner').hidden")
    assert page.evaluate("PRG32GuestStore.list().then(rows => rows.filter(row => Object.keys(row.blocks_json).length).length)") == 0
    titles = page.evaluate("fetch('/api/projects', {headers: {'X-PRG32-Kit': '1'}}).then(r => r.json())"
                           ".then(d => d.projects.map(p => p.title))")
    assert "Made as a guest" in titles
    context.close()


def test_autosave_and_a_conflict_between_two_windows(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    first, project_id = open_ide(context, live_kit, {
        "title": "Two windows", "game_json": {"source_mode": "c", "source_c": "void two_windows_init(void) {}\n"}})
    second = context.new_page()
    second.goto(f"{live_kit}/ide/{project_id}")
    wait_until(second, "document.getElementById('ide').dataset.ready === 'true'")
    # The first window edits and autosaves (no Save pressed).
    first.evaluate("PRG32Ide.editors.src.setValue(PRG32Ide.editors.src.getValue() + '/* first */\\n')")
    wait_until(first, "document.getElementById('statusSaved').textContent.startsWith('Autosaved')", timeout=20)
    assert "/* first */" in project_json(first, project_id)["game_json"]["source_c"]
    # The second window, opened before that, edits too: its autosave is refused, not applied.
    second.evaluate("PRG32Ide.editors.src.setValue(PRG32Ide.editors.src.getValue() + '/* second */\\n')")
    wait_until(second, "!!document.querySelector('#versionConflict.show')", timeout=20)
    assert second.evaluate("PRG32Ide.autosavePaused") is True
    saved = project_json(first, project_id)["game_json"]["source_c"]
    assert "/* first */" in saved and "/* second */" not in saved
    # "Keep mine as a copy": both versions survive.
    second.click("#versionConflict [data-choice=copy]")
    second.wait_for_url(lambda url: "/ide/project_" in url and not url.endswith(project_id))
    copy_id = second.url.rsplit("/", 1)[-1]
    assert copy_id != project_id
    assert "/* second */" in project_json(second, copy_id)["game_json"]["source_c"]
    assert "/* second */" not in project_json(second, project_id)["game_json"]["source_c"]
    context.close()
