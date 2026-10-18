# Evidence index

## Repositories

| Repository | Branch | HEAD | Notes |
|---|---|---|---|
| PRG32-Construction-Kit | `development` | `731e378e811744ffecd4bf346d4f48a6715a13d2` | Untracked `.claude/` and two root Claude notes were pre-existing and untouched. |
| PRG32 | `main` | `679dfb58783bd007125de9ca0b75eaa077908739` | Local reference checkout. |
| PRG32-QT | `main` | `f6d80addf49d0512c2e4390251a81d797a35b157` | Matches WASM build record. |
| CartridgeStore | `main` | `820f74bfe9364c8727db92cb0f15f3b9dd85feab` | Shared protocol identical. |

No network refresh was performed. PRG32-iOS was unavailable.

## Primary source evidence

- IDE shell: `templates/ide.html`; `static/js/ide/ide.js`; `static/js/ide/shell.js`; `static/js/ide/monaco_setup.js`; ADR-0013.
- Offline/CSP/vendor: `prg32_construction_kit/__init__.py`; `static/service-worker.js`; `static/vendor/VENDOR.json`; ADR-0012.
- Browser tests: `tests/test_browser_offline.py`; `tests/test_ide_browser.py`; test-only axe 4.10.2.
- Machine-checked status: `docs/capabilities.json`; `tools/render_capabilities.py`; `tests/test_capabilities.py`.
- Debug gaps: `docs/capabilities.md:20-24`; `docs/implementation-status.md:61-63`.
- Identity/cloud/storage gaps: `docs/capabilities.md:25-32`.
- Build isolation: `build_sandbox.py`; `build_guard.py`; ADR-0010.
- Publish/Store controls: `store_policy.py`; `publishing.py`; `routes.py:990-1125`; ADR-0008/0009.
- CI omission: `.github/workflows/tests.yml:161-169`.
- Stale architecture claims: `docs/architecture/current-state.md:13,55-60`.

## Executed outputs

- Feasible main suite: 482 passed, 31 skipped, 1 deselected.
- Real Chrome suites: 10 passed.
- Store-egress: 94 passed.
- SDK ABI/WASM/native: 30 passed, 1 toolchain skip, 1 deselected.
- Syntax, service-worker lock, capability rendering and diff checks passed.
- SSO protocol comparison passed.

## Missing evidence

1. Real local Blocks/C/assembly builds and new cartridge/header inspection.
2. Exact Emscripten byte rebuild.
3. Linux/container sandbox escape run in this audit.
4. DWARF/source/block debugger scenario D.
5. Guest policy and registered quota/conflict lifecycle.
6. External academic IdP matrix.
7. Drive/OneDrive tenant tests.
8. Live controlled Store conformance.
9. Physical PRG32, user-facing Qt import and verified iOS handoff.
10. Screen-reader session, performance/memory budgets, coverage, SBOM and restore drill.
