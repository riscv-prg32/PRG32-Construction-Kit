# Cartridge Build Guide

## What the app generates

When a student clicks **Generate C**, the app converts Blocks JSON to game IR and then deterministic C.

Generated C exports three functions:

```c
void my_game_init(void);
void my_game_update(void);
void my_game_draw(void);
```

The function prefix comes from the project title, sanitized as a C identifier.

## Prepare Cartridge

When a student clicks **Prepare Cartridge**, the app:

1. saves the Blockly JSON;
2. regenerates C;
3. creates a build record;
4. writes `game.c`, `project.blocks.json`, and `game.ir.json` to `data/builds/<build_id>/`;
5. runs the configured PRG32 build command for `esp32c6` and `qemu` labels;
6. creates a Cartridge Store bundle zip.

## PRG32 build command

Default:

```bash
python3 -m prg32 build
```

The app appends:

```text
game.c --portable --entry-prefix <prefix> --name <slug> --out <slug>-<architecture>.prg32
```

Override the command:

```bash
export PRG32_BUILD_COMMAND="python3 -m prg32 build"
```

## Source-only bundles

If the toolchain is missing, the bundle is marked `source-only` and includes:

- `manifest.json`
- `icon.png`
- `source/game.c`
- `source/project.blocks.json`
- `source/game.ir.json`
- `BUILD_TOOLCHAIN_REQUIRED.txt`

This is useful for teaching conversion even on laptops that cannot build cartridges.

## Publishable bundles

If one or more `.prg32` files are produced, the manifest includes architecture entries and the bundle is marked publishable.
