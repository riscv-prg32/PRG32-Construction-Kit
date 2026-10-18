# Architecture review

## Implemented flow

`Browser (Bootstrap/jQuery/Blockly or textarea)` → authenticated Flask CRUD → SQLite metadata/ownership → validated Blocks IR or validated handwritten source → deterministic C/assembly artifacts → per-build directory and PRG32 builder subprocess → `.prg32` plus Store bundle → download, WebAssembly Player, or Store upload.

The browser Player loads the Qt-free PRG32-QT core compiled to WASM. Its C API exposes cartridge loading, framebuffer/audio/input, deterministic timing and debugger state. Tests compare this module with a native harness built from the same core and, for graphics, PRG32-QT headless (`tests/test_wasm_runtime.py:126-163`). This satisfies the central architectural requirement that real guest instructions execute rather than a JS behavioral facsimile.

## Trust boundaries

1. Browser to Flask: cookies/API tokens and owner checks. Strong negative IDOR/account-switch tests exist.
2. Imported archives/assets to storage: ZIP entries are parsed/limited rather than blindly extracted; format and ownership tests are strong.
3. Student source to compiler: syntax validators and size/time/concurrency limits exist, but the compiler shares the server's OS identity and environment. This is the largest boundary defect.
4. Flask to Store: the former arbitrary-origin boundary is now constrained by an administrator allow-list, public-address checks, DNS pinning, no redirects and bounded responses (`store_policy.py`, ADR-0008). Local/private Stores require explicit trusted-local configuration.
5. Cartridge to WASM: guest memory and instruction budgets exist; committed binary provenance is recorded. Browser resource/memory stress evidence is incomplete.
6. Kit to peer Store SSO: signed/timestamped sync and one-time nonces. The shared protocol file matches the local Store source exactly.

## ABI/API consistency

- Construction Kit: `2ea8616f04e1b134d23e786acba2e536e6eef1e7`.
- PRG32: `679dfb58783bd007125de9ca0b75eaa077908739`.
- PRG32-QT: `f6d80addf49d0512c2e4390251a81d797a35b157`, exactly the `BUILD.json` core revision.
- CartridgeStore: `820f74bfe9364c8727db92cb0f15f3b9dd85feab`, local branch one commit behind its remote-tracking state.
- WASM record: ABI 1.6, hash `0x260f6136`; the SDK ABI test passed with `PYTHONPATH=../PRG32`.
- Generated assembly is RV32IM; the runtime interprets RV32IMAC. This is compatible (generated code is a subset), while handwritten assembly may use compressed instructions.

No incompatible duplicate ABI definition was proven. The build header parser in `build_check.py:23-32` duplicates selected cartridge-layout knowledge for smoke validation; it should ideally import a generated/shared schema to prevent drift.

## Portability and maintainability

Strengths: explicit educational Python/JS, deterministic generators, per-build folder design, readable ADRs, small C/WASM bridge, pinned upstream SHA and hashes, source comments preserved.

Risks: generic CRUD makes resource-specific policy easy to miss; Store URL validation has been added, but publication authorization still demonstrates the risk. External CDN UI dependencies conflict with classroom offline operation. SQLite migrations are hand-rolled and idempotent but lack a versioned migration/rollback tool for larger future schema changes. Server compilation is coupled to a locally configured command rather than a hardened build service.

The missing IDE shell/language services should be added without hiding generated C/assembly. Source maps should be first-class deterministic artifacts linking block IDs → IR nodes → C/assembly lines → addresses/DWARF.
