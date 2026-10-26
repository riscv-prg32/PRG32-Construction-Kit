# PRG32-Construction-Kit Documentation

PRG32-Construction-Kit is a classroom web application for making PRG32 games with Blocks, C or RISC-V assembly: an IDE with real compiler messages, real `.prg32` cartridges, a WebAssembly runtime with a source and block debugger, Sprite Lab, AudioStudio, accounts with school sign-in, optional cloud copies, and Cartridge Store publishing.

## Read in this order

1. `setup.md` - local Python setup.
2. `docker.md` - container execution.
   - `install_cartridge_build.md` - install with real `.prg32` builds switched on (Docker, macOS, Linux, Windows).
3. `ci_cd.md` - automated tests, real-cartridge checks and published container images.
4. `architecture.md` - components, trust boundaries, the build pipeline and personal-data flows (with diagrams).
   - `ide.md` - the IDE: Blocks, Advanced C and assembly, compiler messages, debugging.
   - `wasm_runtime.md` - running and debugging real cartridges in the browser, and its limits.
   - `privacy/README.md` - personal data, for the school that runs the kit: records, notices, rights, incidents.
   - `release_checklist.md` - what a person checks before a release; `figures/manifest.json` lists every picture.
5. `blockly.md` - block vocabulary, expressions and JSON storage.
   - `prg32_feature_coverage.md` - which PRG32 services Blocks, the simulator and Advanced C reach.
6. `sprite_editor.md` - sprite/image editor guide.
7. `cartridge_build.md` - generated C and PRG32 build hooks.
   - `generated_code.md` - reading the explained C and RISC-V assembly made from the blocks.
   - `concurrent_builds.md` - many students building at the same time.
   - `videos/snake-workflow-demo.mov` - short screen recording of the Snake workflow.
8. `cartridge_store_publish.md` - publishing bundles.
   - `audio_engine.md` - how PRG32 games sound: 8 voices, ADSR, stereo, and how the browser matches the console.
   - `deploy.md` - the Deploy tool: a compiled cartridge onto a PRG32 console, PRG32-QT or QEMU, checked step by step.
   - `external_gates.md` - what only the school, other repositories, a real console or real accounts can close, and the evidence that closes each.
   - `evaluate.md` - the Evaluate tool: one versioned performance protocol on the three targets, raw data, statistics and charts.
   - `delivery.md` - getting a game onto a PRG32 console or PRG32-QT, and recording that it worked.
   - `backup_restore.md` - backing up the kit, restoring it into a clean folder, and the restore drill.
   - `dependencies.md` - the dependency lock, the SBOM and how security updates are handled.
   - `performance.md` - how fast the kit must be on classroom computers.
   - `accessibility_session.md` - how to run and record a keyboard and screen-reader session.
   - `store_contract.md` - the shared Store contract: what the Store accepts, what its refusals mean, and how it is tested.
9. `api.md` - CRUD and action API.
   - `accounts_and_sso.md` - accounts, school sign-in (OIDC with PKCE), who sees what, and sharing users with a Cartridge Store.
   - `classes_and_roles.md` - classes, teachers, facilitators and students: who reads whose work.
   - `identity_live_testing.md` - testing school sign-in against Keycloak or your institution's provider.
   - `live_testing.md` - every live test (Store, sign-in, cloud, QEMU) in one step, with no secrets kept.
   - `storage.md` - where games are kept: autosave, conflicts, quotas, retention, and guest games in the browser.
   - `guest_mode.md` - using the kit without an account: what works, what needs a sign-in, moving games in.
   - `cloud_storage.md` - keeping projects in Google Drive or OneDrive (optional).
   - `github.md` - committing a project to a GitHub repository, pulling it back (optional).
10. `tutorials/` - step-by-step lessons.
   - `tutorials/games/` - five complete classic-inspired games with slide decks
     (`presentations/*.html`).
   - `runtime_check.md` - building the examples and running them on QEMU and PRG32-QT.
11. `../examples/textbook/` - 36 C and RISC-V assembly textbook examples.
12. `project_archive.md` - saving, sharing and importing a whole project as one zip file.
   - `project_history.md` - History (earlier versions) and Recently deleted.
13. `handwritten_assembly.md` - writing a cartridge directly in RISC-V assembly.
   - `python_language.md` - PRG32 Python: the small, typed Python the kit compiles into C and assembly.
   - `tutorials/09_python.md` - your first game in PRG32 Python.
   - `i18n.md` - the five interface languages, and the quick start in each
     (`tutorials/quickstart.en.md`, `.it`, `.es`, `.fr`, `.de`).
14. `build_provenance.md` - what made each cartridge (versions, settings, SHA-256 fingerprints).
15. `wasm_runtime.md` - the Player: real cartridges running in the browser (PRG32-QT core as WebAssembly).
   - `tutorials/07_debugger.md` - the Player's RISC-V debugger (steps, breakpoints, registers, memory).
16. `offline.md` - what works without the server, and why nothing signed-in is stored offline.
17. `ide.md` - the IDE: files, tabs, panels, command palette and keyboard shortcuts.
18. `audio_studio.md` - AudioStudio: instruments, sound effects, soundtracks and samples.
   - `tutorials/08_audio_studio.md` - a sound effect and a tune for your game.
   - `audio_engine.md` - the 8-voice PRG32 sound engine and how it is checked.
   - `hardware_audio_check.md` - checking the sound on a real PRG32 console (I2S capture or microphones).
   - `upstream/README.md` - changes the kit proposes to the PRG32 SDK, PRG32-QT and the Cartridge Store.
19. `reproducing.md` - running every toolchain check with Docker only (for reviewers and auditors).

## Full-IDE roadmap

- `user-guide.md` and `admin-guide.md` - where to start as a student/teacher or as an administrator.
- `admin_settings.md` - the admin Settings page: what each tab changes and which server variable locks it.
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
