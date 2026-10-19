# Evidence index

## Repositories

| Repository | Branch | HEAD |
|---|---|---|
| PRG32-Construction-Kit | `ide/refine-after-731e378` | `5dd98a95a0f910091896eb1149d29a5f96265b3d` |
| PRG32 | `main` | `679dfb58783bd007125de9ca0b75eaa077908739` |
| PRG32-QT | `main` | `f6d80addf49d0512c2e4390251a81d797a35b157` |
| CartridgeStore | `main` | `820f74bfe9364c8727db92cb0f15f3b9dd85feab` |

Pre-existing untracked `.claude/` and root Claude notes were untouched. No network refresh was performed. PRG32-iOS was unavailable.

## Primary evidence

- Language design/index: ADR-0014; `tools/build_language_index.py`; `static/js/ide/language.js`; `monaco_language.js`; `tests/test_language_services.py`.
- Debug design/build/maps: ADR-0015; `debug_build.py`; `debug_info.py`; `source_maps.py`; generator markers; `tests/test_source_debugger.py`.
- Real-browser debugger: `tests/test_debugger_browser.py`; `source_debug.js`; `source_debugger.js`; Player template.
- Compressed/native/WASM parity: `tests/fixtures/debug/compressed.*`; `tests/test_wasm_runtime.py`.
- Owner-scoped API: `routes.py:936-1018`; source-debug API tests.
- CI browser enforcement: `.github/workflows/tests.yml:135-181`.
- Status consistency: `docs/capabilities.json`; `tests/test_doc_consistency.py`; `tests/test_capabilities.py`.

## Executed evidence

- Broad feasible suite: 614 passed, 37 skipped, 1 deselected.
- Focused language/debug/docs: 227 passed, 2 toolchain skips.
- Required Chrome suites: 65 passed.
- Store-egress: 94 passed.
- SDK ABI/WASM/native: 37 passed, 1 toolchain skip, 1 deselected.
- Syntax/reproducibility/diff checks passed.

## Missing evidence

1. Local regeneration of real-toolchain debug fixtures and three-mode cartridges.
2. Linux bubblewrap/debug-build rerun and total-disk exhaustion testing.
3. Exact Emscripten byte rebuild.
4. Guest/registered quota/conflict/deprovision lifecycle.
5. External academic IdP matrix.
6. Drive/OneDrive tenant tests.
7. Controlled live Store contract conformance.
8. Physical PRG32, Qt import and verified iOS handoff.
9. Screen-reader session, performance budgets, coverage, full SBOM and restore drill.
