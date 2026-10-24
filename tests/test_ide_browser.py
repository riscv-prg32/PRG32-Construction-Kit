"""The IDE in a real browser (refinement phases 2-3, ADR-0013/0014): keyboard-only work, Monaco,
language services, a11y.

Uses Playwright with Chrome (or Playwright's Chromium) against a live kit; skips cleanly without
them. Every workflow below is driven with the keyboard only (no mouse clicks), and axe-core
(tests/vendor, test-only) checks the page for serious or critical accessibility violations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from test_browser_offline import (  # noqa: F401 - fixtures
    Recorder,
    browser,
    live_kit,
    settled,
    sign_in,
    wait_until,
)

ROOT = Path(__file__).resolve().parent.parent
# Monaco's "end of file" key: Cmd+Down on a Mac, Ctrl+End elsewhere.
END_OF_FILE = "Meta+ArrowDown" if sys.platform == "darwin" else "Control+End"
# Monaco's own modifier for chords such as "show hover" (Ctrl+K Ctrl+I): Cmd on a Mac.
MOD = "Meta" if sys.platform == "darwin" else "Control"
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
    settled(page)
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
    # The live check marks exactly the directive, while typing and before any server round trip.
    wait_until(page, "monaco.editor.getModelMarkers({owner: 'prg32-live'}).length > 0")
    live = page.evaluate("monaco.editor.getModelMarkers({owner: 'prg32-live'})"
                         ".map(m => [m.startLineNumber, m.startColumn, m.endColumn, m.code])")
    assert live == [[11, 5, 10, "asm-directive"]]
    page.keyboard.press("Control+Shift+G")       # generate = check the source on the server
    wait_until(page, "PRG32Ide.serverProblems.length > 0")
    problem = page.evaluate("PRG32Ide.serverProblems[0]")
    assert problem["line"] == 11 and ".fill" in problem["message"]
    markers = page.evaluate("monaco.editor.getModelMarkers({owner: 'prg32'}).map(m => m.startLineNumber)")
    assert markers == [11]
    assert page.evaluate("PRG32Ide.problems.length") == 1  # the server's copy of the live problem is not repeated
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


def suggestions(page) -> list[str]:
    """The labels in Monaco's suggestion list that is open now."""
    wait_until(page, "!!document.querySelector('.monaco-editor .suggest-widget.visible .monaco-list-row')")
    return page.evaluate("""Array.from(document.querySelectorAll('.monaco-editor .suggest-widget.visible .monaco-list-row'))
        .map(row => row.getAttribute('aria-label') || row.textContent)""")


def hover_text(page) -> str:
    """Show the hover for the word at the cursor with the keyboard (Ctrl+K Ctrl+I) and read it."""
    page.keyboard.press(f"{MOD}+k")
    page.keyboard.press(f"{MOD}+i")
    wait_until(page, "!!document.querySelector('.monaco-hover:not(.hidden) .hover-contents')")
    return page.evaluate("document.querySelector('.monaco-hover:not(.hidden)').textContent")


