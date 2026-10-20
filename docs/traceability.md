# Requirement traceability

The audit-aligned, machine-checked summary is `capabilities.md` (from
`capabilities.json`, verified by `tests/test_capabilities.py`). This page keeps
the detailed requirement history.

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
| PM-13a | Restore keeps sprite/asset identity and links, transactionally | Done | `ProjectRevision.child_ids`, `routes.restore_plan`, `db.restore_project_state`, idempotent `_add_missing_revision_child_ids` | `tests/test_restore_relationships.py` (in-place, add/remove, reorder, legacy match by name, malformed ids, damaged revision, foreign ids, rollback, owner, IDOR, old DB) |
| PM-13 | Snapshots/history, autosave, search, soft delete | Partial (history, soft delete, autosave and conflict-safe versions done [ACC-02]; search open) | `project_revisions` table, `add_revision` (db.py); `/api/projects/<id>/revisions*`, `?deleted=1`, `/restore`, `?purge=1` (routes.py); editor **History**, dashboard **Recently deleted** | `tests/test_project_revisions.py` (snapshot rules, cap, restore, IDOR, hide/restore/purge, old DB upgrade) |
| PM-14 | Source maps blocks → C → instructions | Done [IDE-02] | `source_maps.build_source_map`, `debug_info.build_debug_map`, ADR-0015 | `tests/test_source_debugger.py` |

## Other areas

