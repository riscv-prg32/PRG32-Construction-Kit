# Test report

Audited HEAD: `e2d0cef834bbe75e1fd3fd5c2ea69ce7f1560954`.

## Executed locally

| Gate | Result |
|---|---|
| Python compileall and JavaScript `node --check` | Pass |
| Service-worker lock | Pass |
| Rendered capabilities check | Pass |
| Language-index reproducibility | Pass |
| Broad feasible pytest suite, excluding Store egress and exact WASM rebuild | 710 passed, 42 skipped, 1 deselected |
| Required Chromium suites: offline, IDE, debugger, accounts, storage, frontend | 74 passed, no skips |
| Store-egress suite | 94 passed |
| Capability and documentation consistency after score rendering | Pass |
| CartridgeStore SSO protocol comparison | Byte-identical |

Broad-suite skips were the separately rerun browser cases plus unavailable RISC-V/PRG32 toolchain, Linux bubblewrap/RLIMIT and exact WASM rebuild cases. Browser tests were rerun with `PRG32_REQUIRE_BROWSER=1`, so missing browser evidence would fail.

## Scenario assessment

| Scenario | Result |
|---|---|
| Guest classroom use | Pass: projects remain in IndexedDB; export/import, migration, capacity and clearing behavior covered. |
| Registered student | Pass: ownership, autosave, atomic conflict response, quotas and retention covered. |
| Academic identity | Conditional: signed fake-provider PKCE/ID-token/security matrix passes; no external tenant or SCIM. |
| Teacher/facilitator supervision | Pass: class-scoped, read-only boundaries and denial paths covered. |
| Language services | Pass within documented validator-derived scope. |
| Source/block debugging | Pass within documented optimized-code limits. |
| Store | Local policy passes; shared/live conformance remains unexecuted. |
| Cloud providers | Not implemented. |
| Delivery | Runtime evidence only; hardware/Qt import/iOS handoff unexecuted. |

## Revisions and immutable artifacts

- PRG32: `679dfb58783bd007125de9ca0b75eaa077908739`
- PRG32-QT: `f6d80addf49d0512c2e4390251a81d797a35b157`
- CartridgeStore: `820f74bfe9364c8727db92cb0f15f3b9dd85feab`
- committed WASM SHA-256: `3a19c44f2ead629196899ef187d8c87418d6277b90eadad07cff4052184d371f` (matches `static/wasm/BUILD.json`)
