# Executive summary

Audit date: 2026-10-21 (Europe/Rome)

Audited revision: `ide/refine-after-e2d0cef` at `7c83e716796ae8b2a5771173d885d5f20a390209`, with the pre-existing dirty documentation worktree recorded in `audit/EVIDENCE_INDEX.md`

Recommendation: **NO-GO**

The newly mandatory GDPR and documentation-freshness gates fail. There is no
maintained `docs/privacy/` area, field-level processing inventory/ROPA,
controller/processor and legal-basis decision record, complete data-subject
rights workflow, processor/transfer register, breach exercise, DPIA/DPO
determination, or qualified counsel/DPO approval. This is a technical and
operational evidence finding, not a legal conclusion that the deployment
violates the GDPR.

Documentation is extensive, but the root README still presents the older
Blocks/JavaScript-simulator product shape and omits the Full IDE, WASM runtime,
debugger, AudioStudio, account/cloud boundaries and privacy responsibilities.
`docs/architecture.md` has the same stale pipeline, and the repository has no
visual provenance/freshness manifest or automated complete link/image/claim
gate. These are release-blocking misrepresentations under `DOC-02`.

The revision adds credible reference evidence beyond the previous audio work. A pinned Docker toolchain rebuilt all four authoring paths for ESP32-C6 and QEMU and matched macOS hashes. Canonical PRG32-QT stored, launched and drew five hashed cartridges. IDE C and assembly diagnostics now combine safe validator feedback with the actual PRG32 compiler after each saved edit. Fresh disposable HTTP tests verify shared Kit/CartridgeStore accounts, one-time sign-on tickets and publisher-authorized upload tickets. Documentation milestones now identify their commits.

Audio refinement is strong but still split between the Kit and proposed upstream patches. The SDK buzzer-retirement patch preserves slots 5/7/8 as silent compatibility entries while removing public names; the Qt patch makes the firmware engine the default and records frames accepted by a real macOS output device; the QEMU clock/reset patch brings most whole recordings into sample alignment. All apply and test against clean copies, but none is a canonical upstream revision. Physical stereo-console and human screen-reader sessions remain unperformed.

Fresh execution:

- focused cross-feature audit selection: **294 passed, 9 skipped**, plus five sandbox-denied delivery setups;
- delivery rerun with loopback permission: **8 passed**;
- mandatory Chrome suite: **88 passed**;
- live disposable Kit/CartridgeStore SSO and publishing suite: **11 passed**;
- broad feasible suite: **1,009 passed, 85 skipped, 1 deselected**, with only the five sandbox-denied delivery setups;
- syntax and locally feasible reproducibility checks passed; toolchain fixture rebuilds were verified from retained Docker evidence but could not run locally.

The expanded matrix score is **127/156 (81.4%)**: `GDPR-01` is **0/4** and
`DOC-02` is **1/4**. The former 37-row assessment remains useful for the
implementation baseline, but its bounded GO statement is superseded by the new
hard gates. Other blockers remain canonical upstream audio-patch adoption,
physical PRG32 stereo evidence, complete QEMU/frame-event alignment, human
AudioStudio screen-reader evidence, physical-console delivery, and iOS handoff.
