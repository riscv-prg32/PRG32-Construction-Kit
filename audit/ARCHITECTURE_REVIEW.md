# Architecture review

## Implemented flow

`Browser (Bootstrap/jQuery/Blockly/textareas)` → authenticated Flask CRUD → SQLite/PostgreSQL-compatible models → validated Blocks IR or validated source → deterministic C/assembly → isolated PRG32 builder → `.prg32`/Store bundle → download, WASM Player, or reviewed Store upload.

The Player is not the JavaScript teaching simulator: it loads a Qt-free PRG32-QT RV32IMAC core compiled to WebAssembly. `static/wasm/BUILD.json` pins PRG32-QT `f6d80add…`, ABI 1.6/hash `0x260f6136`, and file hashes. Differential tests compare native and WASM state/framebuffer. This is the strongest reference-backed part of the design.

## Trust boundaries

1. Browser→Flask: signed-in guard, cookies/tokens, owner filtering and stale-window `X-PRG32-User` refusal.
2. Archive→storage: bounded ZIP parsing, traversal/symlink checks, ownership and transactional import.
3. Source→compiler: validators plus production-required bubblewrap, one writable build directory, no network, clear environment, seccomp and rlimits (`build_sandbox.py`; ADR-0010).
4. Flask→Store: approved origins, DNS/IP validation, pinned address, TLS hostname validation, no redirect and bounded replies; publish adds publisher authorization and signed confirmation.
5. Cartridge→WASM: guest memory/instruction limits and pinned provenance; browser stress evidence remains incomplete.
6. Kit↔Store identity: shared signed ticket/sync protocol; files are byte-identical at inspected SHAs.

## Cross-repository consistency

- Construction Kit: `6b7aac93554bcdbbeeb0c7b80fcad576b1a9bea6` (`development`).
- PRG32: `679dfb58783bd007125de9ca0b75eaa077908739` (`main`).
- PRG32-QT: `f6d80addf49d0512c2e4390251a81d797a35b157` (`main`), exactly the WASM build input.
- CartridgeStore: `820f74bfe9364c8727db92cb0f15f3b9dd85feab` (`main`).

Generated assembly targets RV32IM while the runtime accepts RV32IMAC; this is a compatible subset. Handwritten assembly may use compressed instructions. No incompatible ABI duplicate was demonstrated, but `publishing.py` and `build_check.py` duplicate selected cartridge/manifest constants and should consume a versioned shared contract.

## Maintainability

Strengths are explicit educational code, deterministic generators, inspectable sources, per-build folders, readable ADRs, and focused negative tests. Risks are a growing generic CRUD surface, hand-rolled migrations, CDN-coupled frontend, duplicated schemas, and stale `docs/architecture/current-state.md`. The missing IDE should make block→IR→C/assembly→address mapping a first-class deterministic artifact rather than retrofit it later.