| ID | Requirement | Status | Notes |
| --- | --- | --- | --- |
| IDE-* | JetBrains-style shell, Monaco, language services | Shell and Monaco done [IDE-01]; offline language services done [IDE-03] [IDE-04]; block source maps open (phase 4) | G2, ADR-0013, ADR-0014, `capabilities.md` |
| TC-1 | Real `.prg32` from Blocks and C | Done (pre-existing) | `tests/test_concurrency.py`, CI container job |
| TC-2 | Provenance and hashes per build | Done | `provenance.py`, `packager.prepare_package` (`cartridges`, `attempts`), `routes._run_package_build`; tests `tests/test_build_provenance.py` (C, generated asm, handwritten asm, both, failed, source-only, crash, deterministic fields, path/secret redaction, real toolchain) |
| TC-2a | Compiler errors are `failed`, not `source-only` | Done | `build_check.toolchain_present`, `routes._run_package_build`; `test_compiler_errors_are_failed_builds_not_source_only` |
| TC-2b | No server paths or secrets in build responses and logs | Done | `packager.redact_build_path`, `public_command`, `routes.public_build_result`; `test_no_server_paths_or_secrets_leave_the_server`, `tests/test_api.py::test_package_uses_configured_build_root` |
| TC-3 | Browser toolchain | Open | G3 spike |
| RT-1 | Qt-free core compiled to WASM, guest interpreted in WASM | Done | `wasm/`, `static/wasm/BUILD.json`; `test_committed_module_matches_its_build_record`, `test_fresh_build_matches_the_committed_module` |
| RT-2 | Matches PRG32-QT on golden cartridges | Done | `test_wasm_runs_golden_cartridges_exactly_like_native`, `test_native_harness_draws_exactly_like_prg32qt_headless` |
| RT-3 | Kit-built Blocks/C/assembly cartridges run in the browser core | Done | `test_kit_cartridges_run_the_same_in_the_browser_core` (real toolchain) |
| RT-4 | Browser host: framebuffer, input, timing (guest vs wall), audio, offline | Done (audio approximate) | `static/js/prg32_runtime.js`, `/player`; `test_audio_calls_reach_the_browser_host`, `test_service_worker_caches_the_runtime_for_offline_use`; manual browser check |
| RT-5 | Deterministic clock and scripted input playback | Done | accurate-mode virtual clock; harness scripted input |
| RT-6 | Multiplayer, Wi-Fi, score services in the browser | Open | — |
| DBG-1 | PRG32-QT debugger parity: pause/resume, instruction step, speed, address breakpoints (resume ignores once), registers, disassembly with Init/Update/Draw/PC views, bounded memory view | Done | `wasm/prg32_core_api.cpp` (`prg32_debug_*`, `prg32_breakpoint`, `prg32_disassemble`), `static/js/prg32_runtime.js` `debug()`, `static/js/prg32_debugger.js`; `test_debugger_steps_exactly_like_native`, `test_breakpoint_stops_once_per_visit`, `test_single_steps_add_up`, `test_player_speaks_the_prg32_qt_debug_protocol`; browser check |
| DBG-2 | Step over / step out / step frame | Done | core call/return recognition; `test_step_over_and_step_out_follow_calls`, `test_debugger_steps_exactly_like_native` |
| DBG-3 | Instrumented execution does not change the program | Done | `test_debug_frames_match_normal_frames`, `test_playback_slices_stop_at_every_visit` |
| DBG-4 | Breakpoints persisted per cartridge; beginner/advanced views on one state | Done | `localStorage` by SHA-256; `test_player_speaks_the_prg32_qt_debug_protocol`; browser check |
| DBG-5 | Shared protocol (ADR-0006) | Done (main-thread transport) | `docs/adr/0006-shared-debug-protocol.md` |
| DBG-6 | DWARF: C locals, call stack, watches, conditional breakpoints | Done [DBG-05] | `debug_build.py` (-g wrappers, identical cartridge), `debug_info.py`, `static/js/source_debug.js`; `tests/test_source_debugger.py`, `tests/test_debugger_browser.py` |
| DBG-7 | Blockly block highlighting while stepping | Done [IDE-02] | `static/js/source_debugger.js` (read-only Blocks view, block breakpoints, Next block); `test_scenario_d_block_and_source_debugging` |
| ID-* | OIDC+PKCE, roles, guest policy | Identity, roles [SSO-01] [SSO-02] [SSO-03] and guest policy [ACC-01] done | ADR-0007, ADR-0016; `tests/test_identity.py`, `tests/test_authorization.py` |
| SEC-5 | Store publishing cannot be used for SSRF (audit H-01) | Implemented and verified (automated) | `store_policy.py`, `publisher.py`, `routes.checked_payload`/`api_publish`, ADR-0008; `tests/test_store_egress.py` (URL shapes, numeric IPs, credentials, schemes, private/loopback/link-local/IPv6/mapped addresses, DNS answers, rebinding, redirects, bounded answers, timeouts, TLS with host-name check, API refusals, audit, token non-disclosure, trusted-local workflow) |
| CLD-1 | Google Drive and OneDrive behind one interface, no silent overwrite [CLD-01] [CLD-02] | Partial (no live tenant run) | `cloud_storage.py`, `static/js/cloud.js`, ADR-0019 | `tests/test_cloud_storage.py` (both providers), `tests/test_cloud_browser.py`, opt-in `tests/test_cloud_live.py` |
| STR-C | Shared versioned Store contract, enforced before upload, agreed with the Store [STR-01] | Done | `contracts/prg32-store-contract-1.json`, `store_contract.py`, ADR-0018 | `tests/test_store_contract.py` (fixtures through kit and Store code), `tests/test_store_live.py` (throwaway live Store) |
| SEC-6 | Publishing needs the publisher role and an explicit, unchanged review (audit H-02) | Implemented and verified (automated + browser check against a local test Store) | `publishing.py`, `routes._prepare_publish`/`api_publish_review`/`api_publish`, `publish.html`/`publish.js`, ADR-0009; `tests/test_publish_authorization.py` (roles, 428/409 paths, swaps, changed bundle/Store, stale/forged/other-user tokens, source-only, missing/fake/mismatched cartridges, bad manifest, uploaded bundles, double confirm, retry after failure, Store refusal, audit stages) |
| SEC-7 | Untrusted compiles run in an isolation boundary (audit H-03) | Implemented and verified (automated, inside the Linux container on aarch64 with the production security options; x86_64 in CI) | `build_sandbox.py`, `build_guard.py`, `packager.run_prg32_build`, `docker/seccomp-kit.json`, Dockerfile, compose, ADR-0010; `tests/test_build_sandbox.py` (secret env, timeout/group kill, output/file/memory caps, production no-fallback, refused sandbox = no build, command line, mounts, seccomp program; in bwrap: other builds/data/`/etc/shadow` unreadable, no network, no writes outside, mknod/unshare/ptrace/mount refused, fork bomb + CPU loop contained, memory/file bombs contained); real Blocks/C/assembly cartridges and the classroom check built inside the sandbox |
| SEC-8 | Disk budgets for builds; confined AppArmor profile instead of unconfined; fuzzed debug readers | Implemented (Linux container locally); AppArmor-confined CI run failed with the first profile, rerun pending | `build_budget.py`, `build_guard.py --disk-budget`, `docker/apparmor/prg32-kit`, `debug_info.MAX_IMAGE_BYTES`, numeric source-map markers | `tests/test_build_budget.py`, `tests/test_debug_fuzz.py`, CI `container-smoke-test` |
| SEC-1 | No network-deployable default admin password | Done | `auth.bootstrap_admin`, `config.KIT_ENV`, Dockerfile `PRG32_KIT_ENV=production`, compose; `tests/test_admin_bootstrap.py` |
| SEC-2 | Sign-in, registration, link and token throttling | Done | `security.py` limits, `auth.login/register/register_complete/create_token`; `tests/test_security_controls.py` (threshold, expiry, reset, isolation, proxy trust, unlock) |
| SEC-3 | Admin audit log | Done | `security.record`, `GET /api/admin/audit`; `tests/test_security_controls.py` (users, roles, groups, tokens, publish, bootstrap, admin-only, no secrets) |
| SEC-4 | Audit of configuration/SSO admin actions | Partial | Manual SSO sync and throttle clearing are audited; the kit has no other admin configuration endpoints |
| CL-* | Drive/OneDrive sync | Open | needs OAuth app registrations |
| ST-1 | Store bundle publish | Done (pre-existing) | `tests/test_api.py` publish tests |
| TG-* | Qt / iOS / hardware targets [DEP-01] [DEP-02] [DEP-03] | Partial | download, `delivery.md`; `tools/delivery_check.py` records device runs (`tests/test_delivery_check.py`); iOS deferred (ADR-0020) |
