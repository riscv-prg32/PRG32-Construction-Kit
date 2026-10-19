# Test report

## Environment

- 2026-10-19, Europe/Rome; macOS.
- Python 3.12.10; pytest 8.4.2; Node v26.12.0; Playwright 1.64.0; installed Google Chrome.
- PRG32 `679dfb5`; PRG32-QT `f6d80ad`; CartridgeStore `820f74b`.
- No local RISC-V/PRG32 toolchain or bubblewrap.

## Commands and results

1. `python3 -m compileall -q app.py prg32_construction_kit tests tools` — pass.
2. JS syntax over `static/js/*.js`, `static/js/ide/*.js`, service worker and tool modules — pass.
3. `service_worker_lock.py --check`, `render_capabilities.py --check`, `build_language_index.py --check`, `git diff --check` — pass.
4. Broad feasible suite excluding loopback Store and exact WASM rebuild — **614 passed, 37 skipped, 1 deselected**, 57.75 s. Browser skips were rerun in command 6.
5. Focused language/source-debug/doc/capability/frontend suite — **227 passed, 2 skipped**, 4.15 s. Skips require the real PRG32 toolchain.
6. `PRG32_REQUIRE_BROWSER=1 PRG32QT_DIR=../PRG32-QT python3 -m pytest -q -rs tests/test_browser_offline.py tests/test_ide_browser.py tests/test_debugger_browser.py tests/test_frontend_offline.py` — **65 passed**, 21.92 s.
7. `python3 -m pytest -q -rs tests/test_store_egress.py` with loopback permission — **94 passed**, 7.52 s.
8. SDK ABI plus `tests/test_wasm_runtime.py` excluding exact rebuild — **37 passed, 1 skipped, 1 deselected**, 12.10 s. Skip: real PRG32 toolchain.
9. Shared `sso_protocol.py` comparison and committed WASM SHA/build record — pass.

## Scenario coverage

| Scenario | Result |
|---|---|
| A Guest policies | Missing; offline scratchpad is not administrator-controlled guest storage. |
| B Registered student | CRUD/history/isolation covered; cloud, autosave conflicts, quotas and token lifecycle missing. |
| C Three language modes | Generation/validation covered; real local builds unavailable. |
| D Debugger parity | Passed in Chrome and Node/native/WASM fixtures: source/block breakpoints, active block, call stack, variables, watches, condition, CSR, stack, compressed instructions and fallback. |
| E Academic SSO | Incomplete source implementation; no external IdP execution. |
| F CartridgeStore | Local security/review suites passed; no live Store publication. |
| G Security/performance/a11y | CSP/offline/keyboard/axe/debug boundary tests passed; no Linux rerun, screen reader or performance budget. |

No hardware, iOS, external IdP/cloud, live Store, newly built cartridge, exact WASM rebuild or independently executed CI/container result is claimed.
