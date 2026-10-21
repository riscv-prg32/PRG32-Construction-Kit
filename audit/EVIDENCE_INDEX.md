# Evidence index

## Revisions

| Repository | HEAD |
|---|---|
| PRG32-Construction-Kit | `c0d115e80c53b1d7d46afb639d104efd2b1c8516` |
| PRG32 | `679dfb58783bd007125de9ca0b75eaa077908739` |
| PRG32-QT | `f6d80addf49d0512c2e4390251a81d797a35b157` |
| CartridgeStore | `820f74bfe9364c8727db92cb0f15f3b9dd85feab` |

## Audio evidence

- Browser approximation: `static/js/prg32_runtime.js`, `AudioHost`.
- WASM semantic records: `wasm/prg32_core_api.cpp`, `QueueAudioSink`.
- Existing call-only test: `tests/test_wasm_runtime.py::test_audio_calls_reach_the_browser_host`.
- Generated buzzer exposure: `tools/build_language_index.py` and `static/js/ide/prg32_language_index.js`.
- Basic Blocks/generation: `prg32_construction_kit/generator.py`, `asm_generator.py`, `tools/build_example_games.py`.
- Upstream reference: PRG32 `components/prg32_audio/`; PRG32-QT `src/core/Audio.h`, `Runtime.cpp`, and `src/qt/QtAudioEngine.cpp`.
- Missing evidence: AudioStudio files/tests, eight-voice fixture, ADSR trace, rendered stereo comparison and buzzer-removal test.

## Executed evidence

- Broad feasible suite: 857 passed, 70 skipped, 1 deselected before isolated reruns.
- Syntax and all reproducibility checks passed.
- Required Chromium: 81 passed; delivery: 6 passed; disposable Store contract/lifecycle: 51 passed; Store egress: 94 passed; capability/document consistency: 150 passed.
