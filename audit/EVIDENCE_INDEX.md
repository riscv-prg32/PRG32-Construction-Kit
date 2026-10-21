# Evidence index

## Revisions

| Repository | HEAD |
|---|---|
| PRG32-Construction-Kit | `7c83e716796ae8b2a5771173d885d5f20a390209` |
| PRG32 | `679dfb58783bd007125de9ca0b75eaa077908739` |
| PRG32-QT | `f6d80addf49d0512c2e4390251a81d797a35b157` |
| CartridgeStore | `820f74bfe9364c8727db92cb0f15f3b9dd85feab` |

## Primary evidence

- Toolchain: `docs/evidence/toolchain/2026-10-21/`, `tools/reproduce_toolchain_checks.py`.
- PRG32-QT delivery: `docs/evidence/delivery/2026-10-21-prg32qt/`.
- Compiler checks: `prg32_construction_kit/packager.py`, `routes.py`, `tests/test_compiler_check.py`.
- Live Store SSO/publishing: `tests/test_sso_live.py`, `docs/accounts_and_sso.md`.
- Audio/QEMU: `docs/evidence/qemu-audio/2026-10-21-patched/`.
- Qt audio device: `docs/evidence/prg32qt-audio/2026-10-21/`.
- Upstream patches: `docs/upstream/prg32-sdk-retire-buzzer.patch`, `prg32-qt-firmware-audio.patch`, `prg32-sdk-audio-clock-and-reset.patch`.
- Audio handoff: `docs/handoff/audio-after-f4b74bc.md`.

## Fresh execution

- Refinement selection (`test_doc_consistency`, `test_capabilities`, `test_auth`, `test_authorization`, `test_storage_policy`, `test_cloud_storage`, `test_backup_restore`, `test_api`): **331 passed in 34.42 s**.
- Focused cross-feature selection: **294 passed, 9 skipped**; five delivery setups were sandbox-denied.
- Delivery with loopback permission: **8 passed**.
- Mandatory Chrome: **88 passed**.
- Disposable live Kit/Store HTTP suites: **11 passed**.
- Broad feasible suite: **1,009 passed, 85 skipped, 1 deselected**; the same five delivery setups were isolated and passed separately.
- Syntax/reproducibility checks: pass where the local environment provides required tooling.

## GDPR and documentation evidence status

- Privacy notices/ROPA/role and legal-basis matrix/subprocessor and transfer register/DPIA/DPO/counsel decisions: **not found**; `docs/privacy/` does not exist.
- Rights-request artifacts and breach exercise: **not found**.
- Privacy-supporting partial evidence: `prg32_construction_kit/retention.py`, `storage_policy.py`, `cloud_storage.py`, `security.py`; `tests/test_storage_policy.py`, `test_cloud_storage.py`, `test_authorization.py`, `test_backup_restore.py`.
- Documentation entry points inspected: `README.md`, `docs/architecture.md`, `docs/architecture/current-state.md`, `docs/capabilities.json`.
- Visuals inventoried under `docs/figures/` and delivery evidence; repository-wide provenance/freshness manifest and complete link/image/alt checker: **not found**.

## Worktree state

The audit began with pre-existing modifications to
`docs/briefs/CODEX_PRG32_CONSTRUCTION_KIT_QUALITY_AUDIT_AUDIOSTUDIO.md` and
`docs/briefs/README.md`, plus untracked `.claude/`, root refinement notes and
`docs/briefs/CLAUDE_PRG32_GDPR_DOCUMENTATION_REFINEMENT_AUDIT_951F782.md`.
They were treated as inputs/working material, not implementation evidence, and
were not overwritten by this audit.
