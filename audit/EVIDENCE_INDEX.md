# Evidence index

## Revisions

| Repository | HEAD |
|---|---|
| PRG32-Construction-Kit | `fe2e2c4978ff67c0e3f48987b80187cff40c1094` |
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

- 2026-10-23 broad feasible suite: **1,332 passed, 57 skipped, 3 failed**; failures are the unmerged Store identity contract.
- Linux-only `test_the_process_limit_starts_from_what_the_kernel_counts`: skipped on macOS.
- 2026-10-22 privacy/docs/new-feature selection: **441 passed, 1 skipped**.
- 2026-10-22 broad feasible suite with loopback/cache access: **1,330 passed, 56 skipped, 1 failed**.
- Failing test: `tests/test_sso_with_cartridge_store.py:75`; isolated reproduction failed twice with different generated `player-*` usernames.
- Forced browser selection: **5 passed, 40 setup errors** because no Chrome or Playwright Chromium is installed; no browser pass is claimed from this host.
- Refinement selection (`test_doc_consistency`, `test_capabilities`, `test_auth`, `test_authorization`, `test_storage_policy`, `test_cloud_storage`, `test_backup_restore`, `test_api`): **331 passed in 34.42 s**.
- Focused cross-feature selection: **294 passed, 9 skipped**; five delivery setups were sandbox-denied.
- Delivery with loopback permission: **8 passed**.
- Mandatory Chrome: **88 passed**.
- Disposable live Kit/Store HTTP suites: **11 passed**.
- Broad feasible suite: **1,009 passed, 85 skipped, 1 deselected**; the same five delivery setups were isolated and passed separately.
- Syntax/reproducibility checks: pass where the local environment provides required tooling.

## GDPR and documentation evidence status at `bb2b062`

- Privacy implementation: `prg32_construction_kit/privacy.py`, `privacy_notices.json`, `retention.py`, `secrets_at_rest.py`; `tests/test_privacy_records.py`, `test_privacy_rights.py`.
- Records: `docs/privacy/ropa.json` and generated `ropa.md`, roles/legal bases, notices, retention, processors/transfers, Article 32, DPIA/DPO screening, breach playbook and rehearsal.
- Open legal/operational evidence: every deployment decision D-0–D-10 remains open; no qualified DPO/counsel review or staffed tabletop.
- Documentation: current `README.md`, `docs/architecture.md`, generated diagrams, `docs/figures/manifest.json`, `tools/check_docs.py`, capture/build recipes and review commits through `bb2b062`.

## Worktree state

The tracked worktree was clean. Pre-existing untracked `.claude/`,
`CLAUDE_PRG32_FULL_IDE_REFINEMENT.md` and
`CLAUDE_PRG32_QUALITY_IMPROVEMENT_ROUND.md`, plus the previous downloadable
audit note, were preserved and were not treated as implementation evidence.
