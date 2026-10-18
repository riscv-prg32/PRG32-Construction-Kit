# Executive summary

Audit date: 2026-10-18 (Europe/Rome)  
Audited revision: `development` at `2ea8616f04e1b134d23e786acba2e536e6eef1e7`
Recommendation: **NO-GO for the advertised Full IDE release**

The current repository is a credible classroom construction kit with unusually strong deterministic Blocks generation, project ownership tests, a real PRG32-QT-derived WebAssembly runtime, and useful address-level debugging. It is not the Full IDE described by the audit matrix. The repository's own status page agrees: the IDE shell is not started, identity/storage and toolchain work are in progress, and delivery/release work is not started (`docs/implementation-status.md:8-16`).

The NO-GO is driven by release-gate gaps, not by the raw score:

1. Publishing has no publisher-role authorization and no explicit confirmation. The endpoint accepts both `store_bundle` and non-publishable `source_bundle` artifacts (`routes.py:989-1029`); the UI publishes on one click (`static/js/publish.js:51-56`).
2. Student C/assembly builds invoke a host subprocess with time and concurrency limits but without an OS sandbox, filesystem isolation, syscall/network policy, or per-build UID (`packager.py:117-150`). The validators reduce file-read syntax but explicitly state they are not a sandbox (`source_project.py:64-70,141-146`).
3. The claimed Full IDE core is absent: no JetBrains-style shell, Monaco, completion/navigation, project tree, command palette, or language services (`templates/editor.html:63-83`; `docs/traceability.md:32`).
4. Guest policy/IndexedDB, Drive, OneDrive, full academic RBAC, DWARF/source debugging, hardware delivery, and iOS handoff are missing or unverified.

## Verified strengths

- The unchanged core suite passed 346 tests with 14 expected toolchain/host-GCC/SDK skips. All 94 new Store-egress tests passed separately with loopback sockets enabled. Syntax checks passed.
- With `PYTHONPATH=../PRG32`, the SDK ABI check and all feasible committed-WASM/native/PRG32-QT differential tests passed: 30 passed, 1 real-toolchain test skipped, 1 reproducibility test intentionally deselected after its environment-only failure was captured.
- H-01 is independently closed: approved-origin validation, address classification, DNS pinning, no redirects, TLS hostname verification, bounded responses and safe errors are implemented in `store_policy.py`/`publisher.py` and exercised by the 94-test adversarial suite.
- The committed WASM JS and binary hashes match `static/wasm/BUILD.json`, pinned to PRG32-QT `f6d80add…` and ABI 1.6 hash `0x260f6136`.
- The local Construction Kit and PRG32-QT SHAs exactly match the recorded SDK/core inputs. `sso_protocol.py` is byte-identical to the local CartridgeStore copy.
- Ownership, account-switch refusal, token redaction, archive validation, deterministic archive behavior, history, build-folder separation, throttling, and audit logging have meaningful automated coverage.

## Limitations

No physical PRG32 hardware, browser UI automation, external IdP tenant, live public Cartridge Store publication, Drive/OneDrive tenant, PRG32-iOS source, or real local PRG32 build toolchain was used. No claim is made for those scenarios. Store transport was exercised only against local HTTP/TLS test servers. The local CartridgeStore checkout is one commit behind its remote-tracking branch; network refresh was not performed. The named design input `CLAUDE_PRG32_CONSTRUCTION_KIT_IMPLEMENTATION.md` was not found.

The scored coverage is **61/128 (47.7%)** across 32 applicable rows. Scores are evidence-weighted and do not override the blockers above.
