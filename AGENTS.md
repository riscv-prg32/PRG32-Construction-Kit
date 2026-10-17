# AGENT.md

Formal constraints for coding agents and contributors working on PRG32-Construction-Kit.

## Scope

This file applies to the whole repository.

## Project identity

- The application name is **PRG32-Construction-Kit**.
- The target audience is young students, teachers, and classroom facilitators.
- The project is a construction kit for PRG32 games, not a replacement for PRG32 firmware or Cartridge Store.
- Preserve the phrase **PRG32 cartridge** for `.prg32` artifacts.

## Educational constraints

- Prefer readable, explicit Python and JavaScript over clever abstractions.
- Keep APIs and JSON formats explainable to middle-school and early high-school learners.
- Do not hide the generated C or generated RISC-V assembly; students must be able to inspect both.
- Generated C and assembly are teaching material: keep the per-block and per-line explanatory comments.
- Generated code must be deterministic from saved Blocks JSON and project metadata.
- The simulator should favor understandable behavior over cycle-accurate emulation.

## Safety and generation constraints

- Do not compile arbitrary unvalidated user C supplied by an LLM.
- The normal pipeline is: Blockly JSON -> validated game IR -> deterministic C (and, on request, deterministic RISC-V assembly) -> PRG32 toolchain.
- Generate assembly (`asm_generator.py`) only from the validated game IR, never from user-typed assembly. It must do exactly what the generated C does; keep `tests/test_asm_generator.py` proving that.
- Generated assembly is RV32IM in a `.S` file for the portable PRG32 cartridge ABI. Full-line comments use `/* ... */` because the file goes through the C preprocessor.
- `source_language` accepts only `"c"`, `"asm"` or `"both"`; Advanced C projects compile their own C only.
- AI assistants, when added, may propose block edits or explain errors, but they must not silently alter projects.
- Validate expressions used in generated C. Reject or sanitize semicolons, braces, preprocessor directives, and unknown unsafe syntax.
- Keep generated C freestanding and small. Avoid libc, floating point, dynamic allocation, and hidden network calls.

## Storage constraints

- Save block programs as JSON in the `projects.blocks_json` field.
- Save generated and uploaded artifacts through the artifact CRUD API.
- Keep large bundles on disk and metadata in SQLite.
- Do not store bearer tokens in logs or public responses.
- Maintain idempotent SQLite initialization with `CREATE TABLE IF NOT EXISTS`.
- Generated C is stored as `c_source` artifacts and generated assembly as `asm_source` artifacts.
- Every build works only inside its own `<build_id>/` folder (with a private `tmp/`); builds must never share files.

## API constraints

Preserve these resource CRUD routes unless a documented migration is added:

- `GET/POST /api/projects`
- `GET/PUT/DELETE /api/projects/<id>`
- `GET/POST /api/sprites`
- `GET/PUT/DELETE /api/sprites/<id>`
- `GET/POST /api/assets`
- `GET/PUT/DELETE /api/assets/<id>`
- `GET/POST /api/artifacts`
- `GET/PUT/DELETE /api/artifacts/<id>`
- `GET/POST /api/builds`
- `GET/PUT/DELETE /api/builds/<id>`
- `GET/POST /api/publish_profiles`
- `GET/PUT/DELETE /api/publish_profiles/<id>`

Preserve these action routes:

- `POST /api/projects/<id>/convert`
- `POST /api/projects/<id>/package`
- `POST /api/sprites/<id>/convert`
- `POST /api/publish`
- `GET /.well-known/prg32-construction-kit.json` (keep its `cartridge_builds` field)

## Security constraints

- Every page and `/api/` route except sign-in, static files, docs and discovery requires a signed-in user.
- Keep the account model aligned with PRG32 Cartridge Store (roles, groups, API tokens, `/auth/*` routes).
- Items belong to their creator (`owner_id`); items without an owner are shared and read-only for non-admins.
- `prg32_construction_kit/sso_protocol.py` must stay identical to `cartridge_store/sso_protocol.py` in CartridgeStore.
- Never store plain-text passwords; synced records carry password hashes only.
- Browser API calls send `X-PRG32-Kit: 1` and `X-PRG32-User`; keep the `409 user_changed` refusal when a window's user no longer matches the session.

## Frontend constraints

- Use Bootstrap for layout and components.
- Use jQuery for app-level DOM and API wiring.
- Use Blockly for the block editor.
- Keep the app installable as a PWA with manifest and service worker.
- Do not require a cloud account for normal classroom use.
- The service worker caches static files only, never signed-in pages; bump its cache version when cached files change.

## Documentation constraints

- Keep all long-form docs in `docs/`.
- README.md must stay short and setup-focused.
- Every feature must have at least one short teacher/student explanation in `docs/` or `docs/tutorials/`.
- Keep `docs/install_cartridge_build.md` in step with the Dockerfile, `docker/`, and `examples/deploy/`.

## Test constraints

- Add or update pytest coverage for backend CRUD, conversion, and packaging logic when behavior changes.
- CI must run tests on every push and pull request.
- CI also builds the Docker image with the PRG32 toolchain and compiles real cartridges with `tools/check_build.py`; keep that job passing.
- Tests that need a RISC-V assembler or the PRG32 toolchain must skip cleanly when it is missing.
