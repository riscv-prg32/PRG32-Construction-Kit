# Evidence index

## Revisions

| Repository | HEAD |
|---|---|
| PRG32-Construction-Kit | `f4b74bcfe2f0b70563daae4fd76cc1c1b8acaf78` |
| PRG32 | `679dfb58783bd007125de9ca0b75eaa077908739` |
| PRG32-QT | `f6d80addf49d0512c2e4390251a81d797a35b157` |
| CartridgeStore | `820f74bfe9364c8727db92cb0f15f3b9dd85feab` |

## Primary audio evidence

- Contract/engine: `contracts/prg32-audio-contract-1.json`, `wasm/audio/audio_port.c`, `wasm/prg32_core_api.cpp`.
- AudioStudio: `prg32_construction_kit/audio_studio.py`, `audio_studio_api.py`, `static/js/audio_studio.js`.
- QEMU: `tools/qemu_audio_capture.py`, `docs/evidence/qemu-audio/2026-10-21/`.
- PRG32-QT proposal: `docs/upstream/prg32-qt-firmware-audio.patch`, `tests/test_prg32qt_firmware_audio.py`.
- Hardware preparation: `docs/hardware_audio_check.md`, `tools/hardware_audio_compare.py`, `tests/fixtures/audio/hardware/`.
- Handoff matrix and hashes: `docs/handoff/audio-after-13766c9.md`.
- Buzzer guard: `tests/test_no_buzzer.py`.

## Fresh execution

- Focused audio/reference suite: **113 passed, 1 skipped**.
- Mandatory Chrome: **87 passed**.
- Broad feasible: **988 passed, 75 skipped, 1 deselected**; four sandbox socket setups passed in the separate **6/6** delivery rerun.
- Capability/document consistency and reproducibility checks: pass where locally available.
- Toolchain fixture rebuild: unavailable on this host.
