# Current state

What the PRG32 repositories contain **now**: `development` at `7c83e71`
(audited as 127/156 in the GDPR and documentation audit, NO-GO) and the changes
after it listed under **Milestones**, read from source and from the test runs below. The per-requirement
status, with the source symbol and test behind every claim, is
`../capabilities.md` (generated from `../capabilities.json`). The lists below
are a summary of that file, and `tests/test_doc_consistency.py` fails when they
disagree with it. Audit scores belong to the auditor (`../../audit/`).

## Repositories

| Repository | Branch | Commit | Role |
| --- | --- | --- | --- |
| PRG32-Construction-Kit | `development` | `7c83e71` (audited); later work under Milestones | This repository. Flask + SQLAlchemy + Bootstrap + jQuery + Blockly + Monaco PWA, all served from `static/vendor/`. MIT. |
| PRG32 | `main` | `679dfb5` | SDK, firmware, `prg32` CLI, portable cartridge builder, ABI 1.6 (`prg32/abi/abi_generated.py`). Open, unmerged proposals from the kit: riscv-prg32/PRG32#45 (buzzer retired, ABI 1.7), #46 (audio frame clock, fresh mixer). |
| PRG32-QT | `main` | `f6d80ad` (0.4.1) | Qt host; its Qt-free `src/core` is compiled into the kit's browser runtime (`static/wasm/BUILD.json`). Open, unmerged proposal: riscv-prg32/PRG32-QT#1 (firmware audio engine). |
| CartridgeStore | `main` | `4a3138b` (GDPR remediation); the kit's CI pins `820f74b` | Store, accounts, `/api/publish/bundle` (pending review). `sso_protocol.py` identical to the kit's. From `4a3138b` the shared username needs the kit's proposal `docs/upstream/cartridge-store-shared-identity.patch` (not merged). |
| PRG32-iOS | `main` | `547fa45` (read 2026-10-18, not checked out here) | Private. Imports cartridges with a SwiftUI file importer; no URL scheme, no debugger. |

## Milestones

Every refinement phase and the audit that followed it. `tests/test_doc_consistency.py`
checks that each `Refinement phase` commit in the history is listed here by its
commit; a milestone is recorded once its commit exists.

| Milestone | Commit | Evidence |
| --- | --- | --- |
| Refinement phase 0: baseline, machine-checked capabilities | `62eb5bf` | `capabilities.json`, `tests/test_capabilities.py` |
| Refinement phase 1: self-contained frontend, root service worker, strict CSP | `903cba0` | ADR-0012, `tests/test_frontend_offline.py`, `tests/test_browser_offline.py` |
| Refinement phase 2: IDE shell with Monaco | `731e378` | ADR-0013, `tests/test_ide_browser.py` (audited: 70/132) |
| CI browser suite, documentation drift repair | `7910e86`, `9332c8c` | `tests/test_frontend_offline.py::test_ci_runs_every_browser_suite_and_forbids_skipping`, `tests/test_doc_consistency.py` |
| Refinement phase 3: offline language services | `a9f2c97` | ADR-0014, `tests/test_language_services.py` |
| Refinement phase 4: source and block debugger | `5dd98a9` | ADR-0015, `tests/test_source_debugger.py`, `tests/test_debugger_browser.py` (audited: 79/132) |
| Evidence drift repair after the audit of `5dd98a9` | `e91b68b` | `../evidence.md`, `tests/test_doc_consistency.py` |
| Refinement phase 5: academic identity and scoped roles | `4a5498a` | ADR-0016, `tests/test_identity.py`, `tests/test_authorization.py`, `tests/test_accounts_browser.py` |
| Refinement phase 6: guest and registered storage policy | `e2d0cef` | ADR-0017, `tests/test_storage_policy.py`, `tests/test_storage_browser.py` (audited: 93/132) |
| Release records and commit-specific CI evidence | `7a6aa9d883224b8d817a16fb9666bf325a42abbe` | `../evidence.md`, CI artifacts `*-<sha>` |
| Live school sign-in harness (disposable Keycloak) | `1ecfd61e010f2a0de6cb3c95182c4e2329e754c9` | `tests/test_identity_live.py`, `../identity_live_testing.md` |
| Shared Store contract, disposable live Store | `c6eb9482f4d1a479e91f8c3377d338d7d7e2098c` | ADR-0018, `tests/test_store_contract.py`, `tests/test_store_live.py` |
| Google Drive and OneDrive behind one interface | `fea31c02348af2adc28e96c3795d38ae18a8f8e9` | ADR-0019, `tests/test_cloud_storage.py`, `tests/test_cloud_browser.py` (audited: 103/132) |

| Audio on one frame clock; whole QEMU recordings equal; upstream PRs | `dc0222fa0e3fe93758c13931b7e266fa28a8446a` | ADR-0021, `tests/test_audio_conformance.py`, `../evidence/qemu-audio/2026-10-21-frame-clock/` |
| Live suites in one step | `7c83e716796ae8b2a5771173d885d5f20a390209` | `../live_testing.md`, `../evidence/live/2026-10-21/` (audited: 127/156) |
| Personal data: inventory, notices, rights, breach playbook | `d68a0e74ebe456102953b81f714211f2e68f9b96` | ADR-0022, `../privacy/`, `tests/test_privacy_rights.py`, `tests/test_privacy_records.py` |

