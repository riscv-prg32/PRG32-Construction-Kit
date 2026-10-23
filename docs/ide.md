# The IDE

The IDE is where you make a game. Open a project on the Projects page (**Open**), or make
one with **New Project**: choose **Blocks**, **C**, **Assembly (RISC-V)** or **Python (PRG32
Python)**. It is laid out
like a JetBrains IDE (ADR-0024):

| Part | What it does |
| --- | --- |
| Toolbar | The project's name and type, **Project** menu, **Save**, **Run**, **Generate**, **Compile**, **Commands**, and buttons to show or hide the side panes. |
| Files (left) | Your source: the Blocks program, `game.c`, `game.S` or `game.py`. For Blocks and Python also the **generated** `game.c`, `game.S` and `game.ir.json` (read-only, with **Copy** and **Download**). **Sprites** and **Sound** open Sprite Lab and AudioStudio. |
| Editor (centre) | One tab per open file or tool. Blocks open in Blockly; C, assembly and PRG32 Python in a code editor with colours, suggestions and help (see below); Sprite Lab and AudioStudio as tabs of this project. |
| Tool window (below the editor) | **Problems** (Enter on one jumps to its line), **Build** (the build log and the cartridge downloads), **Console** (what the kit did, read-only), **Debug** (stop at a block, a line or an instruction: lesson 7), **Git** (the project on GitHub: `github.md`). |
| Simulator (right) | **Run** builds your game and plays it here, in the PRG32 core compiled to WebAssembly: Blocks, C, assembly and Python alike, also without an account. Play/Pause, Frame, Restart, speed, sound and on-screen buttons. |
| Status bar | Project type, saved or not, cursor line/column, build result. |

Drag the lines between the panes to resize them, or move them with the arrow keys; the IDE
remembers the layout in this browser.

## The project type

A project is **Blocks**, **C**, **Assembly** or **Python**, chosen when you make it, and it stays that way.
A Blocks project can become C or assembly **once**: **Project, Convert to C…** (or **to
Assembly…**). The blocks become code, explained line by line, and from then on you change the
code. It cannot be undone; the Blocks version stays in **History**, where you can download it.

## The Project menu

**Properties…** (title, author, summary, tags; for C and assembly the PRG32 features the
cartridge needs), **History…** (go back to an earlier version, or download it), **Export
project** (.zip or JSON), **Make a copy**, and for Blocks **Convert to C…** and **Convert to
Assembly…**. A shared classroom project opens read-only, with **Make my copy**.

## Keyboard

| Keys | Action |
| --- | --- |
| F6 / Shift+F6 | Next / previous area: toolbar, files, editor, tool window, simulator |
| Arrow keys, Home, End, Enter | Move in the file list and open a file |
| Left / Right | Next / previous tab (in the tab bar) |
| Delete | Close the tab (in the tab bar) |
| Ctrl+Shift+P or F1 | Command palette: type, arrows, Enter |
| Ctrl+S | Save |
| Shift+F10 | Run in the simulator |
| Ctrl+Shift+G | Generate (for C and assembly: check the source) |
| Ctrl+Shift+B | Compile the cartridges to download (needs an account) |
| Alt+1 / Alt+4 / Alt+9 | Show / hide the files, the tool window, the simulator |
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
