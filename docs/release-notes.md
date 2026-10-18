# Release notes

## Unreleased

### Security: Store egress policy (audit H-01)

- Bundles are only sent to Cartridge Stores the administrator approved
  (`PRG32_STORE_ALLOWED_ORIGINS`, default: `PRG32_STORE_URL` and
  `PRG32_SSO_PEER_URL`), over https, to public addresses, with the
  connection pinned to the checked address, no redirects, timeouts and a
  bounded answer (ADR-0008).
- Publish profiles with other addresses are refused (`400`); errors no longer
  echo exception text or Store bodies; the result has a new safe shape.
- **Upgrade note:** a Store on a private network or `http://127.0.0.1` now
  needs `PRG32_STORE_TRUSTED_LOCAL=1` (and plain http a non-production
  server). Existing profiles for other Stores stay listed but are refused at
  publish time until the Store is approved. No database change; rollback is a
  plain code revert.

### Debugger in the Player (G5, first slice)

- **Debugger** card on `/player`: Debug mode switch, Continue/Pause, Step
  (one instruction), Step over, Step out, Step frame, speeds 0.01×–4×
  (PRG32-QT's list), breakpoints in the disassembly gutter (remembered per
  cartridge), x0–x31 with ABI names and changed values highlighted, PC and
  update/draw phase, disassembly following the PC with Init/Update/Draw/PC
  views and go-to-address, a 128–1024 byte memory view (decimal or `0x`
  address), game time vs real time. **Beginner** and **Advanced** views
  share one state. Lesson: `docs/tutorials/07_debugger.md`.
- The core's C interface gains breakpoints, an instrumented run with an
  instruction budget, PRG32-QT's resume rule, step over/out and
  disassembly; native and WebAssembly builds are tested to step identically.
  `static/wasm/` rebuilt (≈ 145 KB) from the same PRG32-QT commit.
- JavaScript protocol uses PRG32-QT's `/api/debug` commands and state names
  (ADR-0006 accepted).
- Service worker cache `prg32-kit-v11`. No database changes.

### Browser PRG32 core (G4)

- **Player** page (`/player`) and **Play in browser** after a compile: real
  `.prg32` cartridges run in the browser on PRG32-QT's core compiled to
  WebAssembly (`static/wasm/`, ≈ 125 KB, cached for offline use).
- `tools/build_wasm.py` rebuilds the module from a PRG32-QT checkout and
  records its provenance in `static/wasm/BUILD.json`.
- Golden tests (`tests/test_wasm_runtime.py`) and a CI job prove the browser
  core behaves exactly like the native core and `prg32qt-headless`.
- No database changes.

### Security and quality (round 1)

- **No default admin password.** The first start writes a random password to
  `<data>/initial_admin_password` (mode 600, deleted once an admin changes
  it) unless `PRG32_ADMIN_PASSWORD` is set. With `PRG32_KIT_ENV=production`
  (the Docker image) a short or well-known password stops the start.
  Compose no longer defaults to `password`.
- **Sign-in limits**: wrong passwords (per address+name and per address),
  registration requests, invalid registration links and new API tokens.
  `429` + `Retry-After`. `PRG32_KIT_PROXY_COUNT` for reverse proxies;
  `DELETE /api/admin/throttles` to unlock a class.
- **Audit log** (`GET /api/admin/audit`, admins only) for accounts, roles,
  groups, passwords, API tokens, bootstrap, registrations, sign-in locks,
  publishing, SSO syncs and unlocking. No secrets are stored.
- **Build provenance** in `build.metadata.provenance` and SHA-256/size on
  every `.prg32` artifact (`build_provenance.md`).
- A build whose compiler refused the source is now `failed` (it was shown as
  `source-only`); the editor says so.
- **Restore keeps identity**: sprites and assets are restored in place, in
  one transaction, so artifacts keep their sprite links.
- Build logs and package responses no longer show server folders (the
  Python path in the logged command, `result.source_path`) or secret-looking
  build-command options.

### Migration and rollback

- New tables `audit_events` and `auth_throttle`; new column
  `project_revisions.child_ids` (default `'{}'`). All created at start-up,
  idempotently. Older revisions keep working (matched by name).
- Rollback: the previous release ignores the new tables and column, so
  downgrading the code is safe. Before rolling back, note that the previous
  release would again create `admin`/`password` on an empty database.

### Added

- Portable project archive: **Export → Project archive (.zip)** in the
  editor, `GET /api/projects/<id>/archive`. Holds `prg32.project.json`
  (schema 1), the source, sprites and assets; byte-identical for the same
  project.
- **Import project** on the dashboard accepts archives as well as JSON.
- `GET /api/projects/<id>/manifest` and `POST /api/projects/<id>/duplicate`.
- **History** in the editor: every save that changes the blocks, the
  Advanced C or the handwritten assembly keeps the version before it. Restore one (the current version
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
- Service worker cache `prg32-kit-v8`.

### Migration

New table `project_revisions` and new column `projects.deleted_at`, added
automatically and idempotently on start; existing databases keep working.
Old exports keep importing.