How each kind of evidence is produced and checked: `../evidence.md`.

## Test runs (2026-10-21, macOS, at `ea005c9` plus the documentation work)

| Command | Result |
| --- | --- |
| `python3 -m pytest -q -rs` with `PRG32_REQUIRE_BROWSER=1 PRG32_REQUIRE_SDK=1`, `riscv32-esp-elf-gcc` 14.2.0 and `PYTHONPATH=../PRG32` | 1218 passed, 45 skipped |
| `tools/run_live_suites.py`: throwaway Store, disposable Keycloak 26.0.7, PRG32 firmware in QEMU | 11, 9 and 1 passed; school tenant and cloud accounts not run (none) |
| `tools/check_docs.py`, `build_diagrams.py --check`, `render_ropa.py --check`, `render_capabilities.py --check`, `service_worker_lock.py --check`, `ruff check .` | clean |

The 45 skips:

- run separately or without a service here: 11 live Store, 9 live OIDC, 7 live cloud, 1 live QEMU;
- Linux only: 6 bubblewrap, 1 `RLIMIT_AS`;
- 9 assembly/C differential tests that need a host GCC;
- 1 empty console-evidence set (no physical capture yet).

## Test runs (2026-10-19, macOS, at `5dd98a9`)

| Command | Result |
| --- | --- |
| `python3 -m pytest -q -rs` (no RISC-V toolchain) | 723 passed, 23 skipped |
| same with `riscv32-esp-elf-gcc` 14.2.0 and `PYTHONPATH=../PRG32` | 730 passed, 16 skipped |
| browser suites (`tests/test_*browser*.py`, `tests/test_frontend_offline.py`, Chrome) | 65 passed (`PRG32_REQUIRE_BROWSER=1`: no skips) |
| kit Docker image with the production sandbox (`bwrap`): `tests/test_build_sandbox.py`, `test_handwritten_assembly.py`, `test_source_debugger.py`; `tools/check_build.py` | pass (Node-based tests skip there; they run in the other jobs) |
| `compileall`, `node --check`, `service_worker_lock.py --check`, `render_capabilities.py --check`, `build_language_index.py --check`, `git diff --check` | clean |

Skips: 9 assembly/C differential tests need a host GCC (macOS has Apple clang);
6 bubblewrap escape tests need Linux user namespaces (they pass in the kit's
Docker image, see `../build_sandbox.md`); real-build and SDK-ABI tests need the
PRG32 toolchain/SDK; `RLIMIT_AS` is Linux-only. The browser suites skip without
Playwright and Chrome locally; the CI browser job sets `PRG32_REQUIRE_BROWSER=1`,
so there they run or fail. Emscripten 6.0.12 is installed; the WASM module
matches `static/wasm/BUILD.json`.

## What the kit is today

A **classroom PRG32 construction kit with an IDE shell**, not yet the Full IDE
of the design baseline (`../briefs/`, ADR-0011). Each line ends with its
capability IDs.

### Implemented

- IDE page `/ide/<id>`: project tree, editor tabs, Problems/Output/Preview/Run
  panels, status bar, command palette, F6 regions, keyboard-only use, phone
  layout, axe-core scan in a real browser (ADR-0013). [IDE-01]
- Offline language services for Advanced C and assembly: completion of the
  portable PRG32 ABI, allowed headers and directives, RV32IMC instructions and
  registers; hover, signature help, F12 into a generated `prg32.h (portable
  API)`; live problems at exact ranges that mirror the server's validators;
  compiler messages without server paths (ADR-0014). [IDE-03] [IDE-04]
- Versioned projects (Blocks, Advanced C, handwritten assembly), archives,
  migrations, history with identity-preserving restore, soft delete. [PRJ-01]
- Real `.prg32` builds from Blocks, C and assembly; every compile isolated by
  bubblewrap + seccomp + limits, with provenance and SHA-256. [BLD-01] [BLD-02]
- Browser runtime: the PRG32-QT core as WebAssembly, equal to the native core
  and `prg32qt-headless`. [WASM-01]
- Eight-voice audio in the browser: the PRG32 firmware's own engine (8 voices,
  SID-like synth, independent ADSR, samples, tracker) behind a host-call hook,
  checked against the audio contract on a toolchain-built fixture (ADR-0021). [AUD-01]
- AudioStudio, parallel to Sprite Lab: voice instruments with ADSR, sound
  effects, an 8-voice soundtrack grid and WAV samples, previewed through the
  same engine; one versioned asset per project; named blocks become fixed
  numbers in the generated C and assembly; the audio block is packed
  deterministically into the cartridge build. [AUD-03]
- Player debugger: pause, continue, restart, speeds, instruction/over/out
  stepping, address breakpoints, browser state equal to PRG32-QT's. [DBG-01] [DBG-02] [DBG-03] [DBG-06]
