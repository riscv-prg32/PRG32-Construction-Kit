# The IDE

Open a project and press **Open in IDE** (or **IDE** on the Projects page).
The IDE shows everything about one project at once. The classic editor is
still there (**Classic editor**, top right) and works the same as before.

## What you see

| Part | What it does |
| --- | --- |
| Toolbar | Project type (Blocks, Advanced C, Assembly), **Save**, **Generate**, **Compile**, **Commands**. |
| Files (left) | Your source: the Blocks program, `game.c` or `game.S`. For Blocks also the **generated** `game.c`, `game.S` and `game.ir.json` (read-only), and your sprites. |
| Editor (middle) | One tab per open file. Blocks open in Blockly; C and assembly in a code editor with colours. Generated files have a **Copy** button. |
| Panels (bottom) | **Problems** (click or press Enter on one to jump to its line), **Output** (the compiler's log), **Blocks preview**, **Run & debug** (after Compile: run the real cartridge in the Player). |
| Status bar | Project type, saved or not, cursor line/column, build result. |

## Keyboard

| Keys | Action |
| --- | --- |
| F6 / Shift+F6 | Next / previous area: toolbar, files, editor, panels |
| Arrow keys, Home, End, Enter | Move in the file list and open a file |
| Left / Right | Next / previous tab (in the tab bar) |
| Delete | Close the tab (in the tab bar) |
| Ctrl+Shift+P or F1 | Command palette: type, arrows, Enter |
| Ctrl+S | Save |
| Ctrl+Shift+G | Generate (for C and assembly: check the source) |
| Ctrl+Shift+B | Compile the cartridge |
| Alt+0 | Show / hide the files on a small screen |

On a Mac, Cmd works where Ctrl is written. In the code editor, Tab inserts a
tab; use F6 to leave the editor (or Ctrl+M, Monaco's own "Tab moves focus").

## For teachers

- The Blocks program is still the real source of a Blocks project; the C and
  assembly next to it are generated and cannot be edited there.
- Problems come from the kit's own checks and from the compiler; nothing is
  sent anywhere else, and no code runs in the browser except the kit's own.
- On a phone-sized screen the file list opens with the **Files** button.

## For contributors

The IDE is tested in a real browser with the keyboard only, at desktop and phone
size, with an accessibility scan. On your computer:

```
python3 -m pip install -r requirements-browser.txt
python3 -m pytest -q -rs tests/test_ide_browser.py
```

Without Playwright or Chrome the tests skip. The CI browser job runs them on every
push and pull request with `PRG32_REQUIRE_BROWSER=1`, where a skip becomes a failure.

Design record: `adr/0013-ide-shell-and-monaco.md`.
