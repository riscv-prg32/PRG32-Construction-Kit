# Architecture review

## Current flow

`Browser IDE (Bootstrap/jQuery/Blockly/Monaco)` → authenticated Flask APIs → relational metadata plus disk artifacts → validated Blocks IR or validated source → deterministic C/assembly → sandboxed PRG32 toolchain → PRG32 cartridge/Store bundle → download, WASM Player or reviewed Store submission.

The IDE now adds a project tree, tabs, panels, palette and Monaco without replacing the classic editor or hiding generated sources. Blocks JSON remains canonical. Generated C, assembly and IR are read-only tabs. This is consistent with the educational constraints, but language intelligence and deterministic block/source/address maps are still architectural gaps.

The offline path is deliberately separate from authenticated storage: a root-scoped service worker caches only `/static/`, sends signed-in navigations to a static offline page on network failure, and supports a local Blockly scratchpad plus local PRG32 cartridge player. Chrome verified that pages/API answers are not cached.

## Trust boundaries

1. Browser→Flask: signed-in guards, owner filtering, stale-window identity header and strict CSP.
2. Browser dependencies: vendored with versions/licenses/hashes; no runtime third-party requests in Chrome tests.
3. Archive→storage: bounded parsing, traversal/symlink rejection and transactional ownership behavior.
4. Source→compiler: validators plus production-required bubblewrap, read-only dependencies, no network, cleared environment, seccomp and resource/process controls.
5. Flask→Store: approved origin/address policy plus publisher-only immutable review and confirmation.
6. Cartridge→WASM: pinned PRG32-QT core and bounded host interface; native/WASM/Qt differential evidence.
7. Service worker→user data: static-only cache was verified; offline scratchpad remains local and is not yet the requested guest-policy model.

## Cross-repository consistency

- Construction Kit: `731e378e811744ffecd4bf346d4f48a6715a13d2`.
- PRG32: `679dfb58783bd007125de9ca0b75eaa077908739`.
- PRG32-QT: `f6d80addf49d0512c2e4390251a81d797a35b157`, matching `static/wasm/BUILD.json`.
- CartridgeStore: `820f74bfe9364c8727db92cb0f15f3b9dd85feab`; `sso_protocol.py` is byte-identical.

Generated RV32IM is a compatible subset of the RV32IMAC runtime. No ABI contradiction was found. Selected cartridge/bundle constants remain duplicated locally and should move to a shared versioned contract.

## Maintainability risks

- `docs/capabilities.json` provides useful machine-checked evidence, but `docs/architecture/current-state.md` was not updated after phases 1–2 and contradicts it.
- The CI browser job omits the IDE browser suite, leaving the new shell's strongest regression proof outside CI.
- Monaco language intelligence and debugger source mapping should share one deterministic source-coordinate model rather than evolve independently.
- Migration tooling, quotas, metrics/restore operations and cloud conflict semantics remain immature.
