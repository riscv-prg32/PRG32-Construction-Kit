# Test report

Audited HEAD: `fea31c02348af2adc28e96c3795d38ae18a8f8e9`.

| Gate | Result |
|---|---|
| Python compileall and JavaScript syntax | Pass |
| Service-worker lock, capability rendering, language-index reproduction | Pass |
| Store-contract fixture reproduction | Pass |
| Broad feasible suite | 815 passed, 63 skipped, 1 deselected |
| Required Chromium: offline, IDE, debugger, accounts, storage, cloud, frontend | 77 passed, no skips |
| Store contract + disposable live Store + SSO protocol | 45 passed |
| Store egress | 94 passed |
| Disposable live Keycloak | 9 passed |

The broad skips were browser cases rerun with skipping forbidden, opt-in live services, unavailable RISC-V/PRG32 toolchain, and Linux-only bubblewrap/RLIMIT cases. The four real-cloud tests remained skipped because no Google/Microsoft test-account credentials were available.

## Scenario assessment

| Scenario | Result |
|---|---|
| Guest and registered storage | Pass. |
| Academic identity/RBAC | Pass against unit providers and disposable Keycloak. |
| Cloud UX/provider contract | Pass against both fakes and Chromium; conditional against real tenants. |
| Store contract/publication | Pass against Store code and disposable live Store; no production Store touched. |
| Language services and debugger | Pass within documented scope. |
| Delivery | Incomplete: hardware, end-user Qt import and iOS unexecuted. |

## Revisions

- PRG32-Construction-Kit: `fea31c02348af2adc28e96c3795d38ae18a8f8e9`
- PRG32: `679dfb58783bd007125de9ca0b75eaa077908739`
- PRG32-QT: `f6d80addf49d0512c2e4390251a81d797a35b157`
- CartridgeStore: `820f74bfe9364c8727db92cb0f15f3b9dd85feab`
- WASM SHA-256 remains `3a19c44f2ead629196899ef187d8c87418d6277b90eadad07cff4052184d371f`.