- Source and block debugging for kit-compiled cartridges (ADR-0015): a saved
  block → IR → source → address map, C/assembly line and block breakpoints
  with conditions, the running block highlighted, locals, globals, call stack
  from DWARF call-frame rules, watches, counter CSRs and a stack view, a
  compressed-instruction fixture; the cartridge is byte-identical to one built
  without debug information, and without it the Player stays address-level.
  [IDE-02] [DBG-04] [DBG-05]
- Accounts shared with CartridgeStore; authorized, reviewed, confirmed
  publishing behind a Store egress policy. [SSO-04] [STR-02]
- Academic identity (ADR-0016): OIDC Authorization Code + PKCE with verified ID
  tokens, accounts by issuer + subject (never joined by email), several
  admin-configured providers, explicit account linking; academic roles and
  classes with read-only supervision, scoped and expiring API tokens, session
  epochs, deprovisioning. [SSO-01] [SSO-02] [SSO-03]
- Storage policy (ADR-0017): guest games in the browser's IndexedDB with
  export/import and a move into the account after sign-in; conflict-safe
  project versions, IDE autosave, per-account quotas and retention of trash,
  builds and their folders. [ACC-01] [ACC-02]
- Threat model, SSRF controls, build isolation; CI, Docker, migrations,
  health; documentation and traceability. [SEC-01] [OPS-01] [DOC-01]
- Self-contained frontend: every library from `static/vendor/`, strict CSP,
  static-only service worker at `/` (ADR-0012).

### Partly implemented

- Store bundles against a shared versioned contract (ADR-0018), checked with the
  Store's own code and a throwaway live Store; Store gaps (repeated id/version,
  tokens without expiry) recorded. PRG32-QT delivery recorded through its web API
  (five kit cartridges stored, started and drawn on canonical PRG32-QT); the
  desktop Import menu was not used by a person. [STR-01] [DEP-02]
- Credentials, throttling and audit log; quality gates without lint, type,
  coverage or performance budgets. [SEC-02] [QLT-01]
- Personal data (ADR-0022, `docs/privacy/`): field-level record of processing,
  notices with recorded versions, rights workflows (export, request register,
  restriction, erasure across every table, folder, file and cloud token, backups
  re-apply), breach playbook and a technical rehearsal. The controller's legal
  decisions, DPO review, DPIA and a staffed exercise are open: NO-GO. [GDPR-01]
- Entry point and architecture documents being refreshed after the audit of
  7c83e71. [DOC-02]

- Google Drive and OneDrive behind one provider interface (ADR-0019), proven
  against in-process fakes and a real browser; no live tenant run yet.
  [CLD-01] [CLD-02]
- Browser host with framebuffer, input, timing and an offline subset; its
  stereo sound is the firmware engine's PCM, bit-identical in the native build
  and in PRG32-QT with the kit's proposed firmware-audio patch, and equal to the
  PRG32 firmware in QEMU over the whole recording (with the proposed SDK audio
  patch: one frame-clock scheduling boundary); no console recording yet (procedure, comparison
  tool and evidence check ready). [WASM-02] [AUD-02]
- Buzzer removal on the kit side: refused by the validators, obsolete-only in
  the editor, silent for old cartridges, guarded by a repository-wide test; the
  SDK's portable ABI still lists it (retirement delivered as a tested
  patch in `docs/upstream/`). [AUD-04]

### Not implemented

- Verified hardware delivery (a recording tool exists, no run recorded) and
  PRG32-iOS handoff (deferred, ADR-0020). [DEP-01] [DEP-03]

## Risks

1. **Scope gap:** delivery evidence (hardware, PRG32-QT import, iOS) and real
   cloud accounts are the largest missing pieces of the Full IDE. The language
   services follow the
   kit's rules and the SDK, not C semantics (no types or scopes).
2. **Sandbox deployment:** a confined AppArmor profile and disk budgets exist
   (`../build_sandbox.md`); builds still share one user id outside their
   namespaces (evaluated, ADR-0010 amendment).
3. **Accessibility:** automated axe-core scans and keyboard tests only; no
   screen-reader session has been run.
4. **External validation:** the kit has been run against **disposable local
   services** only: Keycloak 26.0.7 in Docker with a test realm
   (`tests/test_identity_live.py`) and a throwaway CartridgeStore on loopback with
   temporary data (`tests/test_store_live.py`). No production or institutional
   identity provider, no production Store, no real Google or Microsoft account, no
   PRG32 hardware and no iOS device has been used; claims about them are absent on
   purpose. Cloud storage is proven against in-process fakes of both providers.

---

## History: G0 discovery (2026-10-18, at `b360678`)

At the start of the Full IDE work the kit had Blocks, Advanced C, generated
C/assembly, server builds without a sandbox, an IR-level simulator, local
accounts and SSO with CartridgeStore, and Store publishing without an egress
policy or publisher gate. PRG32-QT's Qt-free core was identified as the browser
runtime (ADR-0003, done in G4). The baseline then was 187 passed, 10 skipped.
The ADRs in `../adr/` record every decision taken since.
