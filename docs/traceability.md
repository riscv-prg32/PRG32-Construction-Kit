# Requirement traceability

Each requirement from the full-IDE brief, the evidence for it, and the test
that proves it. "—" means not implemented yet. Statuses: **Done**,
**Partial**, **Open**, **Blocked**.

## Project model (G1)

| ID | Requirement | Status | Evidence | Test |
| --- | --- | --- | --- | --- |
| PM-1 | Versioned `prg32.project.json` with schema version | Done | `prg32_construction_kit/project_format.py` (`build_manifest`) | `test_manifest_describes_a_blocks_project` |
| PM-2 | Authoring mode `blocks` / `c` / `assembly` | Done | `AUTHORING_MODES`; assembly per ADR-0004 (`validate_asm_source`) | `test_assembly_archive_round_trip`, `tests/test_handwritten_assembly.py` |
| PM-2a | Handwritten assembly is validated before building, and builds a real cartridge | Done | `source_project.validate_asm_source`, `routes._generate_project` | `test_file_reading_and_unknown_directives_are_rejected`, `test_bad_assembly_is_refused_before_building`, `test_handwritten_assembly_builds_a_real_cartridge` |
| PM-3 | Entry points, assets, SDK/ABI, targets, build profiles, tests in manifest | Done | `build_manifest` | `test_manifest_describes_a_blocks_project`, `test_sdk_abi_matches_the_prg32_sdk_when_installed` |
| PM-4 | Canonical source stays in its mode; generated code never overwrites it | Done | Archive holds only `src/*`; generated code excluded | `test_archive_is_deterministic_and_holds_only_source` |
| PM-5 | Portable archive export/import | Done | `GET /api/projects/<id>/archive`, `POST /api/projects/import` | `test_archive_round_trip_keeps_blocks_sprites_and_assets`, `test_advanced_c_archive_round_trip` |
| PM-6 | Deterministic output | Done | Fixed zip dates, sorted entries, content-ordered children | `test_archive_is_deterministic_and_holds_only_source` (incl. re-export of the imported copy) |
| PM-7 | Deterministic migrations | Done | `MIGRATIONS`, `upgrade` (legacy export = v0) | `test_legacy_json_export_is_migrated`, `test_legacy_c_export_keeps_its_source`, `test_upgrade_rejects_newer_and_foreign_documents` |
| PM-8 | Safe import (traversal, links, size, zip bombs) | Done | `read_archive_files` | `test_unsafe_or_broken_archives_are_refused`, `test_symlinks_and_oversized_entries_are_refused` |
| PM-9 | No half-imported projects | Done | `_create_from_contents` cleanup | `test_failed_child_insert_leaves_no_half_project` |
| PM-10 | Duplicate | Done | `POST /api/projects/<id>/duplicate`, editor "Make my copy" | `test_duplicate_copies_children_and_belongs_to_the_caller` |
| PM-11 | Ownership: imports belong to the importer; no IDOR on export | Done | `owned()`, `readable()` | `test_imported_archive_belongs_to_the_importer`, `test_duplicate_copies_children_and_belongs_to_the_caller` |
| PM-12 | Create/open/rename/delete | Done (pre-existing) | CRUD routes | `tests/test_api.py::test_project_crud` |
| PM-13 | Snapshots/history, autosave, search, soft delete | Partial (history and soft delete done; autosave and search open) | `project_revisions` table, `add_revision` (db.py); `/api/projects/<id>/revisions*`, `?deleted=1`, `/restore`, `?purge=1` (routes.py); editor **History**, dashboard **Recently deleted** | `tests/test_project_revisions.py` (snapshot rules, cap, restore, IDOR, hide/restore/purge, old DB upgrade) |
| PM-14 | Source maps blocks → C → instructions | Open | — | — |

## Other areas

| ID | Requirement | Status | Notes |
| --- | --- | --- | --- |
| IDE-* | JetBrains-style shell, Monaco, language services | Open | G2 |
| TC-1 | Real `.prg32` from Blocks and C | Done (pre-existing) | `tests/test_concurrency.py`, CI container job |
| TC-2 | Provenance and hashes per build | Open | G3 |
| TC-3 | Browser toolchain | Open | G3 spike |
| RT-* | WASM guest runtime from PRG32-QT core | Open | ADR-0003 |
| DBG-* | Debugger with Qt parity | Open | ADR-0006; parity table in `compatibility.md` |
| ID-* | OIDC+PKCE, roles, guest policy | Open | ADR-0007 |
| CL-* | Drive/OneDrive sync | Open | needs OAuth app registrations |
| ST-1 | Store bundle publish | Done (pre-existing) | `tests/test_api.py` publish tests |
| TG-* | Qt / iOS / hardware targets | Partial | download + manual import only |
