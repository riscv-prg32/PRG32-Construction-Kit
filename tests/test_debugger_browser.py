"""Audit scenario D in a real browser: the source and block debugger (refinement phase 4, ADR-0015).

The kit gets the committed Pong debug fixture (tests/debug_seed.py: the cartridge, its DWARF
debug map and its block map, made by the real toolchain), so this runs without one. In the
Player, with Chrome: a breakpoint on a block, the active block highlighted, the line in
game.c, the call stack, the Blocks variables, a watch, a conditional breakpoint, "Next
block", a source-line breakpoint from the keyboard, the CSR and stack views, no CSP
violation and no serious accessibility problem; and a cartridge without debug
information falls back to the address-level debugger.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from conftest import make_app
from debug_seed import seed_pong
from test_browser_offline import Recorder, browser, sign_in, wait_until  # noqa: F401 - fixtures

ROOT = Path(__file__).resolve().parent.parent
AXE = ROOT / "tests" / "vendor" / "axe-core" / "4.10.2" / "axe.min.js"


@pytest.fixture(scope="module")
def debug_kit(tmp_path_factory):
    from werkzeug.serving import make_server

    app = make_app(tmp_path_factory.mktemp("debugger-kit"))
    client = app.test_client()
    seeded = seed_pong(client, app.config["BUILD_ROOT"])
    plain = seed_pong(client, app.config["BUILD_ROOT"], with_maps=False)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield {"url": f"http://127.0.0.1:{server.server_port}", "cartridge": seeded["cartridge"],
           "plain": plain["cartridge"]}
    server.shutdown()


def open_player(context, kit, cartridge):
    page = context.new_page()
    sign_in(page, kit["url"])
    page.goto(f"{kit['url']}/player?artifact={cartridge}")
    wait_until(page, "!!window.PRG32SourceDebugger && document.getElementById('dbgEnable').disabled === false")
    return page


def stopped(page):
    wait_until(page, "!prg32Player.debugState().running && prg32Player.debugState().reason === 'breakpoint'", timeout=30)


def test_scenario_d_block_and_source_debugging(browser, debug_kit):  # noqa: F811
    context = browser.new_context(viewport={"width": 1400, "height": 1000})
    record = Recorder(context, debug_kit["url"])
    page = open_player(context, debug_kit, debug_kit["cartridge"])
    record.watch(page)
    wait_until(page, "!!PRG32SourceDebugger.session && PRG32SourceDebugger.session.ok && !!PRG32SourceDebugger.workspace")
    assert page.is_hidden("#srcDebugNote") and page.is_visible("#srcDebug")
    page.click("#dbgEnable")

    # A breakpoint on a block: click it in the (read-only) Blocks view, then the button.
    page.locator("#dbgBlocks").scroll_into_view_if_needed()
    page.evaluate("PRG32SourceDebugger.workspace.centerOnBlock('pong-24')")
    box = page.locator("#dbgBlocks [data-id='pong-24'] > .blocklyPath").first.bounding_box()
    page.mouse.click(box["x"] + 8, box["y"] + 8)
    wait_until(page, "document.getElementById('dbgBlockChoose').value === 'pong-24'")
    # ... or choose it from the keyboard list (here: the block that keeps player_y on screen).
    page.select_option("#dbgBlockChoose", "pong-34")
    wait_until(page, "!document.getElementById('dbgBlockBreak').disabled && $('#dbgBlockSelected').data('block') === 'pong-34'")
    page.focus("#dbgBlockBreak")
    page.keyboard.press("Enter")
    wait_until(page, "document.querySelectorAll('#dbgBlocks .dbg-block-breakpoint').length === 1")
    page.click("#dbgContinue")
    stopped(page)
    # The active block, its line in game.c, the call stack and the Blocks variables.
    assert page.evaluate("PRG32SourceDebugger.activeBlock") == "pong-34"
    assert page.evaluate("document.querySelectorAll('#dbgBlocks .dbg-block-active').length") == 1
    assert "keep player_y between" in page.inner_text("#dbgWhere")
    current = int(page.get_attribute("#dbgSource .dbg-current", "data-line"))
    source_map = page.evaluate("fetch(location.search.replace('?artifact=', '/api/artifacts/') + '/debug', "
                               "{headers: {'X-PRG32-Kit': '1'}}).then(r => r.json()).then(a => a.source_map)")
    span = next(entry["lines"] for entry in source_map["entries"] if entry["block"] == "pong-34")
    assert span[0] <= current <= span[1]
    assert page.inner_text("#dbgCallStack").startswith("pong_update")
    variables = page.inner_text("#dbgVariables")
    assert "player_y" in variables and "ball_x" in variables and "prg32_kit_" not in variables  # beginner view

    # A watch, then a condition on the block breakpoint: it only stops while ball_x < 150.
    page.fill("#dbgWatchInput", "ball_x")
    page.press("#dbgWatchInput", "Enter")
    wait_until(page, "document.getElementById('dbgWatches').innerText.includes('ball_x')")
    page.fill(".dbg-condition", "ball_x < 150")
    page.press(".dbg-condition", "Tab")
    for _ in range(3):
        page.click("#dbgContinue")
        stopped(page)
        ball_x = page.evaluate("PRG32SourceDebugger.session.watch('ball_x', null, {read: (a, l) => prg32Player.readMemory(a, l)}).value")
        assert ball_x < 150
        assert f"ball_x = {ball_x}" in " ".join(page.inner_text("#dbgWatches").split())

    # Next block: one click runs to the next block of the program.
    page.click("#dbgStepLine")
    wait_until(page, "PRG32SourceDebugger.activeBlock !== 'pong-34'")
    assert page.evaluate("PRG32SourceDebugger.activeBlock")

    # A source-line breakpoint from the keyboard (the line number is a button), in game.c.
    page.click("#tabSource")
    line = page.evaluate("""(() => { const lines = PRG32SourceDebugger.session; for (let n = 360; n < 420; n++) {
        const found = lines.breakpointForLine(n); if (found && found.line === n) return n; } return null; })()""")
    page.focus(f"#dbgSource .dbg-src-gutter[data-line='{line}']")
    page.keyboard.press("Enter")
    wait_until(page, f"!!document.querySelector(\"#dbgSource .dbg-src-line.dbg-bp[data-line='{line}']\")")
    page.click(".dbg-src-remove[data-kind=block]")  # remove the block breakpoint
    page.click("#dbgContinue")
    stopped(page)
    assert page.get_attribute("#dbgSource .dbg-current", "data-line") == str(line)

    # Advanced view: locals of the frame, the counter CSRs and the stack around sp.
    page.click("label[for=dbgAdvanced]")
    wait_until(page, "document.querySelectorAll('#dbgCsr tr').length === 3")
    assert "instret" in page.inner_text("#dbgCsr")
    assert page.evaluate("document.querySelectorAll('#dbgStackWords tr').length") >= 8
    assert "sp →" in page.inner_text("#dbgStackWords")

    page.mouse.move(0, 0)
    page.wait_for_timeout(400)  # Bootstrap's buttons fade their colours for 0.15 s: scan the final ones
    page.evaluate(AXE.read_text())
    results = page.evaluate("""axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})
        .then(r => r.violations.map(v => ({id: v.id, impact: v.impact, target: v.nodes.slice(0, 3).map(n => n.target.join(' '))})))""")
    serious = [violation for violation in results if violation["impact"] in ("serious", "critical")]
    assert serious == [], json.dumps(serious, indent=1)
    assert record.third_party() == []
    assert record.csp_violations() == []
    context.close()


def test_without_debug_information_the_address_debugger_remains(browser, debug_kit):  # noqa: F811
    context = browser.new_context()
    page = open_player(context, debug_kit, debug_kit["plain"])
    wait_until(page, "!document.getElementById('srcDebugNote').hidden")
    assert "without debug information" in page.inner_text("#srcDebugNote")
    assert page.is_hidden("#srcDebug")
    page.click("#dbgEnable")
    page.click("#dbgStep")
    wait_until(page, "document.querySelectorAll('#dbgCode .dbg-current').length === 1")
    context.close()


def test_breakpoints_switch_off_and_survive_compiling_again(browser, debug_kit):  # noqa: F811
    """Breakpoints are kept per project and source file: after the code is generated again they
    follow their line, or are listed as "the code changed" and not placed on other code."""
    context = browser.new_context(viewport={"width": 1400, "height": 1000})
    record = Recorder(context, debug_kit["url"])
    page = open_player(context, debug_kit, debug_kit["cartridge"])
    record.watch(page)
    wait_until(page, "!!PRG32SourceDebugger.session && PRG32SourceDebugger.session.ok")
    page.click("#dbgEnable")
    page.click("#tabSource")
    line = page.evaluate("""(() => { const s = PRG32SourceDebugger.session; for (let n = 360; n < 420; n++) {
        const found = s.breakpointForLine(n); if (found && found.line === n) return n; } return null; })()""")
    page.focus(f"#dbgSource .dbg-src-gutter[data-line='{line}']")
    page.keyboard.press("Enter")
    wait_until(page, f"!!document.querySelector(\"#dbgSource .dbg-src-line.dbg-bp[data-line='{line}']\")")
    # Switched off: kept in the list and in the gutter (hollow), but the program runs past it.
    page.uncheck(".dbg-src-enabled[data-kind=line]")
    wait_until(page, f"!!document.querySelector(\"#dbgSource .dbg-src-line.dbg-bp-off[data-line='{line}']\")")
    page.click("#dbgContinue")
    page.wait_for_timeout(600)
    assert page.evaluate("prg32Player.debugState().running") is True
    key = page.evaluate("Object.keys(localStorage).find(k => k.startsWith('prg32-kit-breakpoints:'))")
    assert key and key.endswith(":game.c")          # by project and file, not by cartridge
    saved = page.evaluate(f"JSON.parse(localStorage.getItem('{key}'))")
    assert saved["lines"][0]["enabled"] is False and saved["lines"][0]["text"]

    # "Compiled again": the line's code was saved at another line that has code of its own
    # (without its anchor the breakpoint would stay there), and one line is gone.
    text = saved["lines"][0]["text"]
    elsewhere = page.evaluate(f"""(() => {{ const s = PRG32SourceDebugger.session; for (let n = 300; n < {line}; n++) {{
        const found = s.breakpointForLine(n); if (found && found.line === n) return n; }} return null; }})()""")
    assert elsewhere and elsewhere != line
    page.evaluate(f"""localStorage.setItem('{key}', JSON.stringify({{lines: [
        {{line: {elsewhere}, text: {json.dumps(text)}, condition: '', enabled: true}},
        {{line: 5, text: 'this_line_was_removed();', condition: '', enabled: true}}], blocks: [], watches: []}}))""")
    page.reload()
    wait_until(page, "!!window.PRG32SourceDebugger && document.getElementById('dbgEnable').disabled === false")
    wait_until(page, "!!PRG32SourceDebugger.session && PRG32SourceDebugger.session.ok")
    page.click("#dbgEnable")                         # the panels are drawn while debugging
    page.click("#tabSource")
    wait_until(page, f"!!document.querySelector(\"#dbgSource .dbg-src-line.dbg-bp[data-line='{line}']\")")
    listed = page.inner_text("#dbgSourceBreakpoints")
    assert f"Line {line}" in listed and "the code changed" in listed and "this_line_was_removed" in listed
    assert not page.query_selector("#dbgSource .dbg-src-line.dbg-bp[data-line='5']")
    assert not page.query_selector(f"#dbgSource .dbg-src-line.dbg-bp[data-line='{elsewhere}']")
    assert record.csp_violations() == []
    context.close()
