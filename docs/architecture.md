# Architecture

## Overview

PRG32-Construction-Kit uses a deliberately simple pipeline:

```text
Blockly workspace JSON
  -> validated PRG32 game IR
  -> JavaScript simulator
  -> deterministic C generator
  -> PRG32 build command
  -> Cartridge Store bundle
  -> Cartridge Store publish endpoint
```

## Main components

| Component | Location | Role |
| --- | --- | --- |
| Flask app | `prg32_construction_kit/` | Routes, CRUD API, conversion, packaging, publishing. |
| SQLite storage | `data/construction_kit.sqlite` | Projects, sprites, assets, artifacts, builds, publish profiles. |
| Blockly editor | `static/js/blockly_blocks.js` | Custom PRG32 block vocabulary. |
| Online simulator | `static/js/simulator.js` | Browser execution of the game IR. |
| C generator | `prg32_construction_kit/generator.py` | Converts saved Blocks JSON into PRG32 C. |
| Packager | `prg32_construction_kit/packager.py` | Runs PRG32 build command and creates publishing zip bundles. |
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

## Why use an intermediate representation?

The IR lets the web app and backend agree on game meaning without treating C as the only source of truth. It makes the pipeline easier to explain:

```text
block: if left pressed -> change player_x by -3
IR:    {op: "if_button", button: "LEFT", then: [...]}
C:     if (input & PRG32_BTN_LEFT) { player_x += -3; }
JS:    if (keys.LEFT) { state.player_x += -3; }
```

## Build behavior

The app always creates generated C. It only creates real `.prg32` files when the configured PRG32 build command is available and succeeds.
