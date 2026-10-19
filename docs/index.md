# PRG32-Construction-Kit Documentation

PRG32-Construction-Kit is a classroom web application for building PRG32 games with blocks, sprites, simulation, generated C, cartridge bundles, and Cartridge Store publishing.

## Read in this order

1. `setup.md` - local Python setup.
2. `docker.md` - container execution.
   - `install_cartridge_build.md` - install with real `.prg32` builds switched on (Docker, macOS, Linux, Windows).
3. `ci_cd.md` - automated tests, real-cartridge checks and published container images.
4. `architecture.md` - how the system is organized.
5. `blockly.md` - block vocabulary, expressions and JSON storage.
   - `prg32_feature_coverage.md` - which PRG32 services Blocks, the simulator and Advanced C reach.
6. `sprite_editor.md` - sprite/image editor guide.
7. `cartridge_build.md` - generated C and PRG32 build hooks.
   - `generated_code.md` - reading the explained C and RISC-V assembly made from the blocks.
   - `concurrent_builds.md` - many students building at the same time.
   - `videos/snake-workflow-demo.mov` - short screen recording of the Snake workflow.
8. `cartridge_store_publish.md` - publishing bundles.
9. `api.md` - CRUD and action API.
   - `accounts_and_sso.md` - accounts, who sees what, and sharing users with a Cartridge Store.
10. `tutorials/` - step-by-step lessons.
   - `tutorials/games/` - five complete classic-inspired games with slide decks
     (`presentations/*.html`).
   - `runtime_check.md` - building the examples and running them on QEMU and PRG32-QT.
11. `../examples/textbook/` - 36 C and RISC-V assembly textbook examples.
12. `project_archive.md` - saving, sharing and importing a whole project as one zip file.
   - `project_history.md` - History (earlier versions) and Recently deleted.
13. `handwritten_assembly.md` - writing a cartridge directly in RISC-V assembly.
14. `build_provenance.md` - what made each cartridge (versions, settings, SHA-256 fingerprints).
15. `wasm_runtime.md` - the Player: real cartridges running in the browser (PRG32-QT core as WebAssembly).
   - `tutorials/07_debugger.md` - the Player's RISC-V debugger (steps, breakpoints, registers, memory).
16. `offline.md` - what works without the server, and why nothing signed-in is stored offline.
17. `ide.md` - the IDE: files, tabs, panels, command palette and keyboard shortcuts.

## Full-IDE roadmap

- `user-guide.md` and `admin-guide.md` - where to start as a student/teacher or as an administrator.
- `architecture/current-state.md` - what the PRG32 repositories contain today (capability matrix).
- `implementation-plan.md` - phased plan (gates G0-G8); `adr/` - decisions.
- `implementation-status.md`, `traceability.md` - progress and evidence per requirement.
- `capabilities.md` - machine-checked status table (every claim names its source symbol and test).
- `evidence.md` - how the evidence is made: CI jobs, generated files and their checks, cartridge/debug identity.
- `briefs/` - the design baseline and the briefs that refine it (ADR-0011).
- `compatibility.md`, `security.md`, `deployment.md`, `release-notes.md`.

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
