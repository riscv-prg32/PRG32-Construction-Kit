"""The IDE in a real browser (refinement phase 2, ADR-0013): keyboard-only work, Monaco, a11y.

Uses Playwright with Chrome (or Playwright's Chromium) against a live kit; skips cleanly without
them. Every workflow below is driven with the keyboard only (no mouse clicks), and axe-core
(tests/vendor, test-only) checks the page for serious or critical accessibility violations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from test_browser_offline import (  # noqa: F401 - fixtures
    Recorder,
    browser,
    live_kit,
    sign_in,
    wait_until,
)

ROOT = Path(__file__).resolve().parent.parent
# Monaco's "end of file" key: Cmd+Down on a Mac, Ctrl+End elsewhere.
END_OF_FILE = "Meta+ArrowDown" if sys.platform == "darwin" else "Control+End"
AXE = ROOT / "tests" / "vendor" / "axe-core" / "4.10.2" / "axe.min.js"
C_SOURCE = ('#include "prg32.h"\n'
            "void kb_c_init(void) {}\n"
            "void kb_c_update(void) {}\n"
            "void kb_c_draw(void) { prg32_gfx_clear(0); }\n")
ASM_SOURCE = ("    .section .text\n    .globl kb_asm_init\n    .globl kb_asm_update\n    .globl kb_asm_draw\n"
              "kb_asm_init:\n    ret\nkb_asm_update:\n    ret\nkb_asm_draw:\n    ret\n")


def new_project(page, body):
    return page.evaluate("""body => fetch('/api/projects', {method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-PRG32-Kit': '1'}, body: JSON.stringify(body)})
        .then(r => r.json()).then(p => p.id)""", body)


def project_json(page, project_id):
    return page.evaluate("id => fetch('/api/projects/' + id, {headers: {'X-PRG32-Kit': '1'}}).then(r => r.json())",
                         project_id)


def open_ide(context, live_kit, body=None):  # noqa: F811 - the fixture's value is passed in
    page = context.new_page()
    sign_in(page, live_kit)
    project_id = new_project(page, body) if body else page.evaluate(
        "fetch('/api/projects', {headers: {'X-PRG32-Kit': '1'}}).then(r => r.json())"
        ".then(d => d.projects.find(p => p.title === 'Pong').id)")
    page.goto(f"{live_kit}/ide/{project_id}")
    wait_until(page, "document.getElementById('ide').dataset.ready === 'true'")
    return page, project_id


def active(page) -> dict:
    """What has the keyboard focus now."""
    return page.evaluate("""() => { const e = document.activeElement;
        return {role: e.getAttribute('role'), id: e.id, tag: e.tagName, inMonaco: !!e.closest('.monaco-editor'),
                region: (e.closest('[data-region]') || {}).dataset ? e.closest('[data-region]').dataset.region : null,
                text: (e.textContent || '').trim().slice(0, 60)}; }""")


def press_until(page, key, predicate, limit=12):
    for _ in range(limit):
        if predicate(active(page)):
            return
        page.keyboard.press(key)
    assert predicate(active(page)), active(page)


def test_ide_has_no_csp_violations_or_serious_accessibility_problems(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    record = Recorder(context, live_kit)
    page, _ = open_ide(context, live_kit)
    record.watch(page)
    page.keyboard.press("Control+Shift+P")
    wait_until(page, "document.activeElement.id === 'paletteInput'")
    page.keyboard.type("generated c")
    page.keyboard.press("Enter")
    wait_until(page, "!!PRG32Ide.editors['gen-c'] && PRG32Ide.editors['gen-c'].getValue().includes('PRG32')")
    page.evaluate(AXE.read_text())  # through DevTools, so the page's CSP is not weakened for the test
    results = page.evaluate("""axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})
        .then(r => r.violations.map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.length,
                                           target: v.nodes.slice(0, 3).map(n => n.target.join(' '))})))""")
    serious = [violation for violation in results if violation["impact"] in ("serious", "critical")]
    assert serious == [], json.dumps(serious, indent=1)
    assert record.third_party() == []
    assert record.csp_violations() == []
    context.close()


def test_keyboard_only_c_workflow(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    page, project_id = open_ide(context, live_kit, {
        "title": "Kb C", "game_json": {"source_mode": "c", "source_c": C_SOURCE}})
    # F6 moves between regions until the project tree has the focus.
    press_until(page, "F6", lambda focus: focus["role"] == "treeitem")
    press_until(page, "ArrowDown", lambda focus: focus["id"] == "tree-src")
    page.keyboard.press("Enter")
    wait_until(page, "document.activeElement.closest('.monaco-editor') !== null")
    page.keyboard.press(END_OF_FILE)
    page.keyboard.type("/* typed with the keyboard */\n")
    wait_until(page, "PRG32Ide.dirty === true")
    page.keyboard.press("Control+s")
    wait_until(page, "PRG32Ide.dirty === false")
    assert "typed with the keyboard" in project_json(page, project_id)["game_json"]["source_c"]
    # The command palette compiles; focus comes back afterwards.
    page.keyboard.press("Control+Shift+P")
    wait_until(page, "document.activeElement.id === 'paletteInput'")
    page.keyboard.type("compile")
    page.keyboard.press("Enter")
    wait_until(page, "!['', 'Compiling…'].includes(document.getElementById('statusBuild').textContent)", timeout=60)
    assert page.evaluate("document.getElementById('ideOutput').textContent") != "Compiling…"
    context.close()


def test_assembly_problems_mark_the_line_and_jump_there(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    page, _ = open_ide(context, live_kit, {
        "title": "Kb Asm", "game_json": {"source_mode": "asm", "source_asm": ASM_SOURCE}})
    assert page.evaluate("PRG32Ide.editors.src.getModel().getLanguageId()") == "prg32-asm"
    press_until(page, "F6", lambda focus: focus["inMonaco"])
    page.keyboard.press(END_OF_FILE)
    page.keyboard.type("    .fill 4, 1, 0\n")     # a directive the kit does not allow
    page.keyboard.press("Control+Shift+G")       # generate = check the source on the server
    wait_until(page, "document.getElementById('problemCount').textContent !== '0'")
    problem = page.evaluate("$('#ideProblems').data('problems')[0]")
    assert problem["line"] == 11 and ".fill" in problem["message"]
    markers = page.evaluate("monaco.editor.getModelMarkers({owner: 'prg32'}).map(m => m.startLineNumber)")
    assert markers == [11]
    # Keyboard: F6 to the panel, Tab into it, Tab to the problem, Enter jumps to line 11.
    page.evaluate("PRG32Ide.editors.src.setPosition({lineNumber: 1, column: 1})")
    press_until(page, "F6", lambda focus: focus["region"] == "panel")
    press_until(page, "Tab", lambda focus: focus["tag"] == "BUTTON" and "Line 11" in focus["text"])
    page.keyboard.press("Enter")
    wait_until(page, "PRG32Ide.editors.src.getPosition().lineNumber === 11")
    assert active(page)["inMonaco"]
    context.close()


def test_blocks_stay_editable_and_generated_code_is_read_only(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    page, _ = open_ide(context, live_kit)
    assert page.evaluate("""() => { const ws = PRG32Blocks.getWorkspace(); const n = ws.getAllBlocks(false).length;
        const b = ws.newBlock('prg32_on_start'); b.initSvg(); b.render(); return ws.getAllBlocks(false).length === n + 1; }""")
    for command, tab in (("generated assembly", "gen-asm"), ("game ir", "gen-ir")):
        page.keyboard.press("Control+Shift+P")
        wait_until(page, "document.activeElement.id === 'paletteInput'")
        page.keyboard.type(command)
        page.keyboard.press("Enter")
        wait_until(page, f"!!PRG32Ide.editors['{tab}']")
        assert page.evaluate(f"PRG32Ide.editors['{tab}'].getOption(monaco.editor.EditorOption.readOnly)")
    wait_until(page, "PRG32Ide.editors['gen-asm'].getValue().includes('.globl')")
    # Editor tabs work with the arrow keys.
    page.evaluate("document.querySelector('#ideTabs [role=tab][aria-selected=true]').focus()")
    before = active(page)["id"]
    page.keyboard.press("ArrowLeft")
    assert active(page)["id"] != before and active(page)["role"] == "tab"
    context.close()


def test_small_screens_show_the_files_on_demand(browser, live_kit):  # noqa: F811
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page, _ = open_ide(context, live_kit)
    assert not page.is_visible("#ideTree")
    press_until(page, "Tab", lambda focus: focus["id"] == "ideTreeToggle", limit=40)
    page.keyboard.press("Enter")
    wait_until(page, "document.activeElement.getAttribute('role') === 'treeitem'")
    assert page.is_visible("#ideTree")
    assert page.get_attribute("#ideTreeToggle", "aria-expanded") == "true"
    no_scroll = page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    assert no_scroll, "the IDE scrolls sideways on a phone-sized screen"
    context.close()
