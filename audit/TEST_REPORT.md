# Test report

## Environment

- Date: 2026-10-19, Europe/Rome.
- macOS; Python 3.12.10; pytest 8.4.2; Node v26.12.0; npm 11.20.0; Git 2.55.0; Playwright 1.64.0; installed Google Chrome.
- Local reference checkouts: PRG32 `679dfb5`, PRG32-QT `f6d80ad`, CartridgeStore `820f74b`.
- No local RISC-V/PRG32 build toolchain or bubblewrap; Docker/container execution not repeated.

## Exact commands and results

1. `python3 -m compileall -q app.py prg32_construction_kit tests tools` — **pass**.
2. `for file in static/js/*.js static/js/ide/*.js static/service-worker.js tools/*.mjs; do node --check "$file"; done` — **pass**.
3. `python3 tools/service_worker_lock.py --check` — **pass**.
4. `python3 tools/render_capabilities.py --check` — **pass**.
5. `python3 -m pytest -q -rs --ignore=tests/test_store_egress.py -k 'not fresh_build_matches_the_committed_module'` — **482 passed, 31 skipped, 1 deselected**, 52.30 s. Ten browser skips were rerun in command 7.
6. `python3 -m pytest -q -rs tests/test_capabilities.py tests/test_frontend_offline.py tests/test_ide_browser.py tests/test_browser_offline.py` — **102 passed, 10 browser skips** under restricted execution.
7. `python3 -m pytest -q -rs tests/test_browser_offline.py tests/test_ide_browser.py` with permission to launch Chrome/bind loopback — **10 passed**, 11.46 s.
8. `python3 -m pytest -q -rs tests/test_store_egress.py` with loopback permission — **94 passed**, 7.81 s.
9. `PYTHONPATH=../PRG32 python3 -m pytest -q -rs tests/test_project_format.py::test_sdk_abi_matches_the_prg32_sdk_when_installed tests/test_wasm_runtime.py -k 'not fresh_build_matches_the_committed_module'` — **30 passed, 1 skipped, 1 deselected**, 7.26 s. Skip: missing PRG32 toolchain; deselection: exact Emscripten rebuild.
10. `cmp -s prg32_construction_kit/sso_protocol.py ../CartridgeStore/cartridge_store/sso_protocol.py` — **pass**.

## Mandatory scenario coverage

| Scenario | Result |
|---|---|
| A Guest policies | Missing. Offline scratchpad works but is not configurable guest project policy/storage. |
| B Registered student | CRUD/history/import/export/isolation automated; autosave conflict/cloud/provider cases missing. |
| C Three language modes | Source validation/generation tested; real local builds blocked by missing toolchain. |
| D Debugger parity | Machine-level differential suite passes; source/DWARF/block portions missing. |
| E Academic SSO | Source inspection only; required profile incomplete and no IdP tenant. |
| F CartridgeStore | 94 egress and publisher-review tests available/passing locally; no live public publication. |
| G Security/performance/a11y | Chrome CSP/offline/keyboard/axe tests passed; no screen reader, performance/memory budget, or Linux sandbox rerun. |

No hardware, iOS, external IdP/cloud, live Store, new cartridge, exact WASM rebuild or CI-run result is claimed.
