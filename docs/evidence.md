# How the evidence is made

The status of every requirement is in `capabilities.json` (rendered as
`capabilities.md`). Each claim there names source code and tests. This page
says how those tests and the other checks are run, so a teacher, an
administrator or an auditor can repeat them.

## Checks that run on every push and pull request (CI)

| Check | What it proves | Where |
| --- | --- | --- |
| Full pytest suite, Python 3.11 and 3.12 | backend, generators, validators, maps, documentation consistency | `test` job |
| Real-browser suites with `PRG32_REQUIRE_BROWSER=1` | offline page and player, CSP, IDE keyboard and accessibility, language services offline, the source and block debugger (audit scenario D). A missing browser **fails** the job; it cannot pass by skipping. Results: `browser-test-results.xml` | `browser` job: `tests/test_browser_offline.py`, `tests/test_ide_browser.py`, `tests/test_debugger_browser.py`, `tests/test_frontend_offline.py` |
| Browser core = native core | the WebAssembly core runs cartridges, steps, stops at breakpoints (also at source-line checkpoints) exactly like PRG32-QT's core compiled natively | `wasm-runtime` job: `tests/test_wasm_runtime.py` |
| Real cartridges in the kit's Docker image, inside the production sandbox | builds are isolated; debug builds give byte-identical cartridges; disk budgets and debug-reader fuzzing on Linux; the sandbox and disk tests again confined by `docker/apparmor/prg32-kit` with Ubuntu's user-namespace restriction on (bubblewrap required, no skipping) | `container-smoke-test` job; evidence kept as `container-evidence-<sha>` |
| Cloud storage behaves the same with Google Drive and OneDrive | one contract against fakes of both (consent, tokens, conflicts, expiry, revocation, outages, account switching); real browser dialog | `test` and `browser` jobs: `tests/test_cloud_storage.py`, `tests/test_cloud_browser.py`; real accounts opt-in: `tests/test_cloud_live.py` |
| Kit and Cartridge Store agree on the shared Store contract | generated fixtures through both codes; real publishes to a throwaway Store (visibility, updates, repeated id/version, refusals, revoked token, network loss and retry) | `store-contract` job: `tests/test_store_contract.py`, `tests/test_store_live.py`; evidence kept as `store-contract-results-<sha>` |
| School sign-in against a real OpenID Connect provider (opt-in) | PKCE, state, expiry, audience, key rotation, collision/linking, deactivation, local logout with Keycloak 26.0.7 | `live-identity` job (manual), `tests/test_identity_live.py`, `identity_live_testing.md` |

## Generated files and how they are kept honest

| File | Made by | Check |
| --- | --- | --- |
| `capabilities.md` | `python3 tools/render_capabilities.py` | `--check`; `tests/test_capabilities.py` |
| `static/js/ide/prg32_language_index.js` (editor suggestions, ADR-0014) | `python3 tools/build_language_index.py` from the PRG32 SDK and the kit's validators | `--check`; `tests/test_language_services.py::test_index_is_up_to_date_with_the_sdk` (where the same SDK is checked out) |
| `tests/fixtures/debug/*` (debugger fixtures, ADR-0015) | `python3 tools/build_debug_fixtures.py` with the real toolchain; `BUILD.json` records the SDK revision and compiler | `--check`; `tests/test_source_debugger.py::test_fixtures_are_what_the_toolchain_makes` (skips when the SDK or compiler differ from `BUILD.json`) |
| `static/service-worker.lock.json` | `python3 tools/service_worker_lock.py` | `--check` fails when cached files change without a new cache name |
| `static/wasm/*` (browser core) | `python3 tools/build_wasm.py` with Emscripten | `tests/test_wasm_runtime.py::test_committed_module_matches_its_build_record` |

## Cartridge and debug identity

- Every build compiles with debug information on the side and checks that the
  ELF's code equals the cartridge's code byte for byte; otherwise the debug
  information is dropped (`debug_info.matches_cartridge`).
- `tests/test_source_debugger.py::test_real_debug_build_gives_the_same_cartridge`
  builds the same game with and without debug information and compares the
  SHA-256 of the cartridges (needs the toolchain; runs in the Docker job).
- The debug ELF is never served; debug maps keep file names only.

## Status documents

`architecture/current-state.md` lists every capability ID once, under its
status; `[ID]` tags anywhere in `docs/` must agree with `capabilities.json`;
the milestone table must name every refinement-phase commit. All three are
checked by `tests/test_doc_consistency.py`. Audit scores are written only by
the auditor.
