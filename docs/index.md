# PRG32-Construction-Kit Documentation

PRG32-Construction-Kit is a classroom web application for building PRG32 games with blocks, sprites, simulation, generated C, cartridge bundles, and Cartridge Store publishing.

## Read in this order

1. `setup.md` - local Python setup.
2. `docker.md` - container execution.
3. `architecture.md` - how the system is organized.
4. `blockly.md` - block vocabulary, expressions and JSON storage.
   - `prg32_feature_coverage.md` - which PRG32 services Blocks, the simulator and Advanced C reach.
5. `sprite_editor.md` - sprite/image editor guide.
6. `cartridge_build.md` - generated C and PRG32 build hooks.
   - `concurrent_builds.md` - many students building at the same time.
7. `cartridge_store_publish.md` - publishing bundles.
8. `api.md` - CRUD and action API.
9. `tutorials/` - step-by-step lessons.
   - `tutorials/games/` - five complete classic-inspired games with slide decks
     (`presentations/*.html`).
   - `runtime_check.md` - building the examples and running them on QEMU and PRG32-QT.
10. `../examples/textbook/` - 36 C and RISC-V assembly textbook examples.

## Classroom workflow

```text
Create project
  -> Build with blocks
  -> Save Blocks JSON
  -> Play/debug in browser
  -> Generate PRG32 C
  -> Download a .prg32 cartridge or prepare a cartridge bundle
  -> Publish to Cartridge Store
```
