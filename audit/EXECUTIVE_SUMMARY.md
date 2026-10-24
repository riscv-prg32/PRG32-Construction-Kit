# Executive summary

Audit date: 2026-10-23 (Europe/Rome)

Audited revision: `ide/refine-after-e2d0cef` at `f5b3a0ff3f261f424172e57b30602026bd1ffaca`. The tracked tree was clean; pre-existing untracked local helper/refinement files are recorded in `audit/EVIDENCE_INDEX.md`.

Recommendation: **NO-GO**

The technical GDPR and documentation refinement is substantial. The repository
now has a generated field-level ROPA, layered notices and version records,
complete-account export, rectification/request tracking, erasure across every
known table and file, cloud-token revocation, restriction enforcement,
backup re-erasure, processor/transfer templates, a breach playbook and a
synthetic technical rehearsal. `GDPR-01` rises to **3/4**.

It still fails the release gate for an actual deployment: `docs/privacy/decisions.md`
leaves the controller identity, legal bases, Member-State rules, DPIA, DPO/counsel
review, retention choices, processor agreements, transfers and staffed breach
exercise open. The repository correctly labels itself NO-GO until those decisions
are made. This audit does not make a legal-compliance determination.

`DOC-02` rises to **4/4**. README and architecture now describe the current IDE,
WASM/debug/audio/account/cloud/Store/privacy boundaries. Generated diagrams,
synthetic screenshots, a complete visual manifest, reviewer/date records,
link/image/alt/name/ID checks and CI freshness gates passed inspection and tests.

The revision adds credible reference evidence beyond the previous audio work. A pinned Docker toolchain rebuilt all four authoring paths for ESP32-C6 and QEMU and matched macOS hashes. Canonical PRG32-QT stored, launched and drew five hashed cartridges. IDE C and assembly diagnostics now combine safe validator feedback with the actual PRG32 compiler after each saved edit. Fresh disposable HTTP tests verify shared Kit/CartridgeStore accounts, one-time sign-on tickets and publisher-authorized upload tickets. Documentation milestones now identify their commits.

Audio refinement is strong but still split between the Kit and proposed upstream patches. The SDK buzzer-retirement patch preserves slots 5/7/8 as silent compatibility entries while removing public names; the Qt patch makes the firmware engine the default and records frames accepted by a real macOS output device; the QEMU clock/reset patch brings most whole recordings into sample alignment. All apply and test against clean copies, but none is a canonical upstream revision. Physical stereo-console and human screen-reader sessions remain unperformed.

Fresh verification at `f5b3a0f`:

- GitHub Actions run `39924578831` completed successfully for the exact audited SHA;
- its production-image job passed the same-UID 300-process load, kernel/`/proc` evidence check, bubblewrap and disk-budget suites, real cartridge builds, AppArmor confinement, concurrent builds, fixture rebuilds and container health checks;
- focused local sandbox/documentation/capability selection: **234 passed, 8 platform skips**;
- documentation, visual manifest, generated diagrams and generated ROPA checks passed.

This is sufficient to raise `BLD-02` from 3/4 to **4/4**. `SEC-01` remains 3/4:
the specific RLIMIT_NPROC regression is closed, but builds still share a host UID
outside their namespaces.

Earlier fresh execution at `fe2e2c4`:

- broad feasible suite with disposable loopback/compiler-cache access: **1,332 passed, 57 skipped, 3 failed** in 271.00 s;
- all three failures are the new shared-identity assertions against the adjacent canonical CartridgeStore `4a3138b`, which does not contain the proposed Store patch;
- the new Linux-only kernel-count/process-limit regression test skipped on macOS, so the Docker-server fix remains implemented/tested by retained Linux evidence rather than freshly demonstrated here;
- browser suites remain unavailable on this host because Chrome/Playwright Chromium is absent.

The refinement chooses a coherent shared identity model (private shared username,
separate pseudonymous public handle) and supplies a substantial, tested patch for
CartridgeStore. Retained evidence reports 91 Store tests and 89 Kit cross-repository
tests passing against a clean patched clone. Because the patch is not merged into
canonical CartridgeStore and the default adjacent-repository suite still fails,
`SSO-04` remains 3/4 rather than closing.

Earlier fresh execution at `bb2b062`:

- privacy/documentation/security/new-feature selection: **441 passed, 1 skipped**;
- broad feasible suite with loopback and compiler-cache access: **1,330 passed, 56 skipped, 1 failed**;
- mandatory browser selection: **5 non-browser checks passed; 40 browser setups refused because Chrome/Playwright Chromium is absent**;
- documentation/capability consistency and generated-diagram/ROPA checks passed.

The earlier single reproducible failure was
`tests/test_sso_with_cartridge_store.py::test_kit_user_can_sign_in_to_the_store`:
the Store authenticates the Kit user but returns a generated `player-*` username
instead of the shared username `ada`. `SSO-04` is reduced to 3/4 pending a
contract decision or compatibility fix.

Earlier retained execution at `951f782`:

- focused cross-feature audit selection: **294 passed, 9 skipped**, plus five sandbox-denied delivery setups;
- delivery rerun with loopback permission: **8 passed**;
- mandatory Chrome suite: **88 passed**;
- live disposable Kit/CartridgeStore SSO and publishing suite: **11 passed**;
- broad feasible suite: **1,009 passed, 85 skipped, 1 deselected**, with only the five sandbox-denied delivery setups;
- syntax and locally feasible reproducibility checks passed; toolchain fixture rebuilds were verified from retained Docker evidence but could not run locally.

The expanded matrix score is **132/156 (84.6%)**. The recommendation remains
**NO-GO** because deployment-specific GDPR decisions/sign-off are open. Other
blockers are the unmerged shared-account Store patch, canonical upstream audio
patch adoption, physical PRG32 stereo/delivery evidence, complete QEMU/frame-event
alignment, human screen-reader evidence and unsupported iOS handoff.
