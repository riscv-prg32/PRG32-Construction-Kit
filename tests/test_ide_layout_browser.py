"""The IDE laid out like a JetBrains IDE, in a real browser (ADR-0024).

- Files on the left, the editor in the centre with the tool window below it (Problems, Build,
  Console, Debug), the simulator on the right; splitters and show/hide, remembered.
- Run: Blocks, C and assembly projects run in the WebAssembly simulator, for an account and for
  a visitor without one. Where this machine has no PRG32 toolchain (the CI browser job), Blocks
  run in the JavaScript preview instead and C says why it cannot run: both paths are checked,
  so nothing here is skipped.
- A narrow window stacks the panes; axe finds no serious problem at three widths.
"""

from __future__ import annotations

import json

from test_accounts_browser import serious
from test_browser_offline import Recorder, browser, live_kit, sign_in, wait_until  # noqa: F401 - fixtures

KINDS = ("blocks", "c", "asm")


def new_project(page, kind):
    return page.evaluate("""async kind => {
        const start = await Kit.api('/api/starters/' + kind + '?title=' + encodeURIComponent('Layout ' + kind));
        const project = await Kit.api('/api/projects', {method: 'POST', body: {title: 'Layout ' + kind,
            blocks_json: start.blocks_json, game_json: start.game_json}});
        return project.id; }""", kind)


def open_ide(page, live_kit, project_id):  # noqa: F811
    page.goto(f"{live_kit}/ide/{project_id}")
    wait_until(page, "document.getElementById('ide').dataset.ready === 'true'", timeout=30)


def lit_pixels(page, canvas):
    return page.evaluate("""id => { const d = document.getElementById(id).getContext('2d').getImageData(0, 0, 320, 200).data;
        let n = 0; for (let i = 0; i < d.length; i += 4) if (d[i] | d[i + 1] | d[i + 2]) n++; return n; }""", canvas)


def can_compile(page):
    return page.evaluate("fetch('/.well-known/prg32-construction-kit.json').then(r => r.json())"
                         ".then(d => d.cartridge_builds.available)")


def run_every_kind(page, live_kit):  # noqa: F811
    compiles = can_compile(page)
    for kind in KINDS:
        open_ide(page, live_kit, new_project(page, kind))
        page.click("#ideRun")
        if compiles:
            wait_until(page, "document.getElementById('statusBuild').textContent === 'Running'", timeout=60)
            assert page.is_visible("#playerScreen") and page.is_hidden("#gameCanvas")
            wait_until(page, "PRG32PlayerPage.player.frames > 5")
            assert lit_pixels(page, "playerScreen") > 0, kind
            # The on-screen pad drives the game: hold RIGHT and the player square moves.
            before = page.evaluate("PRG32PlayerPage.player.frames")
            page.dispatch_event("#touchButtons [data-button=RIGHT]", "pointerdown")
            wait_until(page, f"PRG32PlayerPage.player.frames > {before + 10}")
            page.dispatch_event("#touchButtons [data-button=RIGHT]", "pointerup")
        elif kind == "blocks":
            wait_until(page, "document.getElementById('statusBuild').textContent.includes('Blocks preview')")
            assert page.is_visible("#gameCanvas") and page.is_hidden("#playerScreen")
        else:
            wait_until(page, "document.getElementById('statusBuild').textContent === 'Not running'")
            assert "cannot compile" in page.inner_text("#ideConsole")


def test_an_account_runs_blocks_c_and_assembly_in_the_simulator(browser, live_kit):  # noqa: F811
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    sign_in(page, live_kit)
    run_every_kind(page, live_kit)
    assert record.csp_violations() == []
    context.close()


def test_a_guest_runs_blocks_c_and_assembly_in_the_simulator(browser, live_kit):  # noqa: F811
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    page.goto(live_kit + "/")
    wait_until(page, "window.Kit && Kit.guest === true")
    run_every_kind(page, live_kit)
    # A guest's runs keep nothing on the server: no project was created there.
    assert not [url for url in record.requests if url.endswith("/api/projects")]
    assert record.csp_violations() == []
    context.close()


