# Test report

## Environment

- Date/time basis: 2026-10-18, Europe/Rome
- macOS host; filesystem-limited audit environment
- Python 3.12.10; pytest 8.4.2
- Node v26.12.0; npm 11.20.0
- Git 2.55.0; Docker 28.5.2; CMake 4.4.3; Apple clang 21.0.0
- Emscripten 6.0.12 present; its Homebrew cache directory was not writable in the audit sandbox
- Local PRG32 SDK present but its Python module/toolchain was not installed into the default environment
- No hardware, iOS app/source, cloud OAuth tenant, external IdP, or live public Store publication

## Commands and results

1. `python3 -m compileall -q app.py prg32_construction_kit tests tools` — **pass**, no output.
2. `for file in static/js/*.js static/service-worker.js tools/*.mjs; do node --check "$file"; done` — **pass**, no output.
3. `python3 -m pytest -q -rs --junitxml=/tmp/prg32-kit-reaudit-pytest.xml` — **429 passed, 14 skipped, 2 failed, 10 setup errors**, 43.47 s.
   - 9 skips: assembly differential tests need RISC-V GCC and compatible host GCC.
   - 3 skips: real PRG32 toolchain absent (provenance, concurrency, handwritten assembly).
   - 1 skip: SDK Python ABI module absent from default `PYTHONPATH`.
   - 1 skip: kit-built cartridges in WASM need real toolchain.
   - Ten Store transport tests errored, and one TLS transport test failed, solely because the restricted first run could not bind `127.0.0.1`. They were rerun successfully with loopback permission (command 4).
   - The other failure was `test_fresh_build_matches_the_committed_module`; compile reached final link, then Emscripten could not create `/opt/homebrew/.../cache/...json.lock` (`PermissionError: Operation not permitted`). This is an audit-environment restriction; no byte mismatch occurred.
4. `python3 -m pytest -q -rs tests/test_store_egress.py` with local loopback permission — **94 passed**, 7.76 s. This independently exercised HTTP/TLS transport, DNS pinning, redirects, response bounds, safe errors and API policy.
5. `python3 -m pytest -q -rs --ignore=tests/test_store_egress.py -k 'not fresh_build_matches_the_committed_module'` — **346 passed, 14 skipped, 1 deselected**, 39.64 s.
6. `PYTHONPATH=../PRG32 python3 -m pytest -q -rs tests/test_project_format.py::test_sdk_abi_matches_the_prg32_sdk_when_installed tests/test_wasm_runtime.py -k 'not fresh_build_matches_the_committed_module'` — **30 passed, 1 skipped, 1 deselected**, 7.20 s. The skip is the real-toolchain Blocks/C/assembly cartridge test.
7. `shasum -a 256 static/wasm/prg32-core.js static/wasm/prg32-core.wasm` — **pass**: `5896c210…` and `3ba378fb…`, exactly matching `static/wasm/BUILD.json` (unchanged from the baseline audit).
8. `diff -u ../CartridgeStore/cartridge_store/sso_protocol.py prg32_construction_kit/sso_protocol.py` — **pass**, no differences (unchanged from the baseline audit).

No coverage plugin/report was available, so coverage percentage is unknown. No Docker image build was run: the rubric forbids treating CI history as execution, and a full network/toolchain image build was disproportionate after the local toolchain absence and release-blocking source findings were established.

## Scenario coverage

| Mandatory scenario | Result |
|---|---|
| Guest policies | Blocked/missing: guest mode not implemented. |
| Registered student CRUD/history/import/export/isolation | Automated tests passed; no Drive/OneDrive or real concurrent UI session. |
| Each language real build/run | Source generation/validation tests passed; local real build skipped for missing toolchain. CI definition exists but was not executed here. |
| Debugger parity | Passed automated native/WASM/Qt-core differential suite; no GUI browser automation or dedicated compressed fixture. |
| Academic SSO | Blocked: no IdP tenant; source inspection only, required contract incomplete. |
| CartridgeStore | Store egress transport passed 94 local HTTP/TLS tests; shared protocol/unit integration tests passed. No live public draft/publication; local checkout is one commit behind. |
| Security/performance/accessibility | Negative archive/ownership/security tests passed. No penetration, browser memory/latency, screen-reader, or full keyboard test. |

## Reproduction

From the audited commit, install `requirements.txt`, place PRG32 and PRG32-QT at the recorded SHAs in sibling directories, install Node/CMake/clang and the PRG32 toolchain, then run the commands above. For the byte-rebuild test, use the exact Emscripten string in `static/wasm/BUILD.json` with a writable Emscripten cache. The container CI path additionally runs `docker run ... tools/check_build.py --students 2 --windows 2` as defined in `.github/workflows/ci.yml`; that result was not independently reproduced here.
