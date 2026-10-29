# ADR-0029: Project art in code, by name, in every kind of project

**Status:** Accepted (2026-10-29). Amends ADR-0004 (one more allowed line in handwritten assembly)
and builds on ADR-0021 and ADR-0026.

## Context

Sprite Lab, Backgrounds and AudioStudio keep a project's art as data. Blocks could already play
AudioStudio sounds by name, but no project could draw its own sprites or backgrounds without
copying the C made by **Convert to C** into the code by hand, and an assembly or Python project
could not use them at all. A copy goes stale when the art changes, and the PRG32 builder compiles
exactly one source file, so the art cannot be a second file next to the game.

## Decision

1. **Art is used by name, the same way everywhere** (`project_assets.py`, docs/project_art.md).
   `project_assets.catalog` turns a project's sprites, backgrounds and AudioStudio document into
   pieces with a fixed C name each (`rocket_draw`, `sky_load`, `sfx_coin`, `TRACK_THEME`), in a
   fixed order, so the same art always gives the same code.
2. **Blocks and PRG32 Python carry the art in the IR.** Three blocks (draw sprite, load
   background, draw background) and `prg32.sprite`, `prg32.background_load`,
   `prg32.background_draw` become IR operations; `game_ir["assets"]` holds exactly the art they
   use. The C and assembly generators write the same functions from it, and the browser
   simulator draws from it. A name that is not in the project is a warning (Blocks) or an error
   on its line (Python), never a guess.
3. **C and assembly write one include line** (`#include "prg32_assets.h"` / `"prg32_assets.S"`).
   It names no file. The validators accept exactly that line and still refuse every other
   include; the server writes the art in its place, **on that same line**, only in the text given
   to the compiler. Line numbers, compiler messages and the debugger therefore stay on the
   student's lines, and the saved source never changes. The replacement has no comments, `#`
   lines or `//`, so an include inside a comment cannot change what the compiler reads. In
   assembly it uses `.pushsection`/`.popsection` so the student's current section is kept.
4. **Addresses only in code.** An indexed sprite's descriptor is filled in on the stack when it
   is drawn, since a cartridge may be loaded anywhere and the portable format has no data
   relocations.
5. **The tools say how to use the art.** Sprite Lab, Backgrounds and AudioStudio show the line
   for Blocks, PRG32 Python, C and assembly (`GET /api/projects/<id>/art`, `usage`), and the IDE
   shows `prg32_assets.h`/`.S` read-only under **Project art**. Converting a Blocks game to C or
   assembly writes the include line, so the converted game keeps following the tools.

## Consequences

- Star Catcher exists in all four languages with the same art (`examples/art/`); the four
  cartridges draw identical frames in `prg32qt-headless` (`tests/test_project_assets.py`).
- The assembly allow-list grows by one exact line, proven unable to read files by tests that
  refuse every variant (a comment after it, `.include`, `.incbin`, `include_next`, other names).
- A C or assembly game that includes the art compiles all of the project's art, even pictures it
  does not draw; Blocks and Python compile only what they use.
- Guests send their sprites and backgrounds with each request that turns a game into code; the
  server stores none of it (ADR-0023).