def test_panes_resize_hide_and_are_remembered(browser, live_kit):  # noqa: F811
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    sign_in(page, live_kit)
    project = new_project(page, "c")
    open_ide(page, live_kit, project)
    for region in ("#ideTree", "#ideEditorArea", "#idePanel", "#ideSim"):
        assert page.is_visible(region), region
    sim = page.evaluate("document.getElementById('ideSim').getBoundingClientRect()")
    editor = page.evaluate("document.getElementById('ideEditorArea').getBoundingClientRect()")
    panel = page.evaluate("document.getElementById('idePanel').getBoundingClientRect()")
    assert sim["left"] > editor["right"] - 1 and panel["top"] > editor["bottom"] - 1   # right, and below
    width = sim["width"]
    page.focus(".ide-splitter-sim")
    page.keyboard.press("ArrowLeft")                       # the simulator grows
    wait_until(page, f"document.getElementById('ideSim').getBoundingClientRect().width > {width + 10}")
    page.click(".ide-pane-toggle[data-pane=panel]")         # hide the tool window
    assert page.is_hidden("#idePanel")
    page.reload()
    wait_until(page, "document.getElementById('ide').dataset.ready === 'true'", timeout=30)
    assert page.is_hidden("#idePanel")                       # remembered in this browser
    assert page.evaluate(f"document.getElementById('ideSim').getBoundingClientRect().width > {width + 10}")
    page.keyboard.press("Alt+4")                             # and back
    assert page.is_visible("#idePanel")
    page.evaluate("IdeShell.showPanel('debug')")
    assert page.is_visible("#dbgEnable") and page.is_visible("#dbgCode")
    context.close()


def test_a_narrow_window_stacks_the_panes(browser, live_kit):  # noqa: F811
    context = browser.new_context(viewport={"width": 700, "height": 900})
    page = context.new_page()
    sign_in(page, live_kit)
    open_ide(page, live_kit, new_project(page, "blocks"))
    boxes = page.evaluate("""['ideEditorArea', 'ideSim', 'idePanel'].map(id =>
        document.getElementById(id).getBoundingClientRect().top)""")
    assert boxes == sorted(boxes)                            # editor, then simulator, then tool window
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    context.close()


def test_the_ide_is_clean_at_three_widths(browser, live_kit):  # noqa: F811
    for width in (1100, 1280, 1440):
        context = browser.new_context(viewport={"width": width, "height": 900})
        page = context.new_page()
        sign_in(page, live_kit)
        page.click("#storageNoticeOk")
        open_ide(page, live_kit, new_project(page, "blocks"))
        for panel in ("problems", "debug"):
            page.evaluate(f"IdeShell.showPanel('{panel}')")
            found = serious(page)
            assert found == [], (width, panel, json.dumps(found, indent=1))
        context.close()


def convert_in_the_ide(page, live_kit, project_id):  # noqa: F811
    open_ide(page, live_kit, project_id)
    assert page.get_attribute("#ideType", "data-type") == "blocks"
    page.click("#ideProjectMenu")
    page.click("#ideProjectItems [data-convert=c]")
    wait_until(page, "!!document.querySelector('#ideConvertDialog.show')")
    assert "cannot be undone" in page.inner_text("#ideConvertDialog")
    page.click("#ideConvertConfirm")
    page.wait_for_load_state("load")
    wait_until(page, "document.getElementById('ide').dataset.ready === 'true' && "
                     "document.getElementById('ideType').dataset.type === 'c'", timeout=30)
    assert "this is your own C now" in page.evaluate("PRG32Ide.editors.src.getValue()")
    page.click("#ideProjectMenu")
    assert page.is_hidden("#ideProjectItems [data-convert=c]")     # never again, never back
    back = page.evaluate("""id => Kit.api('/api/projects/' + id, {method: 'PUT', body: {game_json: {abi: 'ir'}}})
        .then(() => 'saved', err => err.code)""", project_id)
    assert back == "type_locked"


def test_blocks_convert_to_c_once_for_an_account_and_a_guest(browser, live_kit):  # noqa: F811
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    sign_in(page, live_kit)
    convert_in_the_ide(page, live_kit, new_project(page, "blocks"))
    context.close()
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.goto(live_kit + "/")
    wait_until(page, "window.Kit && Kit.guest === true")
    convert_in_the_ide(page, live_kit, new_project(page, "blocks"))
    context.close()
