# ADR-0024: One IDE: run builds, fixed project types, tools as tabs

**Status:** Accepted (2026-10-22). Amends ADR-0013 (IDE shell) and ADR-0023 (guest workspace);
the classic editor is retired.

## Context

The kit had two editors (the classic editor and the IDE), two simulators (a JavaScript Blocks
preview, and the PRG32 core in WebAssembly on the Player page), project types that changed
with a select box, and Sprite Lab and AudioStudio on pages of their own. Students and teachers
asked for one place to work, laid out like a JetBrains IDE, where every game, Blocks, C or
assembly, runs in the real simulator, also without an account.

## Decision

1. **The IDE is the only editor.** `/projects/<id>` redirects to `/ide/<id>`. The classic editor's
   tools (History, Export, Properties, Make a copy, cartridge downloads) are in the IDE's
   Project menu and Build tab.
2. **JetBrains layout:** project files on the left, editor tabs in the centre with the tool window
   below them (Problems, Build, Console, Debug, Git), the simulator on the right. Splitters
   resize the panes; Alt+1, Alt+4 and Alt+9 hide them; the layout is remembered per browser.
   The Console is read-only: there is no shell on the server.
3. **Run builds** (`run_build.py`): Run compiles the project for the browser core (qemu) exactly
   as Compile does (validated source, build sandbox, slot and disk budget, debug information),
   sends the cartridge and its debug maps straight back and keeps nothing: no row, no file.
   Accounts run their saved project (`/api/projects/<id>/run`); guests send theirs
   (`/api/guest/run`, 30 runs an hour per address). Only when the server cannot compile do
   Blocks fall back to the JavaScript preview. **Compile** (cartridges to download or publish)
   still needs an account.
4. **The debugger lives in the IDE:** the Player's debugger is a shared partial driving the same
   player, in the Debug tab.
5. **The project type is fixed** when the project is made (Blocks, C or assembly). A save or a
   history restore that would change it is refused (409 `type_locked`). A Blocks project can be
   **converted once** to C or assembly (`/api/projects/<id>/convert_to`): the generated code,
   explained, becomes the student's; the Blocks version stays in History to download.
6. **Sprite Lab and AudioStudio are tabs of the open project**, in one layout (list, editor,
   properties). The project tree opens them; their menu items choose a project and open its IDE.

## Consequences

- AGENTS.md: guests may make run builds (stateless, limited); building to download, publishing
  and classes still need a sign-in; there is no classic editor.
- Guest notice 1.2 says the server compiles a guest's game to run it and keeps nothing.
- Tests: `tests/test_run_build.py`, `tests/test_project_type.py`, `tests/test_ide_layout_browser.py`.
