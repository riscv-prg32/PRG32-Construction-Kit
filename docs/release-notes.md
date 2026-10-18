# Release notes

## Unreleased

### Added

- Portable project archive: **Export → Project archive (.zip)** in the
  editor, `GET /api/projects/<id>/archive`. Holds `prg32.project.json`
  (schema 1), the source, sprites and assets; byte-identical for the same
  project.
- **Import project** on the dashboard accepts archives as well as JSON.
- `GET /api/projects/<id>/manifest` and `POST /api/projects/<id>/duplicate`.
- **History** in the editor: every save that changes the blocks or the
  Advanced C keeps the version before it. Restore one (the current version
  is kept first) or download it as a project archive. Newest 50 per project
  (`PRG32_KIT_MAX_REVISIONS`). API: `/api/projects/<id>/revisions...`.
- **Recently deleted** on the dashboard: deleting a project hides it instead
  of removing it; restore it from there (`POST /api/projects/<id>/restore`,
  `GET /api/projects?deleted=1`). Admins can delete for good
  (`DELETE /api/projects/<id>?purge=1`).
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
- `DELETE /api/projects/<id>` keeps its answer but now moves the project to
  Recently deleted. Project items include `deleted_at`.
- Service worker cache `prg32-kit-v7`.

### Migration

New table `project_revisions` and new column `projects.deleted_at`, added
automatically and idempotently on start; existing databases keep working.
Old exports keep importing.
