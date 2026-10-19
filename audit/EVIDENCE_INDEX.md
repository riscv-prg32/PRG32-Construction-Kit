# Evidence index

## Repositories

| Repository | HEAD |
|---|---|
| PRG32-Construction-Kit | `e2d0cef834bbe75e1fd3fd5c2ea69ce7f1560954` |
| PRG32 | `679dfb58783bd007125de9ca0b75eaa077908739` |
| PRG32-QT | `f6d80addf49d0512c2e4390251a81d797a35b157` |
| CartridgeStore | `820f74bfe9364c8727db92cb0f15f3b9dd85feab` |

## Primary evidence

- Identity/RBAC: ADR-0016; `identity.py`, `classes.py`; identity, authorization and account-browser tests.
- Storage: ADR-0017; `guest_store.js`, `storage_policy.py`, `retention.py`; storage unit/browser tests.
- Language/debugger: ADR-0014/0015; reproducible language index, source-map/debug fixtures and browser suites.
- Store/security: Store-egress, publish-authorization, sandbox and security-control tests.
- CI: required-browser job includes account and storage suites with `PRG32_REQUIRE_BROWSER=1`.
- Status: `docs/capabilities.json` rendered into `docs/capabilities.md` and consistency-tested.

## Executed evidence

- Broad feasible suite: 710 passed, 42 skipped, 1 deselected.
- Required Chromium suites: 74 passed, no skips.
- Store egress: 94 passed.
- Syntax, service-worker lock, capabilities, language index and protocol identity checks passed.

## Missing external evidence

Real institutional IdP/SCIM/logout; Drive/OneDrive; controlled live Store conformance; physical PRG32, Qt import and iOS handoff; Linux sandbox/resource exhaustion; real local cartridge/debug rebuild; exact Emscripten rebuild; screen reader, performance, complete SBOM and restore drill.
