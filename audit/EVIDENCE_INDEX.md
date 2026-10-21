# Evidence index

## Revisions

| Repository | HEAD |
|---|---|
| PRG32-Construction-Kit | `13766c9173353f10d4b89222df0c1e60291725a5` |
| PRG32 | `679dfb58783bd007125de9ca0b75eaa077908739` |
| PRG32-QT | `f6d80addf49d0512c2e4390251a81d797a35b157` |
| CartridgeStore | `820f74bfe9364c8727db92cb0f15f3b9dd85feab` |

## Audio evidence

- Contract and packed format: `contracts/prg32-audio-contract-1.json`, `prg32_construction_kit/audio_studio.py`.
- Canonical browser engine bridge: `wasm/prg32_core_api.cpp`, `wasm/audio/audio_port.c`.
- AudioStudio product path: `prg32_construction_kit/audio_studio_api.py`, `templates/audio_studio.html`, `static/js/audio_studio.js`.
- Deterministic cartridge integration: `prg32_construction_kit/routes.py`, generator/assembly paths and `AUD0` packaging tests.
- Conformance: `tests/test_audio_contract.py`, `tests/test_audio_block.py`, `tests/test_audio_conformance.py`, `tests/test_audio_studio.py`, `tests/test_audio_browser.py`.
- Buzzer retirement guard: `tests/test_no_buzzer.py`; authored legacy use is refused and old runtime calls are silent/countable.
- Remaining external references: PRG32 `components/prg32_audio/`; PRG32-QT `src/core/Audio.h`, `Runtime.cpp`, `src/qt/QtAudioEngine.cpp`.

## Executed evidence

- Focused audio/backend/conformance/no-buzzer suite: **95 passed**.
- Broad feasible suite: **965 passed, 72 skipped, 1 deselected**; one capability mismatch was caused by the audit edit before regenerating `docs/capabilities.md`, and four delivery setups were blocked by sandbox loopback policy. The capability/document rerun then passed **156 tests**.
- Python/JavaScript syntax, service-worker lock, language-index reproducibility, Store-contract fixtures, SBOM and the 28-package hashed requirements lock passed.
- Audio fixture regeneration was unavailable because the PRG32 toolchain is not installed on this host.
- Required Chrome suite, including the two AudioStudio browser scenarios: **85 passed**; loopback delivery rerun: **6 passed**.
