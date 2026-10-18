# Executive summary

Audit date: 2026-10-18 (Europe/Rome)

Audited revision: `development` at `6b7aac93554bcdbbeeb0c7b80fcad576b1a9bea6`

Recommendation: **NO-GO for a Full IDE release**

The repository is a credible, well-tested classroom construction kit, but it is not the Full IDE defined by the audit brief. The central browser runtime is real: the committed WebAssembly module is built from the Qt-free PRG32-QT core, its hashes and pinned revision match, and native/WASM differential tests pass. Deterministic project formats, generated sources, ownership checks, publishing controls, and build isolation also have meaningful automated coverage.

The release gate still fails because mandatory product scope is absent: the editor is a Blockly workspace plus plain C/assembly textareas rather than an IDE shell; guest mode, cloud sync, academic OIDC/RBAC, DWARF/source debugging, and verified hardware/iOS delivery are missing or unverified. Mandatory debugger scenario D cannot be completed because locals, call stack, watches, source breakpoints, and active Blockly mappings do not exist (`docs/implementation-status.md:54-63`).

The earlier H-01/H-02/H-03 security blockers are closed at this revision by Store-egress controls, publisher-only signed review/confirmation, and a production-required bubblewrap build sandbox. Source inspection and targeted tests support those closures. The Linux/container escape tests could not be independently rerun on this macOS sandbox, so that portion remains implemented but externally unverified in this run.

## Verified coverage

- Python and JavaScript syntax checks passed.
- The clean local suite (excluding loopback-only Store tests and the exact WASM rebuild) passed; targeted publish/sandbox tests passed **34**, with **7** platform skips.
- PRG32-QT is exactly the revision recorded in `static/wasm/BUILD.json`; committed WASM hash matches; native/WASM tests passed except the real-toolchain skip and a cache-permission-only rebuild failure.
- `prg32_construction_kit/sso_protocol.py` is byte-identical to the local CartridgeStore copy.
- Store publish now enforces `publisher`, publishable cartridge bundles, signed immutable review, explicit confirmation, and idempotent attempts (`routes.py:1004-1125`).
- Production builds refuse fallback when bubblewrap is unavailable and constrain namespaces, mounts, environment, syscalls, resources, and process lifetime (`build_sandbox.py:1-20,219-239`; `packager.py:115-160`).

## Limitations

No physical PRG32 hardware, browser automation, screen reader, external IdP, Drive/OneDrive tenant, live CartridgeStore publication, PRG32-iOS checkout, or locally installed PRG32 cartridge toolchain was used. Docker daemon access and loopback socket binding were denied by this audit environment. The exact Emscripten rebuild reached linking but could not write its Homebrew cache. These are recorded as blocked, not passed.

The scored coverage is **64/128 (50.0%)** across 32 applicable rows. A numeric score does not override the missing mandatory Full IDE and debugger behavior.
