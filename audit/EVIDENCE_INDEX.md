# Evidence index

## Repositories

| Repository | HEAD |
|---|---|
| PRG32-Construction-Kit | `fea31c02348af2adc28e96c3795d38ae18a8f8e9` |
| PRG32 | `679dfb58783bd007125de9ca0b75eaa077908739` |
| PRG32-QT | `f6d80addf49d0512c2e4390251a81d797a35b157` |
| CartridgeStore | `820f74bfe9364c8727db92cb0f15f3b9dd85feab` |

## Primary evidence

- Identity: ADR-0016, `identity.py`, identity/authorization/live Keycloak suites.
- Storage/cloud: ADR-0017/0019, `cloud_storage.py`, guest/storage/cloud unit and browser suites.
- Store: ADR-0018, `contracts/prg32-store-contract-1.json`, fixture builder, contract/live/egress suites.
- Language/debug: ADR-0014/0015, reproducible index/fixtures and browser/native/WASM tests.
- CI: non-skipping browser job, disposable Store job, opt-in Keycloak job and commit-specific artifacts.

## Executed evidence

- Broad feasible suite: 815 passed, 63 skipped, 1 deselected.
- Required Chromium: 77 passed.
- Contract/disposable Store: 45 passed.
- Store egress: 94 passed.
- Disposable Keycloak: 9 passed.

## Missing external evidence

Real Google/Microsoft accounts; physical PRG32, end-user Qt import and iOS; Linux sandbox/resource exhaustion; real local cartridge/debug rebuild; exact Emscripten rebuild; screen reader, performance, complete SBOM and restore drill.
