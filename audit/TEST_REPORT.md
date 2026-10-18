# Test report

## Environment

- 2026-10-18, Europe/Rome; macOS host with restricted filesystem/network/process access.
- Python 3.12.10; pytest 8.4.2; Node v26.12.0; npm 11.20.0; Git 2.55.0; Docker CLI 28.5.2; CMake 4.4.3; Emscripten available.
- No RISC-V GCC/PRG32 cartridge toolchain or bubblewrap on this host. Docker daemon socket access was denied.

## Executed commands and results

1. `python3 -m compileall -q app.py prg32_construction_kit tests tools` — **pass**.
2. `for file in static/js/*.js static/service-worker.js tools/*.mjs; do node --check "$file"; done` — **pass**.
3. `python3 -m pytest -q -rs` — broad run executed. Product-independent environment failures were observed: loopback-bound Store test servers received `PermissionError`, and the exact WASM rebuild could not create a lock in `/opt/homebrew/.../emscripten/.../cache`. Toolchain/platform tests skipped cleanly.
4. `python3 -m pytest -q -rs --ignore=tests/test_store_egress.py -k 'not fresh_build_matches_the_committed_module'` — **380 passed, 21 skipped, 1 deselected** in 49.82 s.
5. `python3 -m pytest -q -rs tests/test_publish_authorization.py tests/test_build_sandbox.py` — **34 passed, 7 skipped** in 8.93 s. Skips: Linux-only address-space check and six bubblewrap/user-namespace tests.
6. `PRG32QT_DIR=../PRG32-QT python3 -m pytest -q -rs tests/test_wasm_runtime.py` — **29 passed, 1 skipped, 1 failed**. Skip: missing PRG32 build toolchain. Failure: rebuild reached final link, then Emscripten cache write was denied; no byte mismatch was produced.
7. `cmp -s prg32_construction_kit/sso_protocol.py ../CartridgeStore/cartridge_store/sso_protocol.py` — **pass**; SHA-256 for both: `611d881247c2ca8bd074320a08e994aaac1db43844dcf7f6e11abd0ae249a593`.
8. `shasum -a 256 static/wasm/prg32-core.wasm` — `3ba378fb805cf9bfcfabe3c0334df7890719139dfed46c560ac137c045262b21`, matching `BUILD.json`.

## Mandatory scenarios

| Scenario | Result |
|---|---|
| A Guest policies | **Missing/blocked:** guest mode not implemented. |
| B Registered student | CRUD/history/import/export/isolation covered by tests; cloud, autosave conflicts and live network-loss flows missing. |
| C Three language modes | Generation/validation tested; real local builds blocked by missing toolchain. CI definition is source evidence, not this audit's execution. |
| D Debugger parity | Machine-level differential tests passed; source/DWARF/block portions missing. No browser GUI automation. |
| E Academic SSO | Source/unit inspection only; no external IdP and required profile incomplete. |
| F CartridgeStore | Authorization/review/idempotency tests passed; loopback transport rerun blocked; no live public publication. |
| G Security/performance/a11y | Negative backend tests partly executed; no browser memory/latency, cold-offline, screen reader or full keyboard run. |

No coverage percentage, hardware result, screenshot, newly built cartridge, iOS result, or live publication is claimed.
