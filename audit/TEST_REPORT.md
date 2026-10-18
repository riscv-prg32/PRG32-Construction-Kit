# Test report

## Environment

- Date/time basis: 2026-10-18, Europe/Rome
- macOS host; filesystem-limited audit environment
- Python 3.12.10; pytest 8.4.2
- Node v26.12.0; npm 11.20.0
- Git 2.55.0; Docker 28.5.2; CMake 4.4.3; Apple clang 21.0.0
- Emscripten 6.0.12 present; its Homebrew cache directory was not writable in the audit sandbox
- Local PRG32 SDK present but its Python module/toolchain was not installed into the default environment
- No hardware, iOS app/source, cloud OAuth tenant, external IdP, or live Store publication

## Commands and results

1. `python3 -m compileall -q app.py prg32_construction_kit tests tools` — **pass**, no output.
2. `for file in static/js/*.js static/service-worker.js tools/*.mjs; do node --check "$file"; done` — **pass**, no output.
3. `python3 -m pytest -q -rs --junitxml=/tmp/prg32-kit-audit-pytest.xml` — **346 passed, 14 skipped, 1 failed**, 41.60 s.
   - 9 skips: assembly differential tests need RISC-V GCC and compatible host GCC.
   - 3 skips: real PRG32 toolchain absent (provenance, concurrency, handwritten assembly).
   - 1 skip: SDK Python ABI module absent from default `PYTHONPATH`.
   - 1 skip: kit-built cartridges in WASM need real toolchain.
   - Failure: `test_fresh_build_matches_the_committed_module`; compile reached final link, then Emscripten could not create `/opt/homebrew/.../cache/...json.lock` (`PermissionError: Operation not permitted`). This is an audit-environment restriction; no byte mismatch occurred.
4. `PYTHONPATH=../PRG32 python3 -m pytest -q -rs tests/test_project_format.py::test_sdk_abi_matches_the_prg32_sdk_when_installed tests/test_wasm_runtime.py -k 'not fresh_build_matches_the_committed_module'` — **30 passed, 1 skipped, 1 deselected**, 7.16 s. The skip is the real-toolchain Blocks/C/assembly cartridge test.
5. `shasum -a 256 static/wasm/prg32-core.js static/wasm/prg32-core.wasm` — **pass**: `5896c210…` and `3ba378fb…`, exactly matching `static/wasm/BUILD.json`.
6. `diff -u ../CartridgeStore/cartridge_store/sso_protocol.py prg32_construction_kit/sso_protocol.py` — **pass**, no differences.
7. `python3 tools/runtime_check.py` — **not executed**: command correctly refused because required `--prg32` was omitted during discovery. No runtime result is claimed from it.

No coverage plugin/report was available, so coverage percentage is unknown. No Docker image build was run: the rubric forbids treating CI history as execution, and a full network/toolchain image build was disproportionate after the local toolchain absence and release-blocking source findings were established.

## Scenario coverage

| Mandatory scenario | Result |
|---|---|
| Guest policies | Blocked/missing: guest mode not implemented. |
| Registered student CRUD/history/import/export/isolation | Automated tests passed; no Drive/OneDrive or real concurrent UI session. |
| Each language real build/run | Source generation/validation tests passed; local real build skipped for missing toolchain. CI definition exists but was not executed here. |
| Debugger parity | Passed automated native/WASM/Qt-core differential suite; no GUI browser automation or dedicated compressed fixture. |
| Academic SSO | Blocked: no IdP tenant; source inspection only, required contract incomplete. |
| CartridgeStore | Local protocol/unit integration tests passed; no live draft/publication and local checkout is one commit behind. |
| Security/performance/accessibility | Negative archive/ownership/security tests passed. No penetration, browser memory/latency, screen-reader, or full keyboard test. |

## Reproduction

From the audited commit, install `requirements.txt`, place PRG32 and PRG32-QT at the recorded SHAs in sibling directories, install Node/CMake/clang and the PRG32 toolchain, then run the commands above. For the byte-rebuild test, use the exact Emscripten string in `static/wasm/BUILD.json` with a writable Emscripten cache. The container CI path additionally runs `docker run ... tools/check_build.py --students 2 --windows 2` as defined in `.github/workflows/ci.yml`; that result was not independently reproduced here.
