# Architecture

## Persistence

All CRUD operations use SQLAlchemy models. SQLite is selected automatically for
local and classroom installations; `DATABASE_URL` can select any supported
SQLAlchemy database. PostgreSQL with the `psycopg` driver is recommended for
production concurrency. JSON-shaped fields remain JSON text columns so the
existing API format and SQLite schema stay compatible.

SQLite connections use foreign-key enforcement, WAL mode, and a five-second
busy timeout. These improve small classroom concurrency but do not turn SQLite
into a multi-server production database.

## Overview

PRG32-Construction-Kit uses a deliberately simple pipeline:

```text
Blockly workspace JSON
  -> validated PRG32 game IR
  -> JavaScript simulator
  -> deterministic C generator (and, on request, RISC-V assembly generator)
  -> PRG32 build command
  -> Cartridge Store bundle
  -> Cartridge Store publish endpoint
```

## Main components

| Component | Location | Role |
| --- | --- | --- |
| Flask app | `prg32_construction_kit/` | Routes, CRUD API, conversion, packaging, publishing. |
| SQLAlchemy storage | `prg32_construction_kit/db.py` | Database-neutral models and CRUD for projects, sprites, assets, artifacts, builds, and publish profiles. |
| Blockly editor | `static/js/blockly_blocks.js` | Custom PRG32 block vocabulary. |
| Online simulator | `static/js/simulator.js` | Browser execution of the game IR on a 320 x 200 RGB565 framebuffer. |
| Expression checker | `prg32_construction_kit/expressions.py` | Grammar of block text fields: integers, variables, list items, kit functions, PRG32 constants. |
| C generator | `prg32_construction_kit/generator.py` | Converts saved Blocks JSON into PRG32 C, adding only the helpers a game uses. |
| Assembly generator | `prg32_construction_kit/asm_generator.py` | Converts the same game IR into explained RISC-V (RV32IM) assembly that does exactly what the C does. |
| Example games | `examples/games/`, `tools/build_example_games.py` | Five complete Blocks games and the script that writes them. |
| Tutorials | `docs/tutorials/games/`, `tools/build_presentations.py` | Step-by-step decks whose block and C excerpts are generated from the games. |
| Runtime check | `tools/runtime_check.py`, `tools/simulate.js` | Builds examples and runs them in the simulator, QEMU and PRG32-QT. |
| Packager | `prg32_construction_kit/packager.py` | Runs PRG32 build command for all or selected architectures and creates publishing zip bundles. |
| Publisher | `prg32_construction_kit/publisher.py` | Sends bundle to Cartridge Store. |

## Storage model

The app uses CRUD resources:

- projects
- sprites
- assets
- artifacts
- builds
- publish profiles

The most important field is `projects.blocks_json`. It stores the Blockly workspace serialization exactly as JSON. Generated C and bundles are artifacts.
An advanced C project stores its explicitly authored source in
`projects.game_json.source_c` with `source_mode: "c"`; this uses the existing
JSON column, so older SQLite databases need no schema migration. Converting or
packaging that project retains and builds the saved C instead of regenerating
it from Blocks. The browser simulator remains specific to Blocks projects.

## Why use an intermediate representation?

The IR lets the web app and backend agree on game meaning without treating C as the only source of truth. It makes the pipeline easier to explain:

```text
block: if left pressed -> change player_x by -3
IR:    {op: "if_button", button: "LEFT", then: [...]}
C:     if (input & PRG32_BTN_LEFT) { player_x += -3; }
JS:    if (keys.LEFT) { state.player_x += -3; }
```

## Game IR 1.1

The IR (`prg32-construction-kit-game-1.1`) lists the game's variables,
lists, required PRG32 features and three statement lists. Statements are
small JSON objects (`set`, `if`, `repeat`, `list_set`, `line`, `playfield_put`,
...) whose expression fields are already checked and normalized. Python
(`generator.py`) and JavaScript (`simulator.js`) build the same IR from the
same Blocks JSON; the tests compare them for every example and for one block of
every toolbox type.

The generated C is freestanding: no libc, no floating point, no dynamic
memory. Lists are `static int` arrays accessed through bounds-checked
helpers, `repeat` loops have a hidden counter capped at 1024 iterations, and
integer division follows the RISC-V rules (no trap on division by zero) in
both the C and the simulator: division by anything other than a fixed number
goes through the `prg32_kit_div` / `prg32_kit_mod` helpers, so the C never
relies on undefined behaviour. Helpers are emitted only when the game uses
them, so the generated C compiles cleanly with `-Wall -Wextra`.

Artifact downloads and publishing only read files inside `BUILD_ROOT` and
`ARTIFACT_ROOT`, and never the SQLite database (it holds publish bearer
tokens), even if an artifact row points at it.

## Build behavior

Blocks projects create generated C. Advanced C projects build the saved source
after checking its permitted includes and required lifecycle entry points.
Both produce real `.prg32` files only when the configured PRG32 build command
is available and succeeds. The editor's **Download .prg32** button asks the
package action for a single architecture and downloads the resulting
`prg32_cartridge` artifact; the C source and build log are still stored. C compilation is intended for trusted classroom
installations; source validation is not an OS sandbox.
