# ADR-0013: IDE shell with Monaco, on Bootstrap + jQuery

**Status:** Accepted (2026-10-19, refinement phase 2)

## Context

The editor page was a Bootstrap layout with Blockly and plain textareas for
C and assembly (audit IDE-01/03/04). `AGENTS.md` requires Bootstrap, jQuery
and Blockly; the briefs allow Monaco as the code editor but no second
application framework.

## Decision

1. A new page, `/ide/<project_id>` (`templates/ide.html`), next to the
   classic editor (kept as the simple fallback):
   toolbar · project tree · editor tabs · panels (Problems, Output, Blocks
   preview, Run & debug) · status bar, laid out with CSS grid. Below 992 px
   the tree becomes a slide-in panel (Files button, Alt+0).
2. Plain jQuery modules: `static/js/ide/shell.js` (regions, ARIA tree with
   roving tabindex, tab lists, command palette, shortcuts; no project
   knowledge) and `static/js/ide/ide.js` (project files, Save/Generate/
   Compile on the existing API, problems and markers).
3. **Monaco 0.52.2** (MIT), vendored like the other libraries (ADR-0012),
   pruned to the editor core, its worker, the codicon font and the C grammar.
   0.52.2 is the last release with the classic AMD build; later releases do
   not add CSP nonce support either. A Monarch grammar `prg32-asm`
   (`static/js/ide/monaco_setup.js`) covers RV32IMC instructions, registers
   and exactly the directives `validate_asm_source` allows; a test keeps the
   two lists equal.
4. **Blockly stays the editable source** of Blocks projects; generated C,
   assembly and IR open as read-only Monaco tabs with a Copy button.
5. **Keyboard model:** F6/Shift+F6 between regions; tree arrows/Home/End/
   Enter; tab lists arrows/Home/End/Delete; Ctrl+Shift+P or F1 command
   palette (combobox + listbox); Ctrl+S, Ctrl+Shift+G (generate/check),
   Ctrl+Shift+B (compile). Problems are buttons; Enter jumps to the line.
6. **CSP:** Monaco creates `<style>` elements and writes code lines as HTML
   with `style` attributes. `static/js/csp_nonce.js` stamps a per-response
   nonce on every `<style>` a library creates, so `style-src-elem` stays
   `'self'` + nonce (+ Blockly's hashes). Only on `/ide/` pages,
   `style-src-attr 'unsafe-inline'` allows style *attributes*, which cannot
   run script. Scripts remain `'self'` only, workers same-origin.
7. Game keys in the Blocks preview and the Player now act only while the game
   screen has the focus (it takes the focus on Play). Before, they were taken
   from the whole window, which stopped Enter from activating buttons and the
   arrows from moving in lists (also in the classic editor).

## Consequences

- Language services (completion, SDK-aware diagnostics, navigation) came in
  refinement phase 3 (ADR-0014); this phase gave syntax colouring, server
  diagnostics as markers, and keyboard-complete editing.
- Browser tests (`tests/test_ide_browser.py`) cover the keyboard-only C and
  assembly workflows, Blocks/generated views, small screens and an axe-core
  scan (no serious/critical violations). No screen-reader session has been run.
  The CI browser job runs them on every push and pull request with
  `PRG32_REQUIRE_BROWSER=1`, so a missing browser fails the job instead of
  skipping, and uploads `browser-test-results.xml`.
