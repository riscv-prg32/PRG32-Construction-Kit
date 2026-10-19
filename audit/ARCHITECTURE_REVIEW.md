# Architecture review

## Current architecture

`Browser IDE (Bootstrap/jQuery/Blockly/Monaco)` → authenticated Flask APIs → relational metadata/disk artifacts → validated Blocks IR or validated source → deterministic C/assembly → sandboxed PRG32 toolchain → PRG32 cartridge plus optional safe debug maps → WASM Player or reviewed Store submission.

Phase 3 uses a generated browser-only index built from pinned SDK headers, ABI data and validator allow-lists. Monaco adapters do not contact a language server. Portable ABI entries are suggested; resident-only functions are diagnosed. Server validation remains authoritative.

Phase 4 adds one coordinate chain: block ID → IR path → generated source lines → DWARF guest addresses. Generator markers are temporary and stripped; tests compare mapped output byte-for-byte with normal generation. Per-build compiler wrappers add only `-g` and `-fdebug-prefix-map`, capture the ELF inside the private build folder, and retain it only if its loadable image exactly matches the PRG32 cartridge. The ELF is converted to bounded JSON and never exposed.

## Trust boundaries

1. Browser dependencies and language services are same-origin, vendored, CSP-constrained and offline.
2. Browser→Flask retains authentication, ownership and stale-window checks.
3. Archive/source validation and the production build sandbox remain layered defenses.
4. Debug JSON is owner-scoped, path-sanitized, size/count-bounded and content-linked to its exact cartridge/source. Missing or malformed information falls back to address debugging.
5. Cartridge execution remains the pinned PRG32-QT core; source features translate to existing core addresses rather than replacing execution semantics.
6. Store egress and publishing retain approved-origin and signed-confirmation boundaries.

## Cross-repository consistency

- Kit: `5dd98a95a0f910091896eb1149d29a5f96265b3d`.
- PRG32 SDK: `679dfb58783bd007125de9ca0b75eaa077908739`; ABI 1.6/hash `0x260f6136` in the generated language index.
- PRG32-QT: `f6d80addf49d0512c2e4390251a81d797a35b157`; rebuilt WASM record matches this revision.
- CartridgeStore: `820f74bfe9364c8727db92cb0f15f3b9dd85feab`; shared protocol remains identical.

No incompatible ABI or debug-execution fork was demonstrated. Store/cartridge schema duplication remains a drift risk.

## Maintainability

The language index and debug fixtures have reproducibility checks, and documentation consistency is machine-tested. Remaining risks are the wrapper dependency on the upstream builder's invocation pattern, complex hand-written DWARF interpretation, optimized-code limitations, missing quotas/migrations for future storage work, and substantial external identity/cloud/device scope.
