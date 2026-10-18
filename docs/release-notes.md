# Release notes

## Unreleased

### Added

- Portable project archive: **Export → Project archive (.zip)** in the
  editor, `GET /api/projects/<id>/archive`. Holds `prg32.project.json`
  (schema 1), the source, sprites and assets; byte-identical for the same
  project.
- **Import project** on the dashboard accepts archives as well as JSON.
- `GET /api/projects/<id>/manifest` and `POST /api/projects/<id>/duplicate`.
- Full-IDE planning documents: current-state matrix, ADRs, plan, status,
  traceability, compatibility, security, deployment, user and admin guides.

- **Assembly (RISC-V)** editor mode: write a cartridge in handwritten
  assembly. It is checked against a directive allow-list and then built by
  the PRG32 toolchain (ADR-0004, `handwritten_assembly.md`). Archives store it
  as `src/game.S` with `authoring_mode: "assembly"`.

### Changed

- **Make my copy** now copies a shared project on the server, including its
  sprites and assets (it used to copy the blocks only).
- Importing an old single-file JSON export goes through the project-format
  migration. The game IR stored in that file is no longer copied; it is
  derived and is made again on the next convert or build.
- Service worker cache `prg32-kit-v6`.

### Migration

No database changes. Old exports keep importing.