def test_c_language_services_work_offline_with_the_keyboard(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    record = Recorder(context, live_kit)
    page, _ = open_ide(context, live_kit, {
        "title": "Kb C", "game_json": {"source_mode": "c", "source_c": C_SOURCE}})
    record.watch(page)
    context.set_offline(True)
    sent = len(record.requests)
    press_until(page, "F6", lambda focus: focus["inMonaco"])
    page.keyboard.press(END_OF_FILE)
    page.keyboard.type("void helper(void) {\n    prg32_gfx_re")
    page.keyboard.press("Control+Space")
    labels = suggestions(page)
    assert any(label.startswith("prg32_gfx_rect") for label in labels), labels
    assert not any("prg32_rgb_led" in label for label in labels)
    page.keyboard.press("Enter")                  # accept: a snippet with the parameter names
    wait_until(page, "PRG32Ide.editors.src.getValue().includes('prg32_gfx_rect(x, y, w, h, color)')")
    # Signature help while typing the arguments.
    page.keyboard.press("Escape")
    line = page.evaluate("PRG32Ide.editors.src.getPosition().lineNumber")
    page.evaluate(f"""PRG32Ide.editors.src.executeEdits('test', [{{range: new monaco.Range({line}, 1, {line}, 200),
        text: ''}}]); PRG32Ide.editors.src.setPosition({{lineNumber: {line}, column: 1}})""")
    page.keyboard.type("    prg32_gfx_rect(1, 2, ")   # "(" and "," open the signature help
    wait_until(page, "!!document.querySelector('.parameter-hints-widget.visible')")
    hint = page.evaluate("document.querySelector('.parameter-hints-widget.visible').textContent")
    assert "int w" in hint and "prg32_gfx_rect" in hint
    page.keyboard.press("Escape")
    page.keyboard.type("3, 4, PRG32_COLOR_RED);\n    prg32_rgb_led_set(1, 2, 3);\n}\n")
    # Hover on a PRG32 name, with the keyboard.
    page.evaluate(f"PRG32Ide.editors.src.setPosition({{lineNumber: {line}, column: 10}})")
    text = hover_text(page)
    assert "void prg32_gfx_rect(int x, int y, int w, int h, uint16_t color)" in text and "Portable PRG32 ABI" in text
    page.keyboard.press("Escape")
    # The resident-firmware call is marked at its exact columns.
    wait_until(page, "monaco.editor.getModelMarkers({owner: 'prg32-live'}).some(m => m.code === 'c-resident-only')")
    marker = page.evaluate("monaco.editor.getModelMarkers({owner: 'prg32-live'}).find(m => m.code === 'c-resident-only')")
    text_line = page.evaluate(f"PRG32Ide.editors.src.getModel().getLineContent({line + 1})")
    column = text_line.index("prg32_rgb_led_set") + 1
    assert (marker["startLineNumber"], marker["startColumn"], marker["endColumn"]) == (line + 1, column, column + 17)
    # F12 goes to the declaration in the read-only prg32.h (portable API).
    page.evaluate(f"PRG32Ide.editors.src.setPosition({{lineNumber: {line}, column: 10}})")
    page.keyboard.press("F12")
    wait_until(page, "!!PRG32Ide.editors['sdk-h'] && document.activeElement.closest('.monaco-editor') !== null")
    at = page.evaluate("[PRG32Ide.editors['sdk-h'].getPosition().lineNumber, "
                       "PRG32Ide.editors['sdk-h'].getModel().getLineContent(PRG32Ide.editors['sdk-h'].getPosition().lineNumber)]")
    assert at[1].startswith("void prg32_gfx_rect(") and at[0] == page.evaluate(
        "PRG32LanguageIndex.c.functions.find(f => f.name === 'prg32_gfx_rect').line")
    assert page.evaluate("PRG32Ide.editors['sdk-h'].getOption(monaco.editor.EditorOption.readOnly)")
    # Nothing asked the server: the only requests are Monaco's own static files (its icon font
    # loads when the suggestion list first draws); the language services make none.
    later = [urlsplit(url).path for url in record.requests[sent:]]
    assert [path for path in later if not path.startswith("/static/vendor/monaco-editor/")] == [], later
    assert record.csp_violations() == []
    context.close()


def test_assembly_language_services(browser, live_kit):  # noqa: F811
    from prg32_construction_kit.source_project import ALLOWED_ASM_DIRECTIVES

    context = browser.new_context()
    page, _ = open_ide(context, live_kit, {
        "title": "Kb Asm", "game_json": {"source_mode": "asm", "source_asm": ASM_SOURCE}})
    context.set_offline(True)
    press_until(page, "F6", lambda focus: focus["inMonaco"])
    page.keyboard.press(END_OF_FILE)
    page.keyboard.type("    .s")
    page.keyboard.press("Control+Space")
    labels = suggestions(page)
    assert labels and labels[0].startswith(".s") and set(labels) <= ALLOWED_ASM_DIRECTIVES, json.dumps(labels)
    offered = page.evaluate("PRG32Language.completions('asm', '    .', {line: 1, column: 6}).items.map(i => i.label)")
    assert set(offered) == ALLOWED_ASM_DIRECTIVES
    page.keyboard.press("Escape")
    source = ASM_SOURCE.replace("kb_asm_draw:\n    ret", "kb_asm_draw:\n    lw a8, 0(sp)\n    call prg32_gfx_clear\n    ret")
    page.evaluate("source => PRG32Ide.editors.src.setValue(source)", source)
    wait_until(page, "monaco.editor.getModelMarkers({owner: 'prg32-live'}).length > 0")
    markers = page.evaluate("monaco.editor.getModelMarkers({owner: 'prg32-live'})")
    assert len(markers) == 1, json.dumps(markers)
    marker = markers[0]
    assert (marker["code"], marker["startLineNumber"], marker["startColumn"], marker["endColumn"]) == ("asm-register", 10, 8, 10)
    page.evaluate("PRG32Ide.editors.src.setPosition({lineNumber: 11, column: 12})")
    text = hover_text(page)
    assert "void prg32_gfx_clear(uint16_t color)" in text and "a0 = color" in text
    page.keyboard.press("Escape")
    page.evaluate("PRG32Ide.editors.src.setPosition({lineNumber: 10, column: 15})")
    assert "stack pointer" in hover_text(page)
    context.close()


def test_the_compiler_check_after_saving_adds_its_problems(browser, live_kit, monkeypatch):  # noqa: F811
    """After a save, the server compiles the saved C (ADR-0014); the compiler's message, which the
    kit's own checks cannot know, appears in Problems at its line. (A stand-in compiler answers
    like gcc here; tests/test_compiler_check.py also runs the real one.)"""
    from test_compiler_check import BROKEN_C, Compiler

    compiler = Compiler()
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", compiler)
    monkeypatch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: True)
    context = browser.new_context()
    page, _ = open_ide(context, live_kit, {"title": "Broken", "game_json": {"source_mode": "c", "source_c": BROKEN_C}})
    assert page.evaluate("PRG32Ide.problems.length") == 0          # the kit's own checks find nothing
    press_until(page, "F6", lambda focus: focus["inMonaco"])
    page.keyboard.press(END_OF_FILE)
    page.keyboard.type("/* saved */\n")
    page.keyboard.press("Control+s")
    wait_until(page, "PRG32Ide.serverProblems.some(p => p.line === 3 && /missing_value/.test(p.message))", timeout=30)
    assert page.evaluate("document.getElementById('statusBuild').textContent") == "Compiler: 1 problem"
    assert page.evaluate("monaco.editor.getModelMarkers({owner: 'prg32'}).map(m => m.startLineNumber)") == [3]
    assert compiler.sources and compiler.sources[-1][1].endswith("/* saved */\n")
    context.close()


def test_a_blocks_project_shows_its_game_py_beside_the_c(browser, live_kit):  # noqa: F811
    """Generated (read-only) has game.py for Blocks (py_generator.py), with its note, Copy and Download."""
    context = browser.new_context()
    page, _ = open_ide(context, live_kit)
    page.click("#ideTree [data-id='gen-py']")
    wait_until(page, "!!document.querySelector('#tab-gen-py[aria-selected=true]')")
    wait_until(page, "PRG32Ide.editors['gen-py'] && PRG32Ide.editors['gen-py'].getValue().includes('import prg32')")
    source = page.evaluate("PRG32Ide.editors['gen-py'].getValue()")
    assert source.startswith('"""Pong: the Blocks program written in PRG32 Python.') and "def update() -> None:" in source
    toolbar = page.locator("#tabpanel-gen-py .ide-editor-toolbar")
    assert "the blocks written in PRG32 Python" in toolbar.locator("span").first.inner_text()
    assert toolbar.locator(".ide-copy").count() == 1 and toolbar.locator(".ide-download").count() == 1
    context.close()
