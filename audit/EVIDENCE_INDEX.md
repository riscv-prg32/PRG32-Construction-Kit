# Evidence index

## Revisions

| Repository | HEAD |
|---|---|
| PRG32-Construction-Kit | `951f782f3c54a306d2bad70396127fc74a596158` |
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

- Focused cross-feature selection: **294 passed, 9 skipped**; five delivery setups were sandbox-denied.
- Delivery with loopback permission: **8 passed**.
- Mandatory Chrome: **88 passed**.
- Disposable live Kit/Store HTTP suites: **11 passed**.
- Broad feasible suite: **1,009 passed, 85 skipped, 1 deselected**; the same five delivery setups were isolated and passed separately.
- Syntax/reproducibility checks: pass where the local environment provides required tooling.
