# The IDE

Open a project and press **Open in IDE** (or **IDE** on the Projects page).
The IDE shows everything about one project at once. The classic editor is
still there (**Classic editor**, top right) and works the same as before.

## What you see

| Part | What it does |
| --- | --- |
| Toolbar | Project type (Blocks, Advanced C, Assembly), **Save**, **Generate**, **Compile**, **Commands**. |
| Files (left) | Your source: the Blocks program, `game.c` or `game.S`. For Blocks also the **generated** `game.c`, `game.S` and `game.ir.json` (read-only), and your sprites. |
| Editor (middle) | One tab per open file. Blocks open in Blockly; C and assembly in a code editor with colours, suggestions and help (see below). Generated files have a **Copy** button. |
| Panels (bottom) | **Problems** (click or press Enter on one to jump to its line), **Output** (the compiler's log), **Blocks preview**, **Run & debug** (after Compile: run the real cartridge in the Player, and debug it by block, by line or by instruction: lesson 7). |
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

## Help while you type (C and assembly)

| Keys | What you get |
| --- | --- |
| Ctrl+Space | Suggestions: PRG32 functions, constants and types in C; instructions, registers, directives and PRG32 functions in assembly. |
| Ctrl+K Ctrl+I | What the word under the cursor is: a function's signature and what it does, a register's role, a directive's syntax. |
| Typing `(` or `,` | The function's parameters, with the one you are writing highlighted. |
| F12 | Go to the declaration: PRG32 names open **prg32.h (portable API)**, a read-only list of everything a cartridge can call; your own functions and labels jump inside your file. |

Problems are underlined **while you type**, at the exact words, and listed in
**Problems** with a short explanation. The kit only suggests what it accepts:
the headers `prg32.h`, `prg32_audio.h`, `stdint.h`, `stddef.h`, `stdbool.h`; the
allowed assembly directives; and the **portable** PRG32 functions. Some
functions in the PRG32 SDK belong to the console's firmware only: the editor
marks them, because a cartridge that calls them cannot be built.

All of this works without a network connection. The server still checks the
source on Generate and Compile, so nothing unsafe is let through.

**The compiler check.** Each time you save C or assembly (Ctrl+S, or the
autosave), the server also compiles and links the saved file with the real PRG32
compiler, the way Compile does, but keeps nothing. The compiler's messages join
**Problems** at their lines, for example a name you never declared, which the
editor's own checks cannot know. The status bar says `Compiler: no problems` or how
many it found. **Check with the compiler** in the command palette runs it on
demand. It needs a server with the PRG32 toolchain; without one it says so and
changes nothing.

On a Mac, Cmd works where Ctrl is written. In the code editor, Tab inserts a
tab; use F6 to leave the editor (or Ctrl+M, Monaco's own "Tab moves focus").

## For teachers

- The Blocks program is still the real source of a Blocks project; the C and
  assembly next to it are generated and cannot be edited there.
- Problems come from the kit's own checks and from the compiler; nothing is
  sent anywhere else, and no code runs in the browser except the kit's own.
- On a phone-sized screen the file list opens with the **Files** button.
- Suggestions and help come from a file made from the PRG32 SDK
  (`tools/build_language_index.py`); after updating the SDK, regenerate it.

## For contributors

The IDE is tested in a real browser with the keyboard only, at desktop and phone
size, with an accessibility scan (a session with a real screen reader is described in
`accessibility_session.md`; none has been recorded yet). On your computer:

```
python3 -m pip install -r requirements-browser.txt
python3 -m pytest -q -rs tests/test_ide_browser.py
```

Without Playwright or Chrome the tests skip. The CI browser job runs them on every
push and pull request with `PRG32_REQUIRE_BROWSER=1`, where a skip becomes a failure.

Design records: `adr/0013-ide-shell-and-monaco.md`, `adr/0014-ide-language-services.md`.
