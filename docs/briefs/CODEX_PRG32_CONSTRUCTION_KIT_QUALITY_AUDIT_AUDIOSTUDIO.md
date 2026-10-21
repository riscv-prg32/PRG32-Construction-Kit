# Codex independent audit brief — PRG32 Construction Kit Full IDE and AudioStudio

**Role:** Act as an independent senior code reviewer, security auditor, test engineer and architecture verifier. **Do not implement features during the initial audit.** Assess actual artifacts against the approved design, report evidence, then propose prioritized remediation. Do not trust implementation summaries without source/tests.

## Repositories and design inputs

- https://github.com/riscv-prg32/PRG32-Construction-Kit — implementation under review.
- https://github.com/riscv-prg32/PRG32 — canonical SDK, cartridge format, ABI, firmware/hardware behavior.
- https://github.com/riscv-prg32/PRG32-QT — canonical portable guest execution/debug semantics.
- https://github.com/riscv-prg32/CartridgeStore — actual authentication, bundle and publishing APIs.
- Verify the actual PRG32-iOS source/contract separately; record unknowns.
- Treat the current PRG32 audio contract in the canonical SDK, firmware and
  PRG32-QT sources as authoritative. The required target is **eight simultaneous
  SID-like voices with independent ADSR envelopes and stereo output**. The old
  buzzer is no longer supported and must not be accepted as evidence of audio
  compatibility.
- Design baseline: `CLAUDE_PRG32_CONSTRUCTION_KIT_IMPLEMENTATION.md` plus committed ADRs, traceability, requirements, test plans and relevant repository `AGENTS.md` files. Identify design conflicts explicitly.

## Audit operating rules

1. Capture each repo URL, branch, HEAD SHA, working-tree status, runtime/toolchain versions and environment. Inspect commits/diffs, not only README claims.
2. Read repo instructions, architecture, build scripts, dependency locks, CI and tests. Execute reproducible setup, lint, type checks, unit/integration/E2E tests, cartridge builds and conformance suites where feasible. Record exact commands, outputs, failures and skips. Never invent execution or hardware results.
3. Distinguish **implemented and verified**, **implemented but unverified**, **partial**, **missing**, **blocked**, and **not applicable**. A UI mock or stub is not a functional integration; a JS simulation is not evidence of actual guest ISA execution.
4. Examine production paths, negative tests and error handling. Check compatibility and security regressions in the pre-existing Construction Kit.
5. For each finding cite exact `path:line`, function/symbol, commit, failing test or artifact; include severity, user impact, reproduction, expected/actual behavior and recommended fix. Report uncertainty clearly.
6. Audit is read-only by default. Do not push, publish, alter infrastructure, rotate credentials, flash devices or make destructive changes.
7. Do not award audio credit for a beep-only oscillator, mono mix, call counter,
   silent stub, prerecorded golden answer, or obsolete buzzer path. Inspect and
   exercise the complete voice lifecycle and rendered stereo samples.
8. Search source, generators, Blockly definitions, language indexes, examples,
   documentation, archives and UI for `buzzer` and equivalent legacy APIs. Any
   reachable buzzer feature is a compatibility defect unless a documented import
   migration converts or rejects it explicitly without presenting it as supported.

## Required audit matrix

Score each row 0–4: **0 missing; 1 prototype/stub; 2 partial; 3 implemented with meaningful tests; 4 implemented, tested and demonstrated against reference.** Mark N/A with justification; do not inflate a score because a feature is planned.

| ID | Requirement / proof to demand |
|---|---|
| IDE-01 | JetBrains-inspired shell: project tree, tabs, panels, command palette, responsive UI, keyboard and accessibility |
| IDE-02 | Blockly remains editable; canonical block project, stable generation and block-to-source mapping |
| IDE-03 | C editing: Monaco syntax, completion, diagnostics, navigation and SDK awareness |
| IDE-04 | RISC-V Assembly editing: syntax, instruction/register/ABI completion, diagnostics |
| PRJ-01 | Versioned project schema, CRUD, assets, templates, imports/exports, autosave, migrations, history |
| BLD-01 | All 3 modes compile/link to **real** ABI-compatible `.prg32` artifacts |
| BLD-02 | Deterministic/reproducible builds, SDK/ABI validation, toolchain provenance and build diagnostics |
| WASM-01 | Browser runs guest RV32IMAC via Qt-free PRG32-QT core compiled to WASM (not fake JS semantics) |
| WASM-02 | Graphics/audio/input/timing/ABI compatibility, browser resource limits, offline behavior |
| AUD-01 | Canonical audio engine: all **8 SID-like voices** can sound simultaneously; each voice has independent waveform/pitch, gate, volume and ADSR attack/decay/sustain/release behavior accepted by the current portable PRG32 ABI |
| AUD-02 | **Stereo audio parity**: per-voice pan/routing and master mixing render distinct left/right PCM output consistently across firmware/reference behavior, PRG32-QT and browser/WASM; timing, clipping, silence, reset and deterministic test semantics are verified |
| AUD-03 | **AudioStudio** parallel to SpriteLab: create, preview, edit, duplicate, import/export and manage instruments, sound effects and soundtracks; arrange notes/events across 8 voices; edit ADSR and stereo placement; save versioned project assets and integrate them into Blocks/generated C/assembly and PRG32 cartridge packaging |
| AUD-04 | Obsolete buzzer removal: no buzzer blocks, APIs, generators, language completions, examples, feature declarations or runtime shims remain; legacy inputs receive an explicit, tested migration or clear unsupported-format diagnostic |
| DBG-01 | Speed control, play/continue, pause, stop/restart with consistent guest timing |
| DBG-02 | Instruction stepping, step into/over/out and RV32IMAC compressed-instruction correctness |
| DBG-03 | Source/address breakpoints, persistence, enable/disable, hit behavior |
| DBG-04 | All integer registers, PC, relevant CSRs, disassembly, memory, stack, watches |
| DBG-05 | C variables/call stack with DWARF; block variables/active-block mappings; graceful fallback |
| DBG-06 | Qt/browser differential debugging tests with reproducible state snapshots |
| ACC-01 | Admin-configurable guest policy, guest IndexedDB projects and export/eviction behavior |
| ACC-02 | Registered projects, privacy, ownership, quotas, versions, conflict handling and migrations |
| SSO-01 | OIDC PKCE/state/nonce/JWKS, issuer/audience, sessions, MFA delegation, logout |
| SSO-02 | Admin provider configuration, safe bootstrap, secrets, claim mapping, multiple IdPs |
| SSO-03 | Scoped RBAC: student, TA, teacher, publisher, admin; no privilege escalation |
| SSO-04 | CartridgeStore-aligned SSO and properly scoped publishing authorization |
| CLD-01 | Google Drive sync/import/export, OAuth scopes, refresh/revoke, conflicts |
| CLD-02 | OneDrive / Microsoft Graph sync/import/export, scopes and conflicts |
| STR-01 | Bundle wizard validates manifest, assets, version, hashes and Store contract |
| STR-02 | Authenticated draft/upload/publish/update with explicit confirmation and error recovery |
| DEP-01 | Verified physical-device transfer and launch workflow with integrity checks |
| DEP-02 | Verified PRG32-QT delivery/import workflow |
| DEP-03 | Verified PRG32-iOS handoff/import workflow, no invented app interface |
| SEC-01 | Threat model: untrusted builds, uploads, OAuth, SSRF, XSS, CSRF, IDOR, tenant isolation |
| SEC-02 | Secrets management, rate limiting, audit logs, retention/deprovisioning, dependency security |
| OPS-01 | CI, container deployment, migrations, TLS, backup/restore, logging/metrics |
| DOC-01 | Architecture ADRs, developer/admin/user docs, examples, API contracts, traceability |
| QLT-01 | Test reliability, regression coverage, code quality, error handling, accessibility/performance |

## Mandatory hands-on test scenarios

A. As a **guest** under each admin policy: create Blocks/C/Assembly projects, edit, build, run, debug, download, reload; verify denied operations and no unintended server persistence.

B. As a **registered student**: project CRUD, autosave, history, import/export, account switch isolation, Drive and OneDrive OAuth connection, concurrent edits/conflict, token expiry/revocation and network loss.

C. For **each language mode**: build and run a small arithmetic/control-flow fixture, graphics/audio/input fixture and one sample game; verify actual ELF/cartridge payload, portable ABI and host-independent artifact. Run on WASM and PRG32-QT; test hardware and iOS only when accessible, otherwise mark not verified.

C-audio. For the audio fixture, do not use a single beep as proof. Gate all eight
voices concurrently with deliberately different waveforms or canonical SID-like
timbres, pitches, ADSR envelopes, volumes and stereo positions. Capture left and
right PCM (or the canonical reference representation) at fixed virtual-time
checkpoints. Prove independent attack, decay, sustain and release transitions,
voice stealing/exhaustion behavior, clipping bounds, master volume, reset/stop,
silence after release and absence of cross-voice state corruption. Compare the
same cartridge on PRG32-QT and browser/WASM sample-for-sample when the reference
contract requires exact output, otherwise against documented numeric tolerances.
Hardware evidence must use the current stereo output path; a buzzer is invalid.

D. **Debugger parity:** start/pause/continue/stop, speed extremes, step one RV32I instruction, one compressed instruction, step over nested call, step out, breakpoint at source/address, inspect x0–x31/PC/memory, locals/globals and Blockly variables; compare browser vs Qt register/PC/memory state at fixed checkpoints. Validate pause does not corrupt guest state or change deterministic results.

E. **Academic SSO:** correct/incorrect issuer, audience, state, nonce, JWKS rotation, expired token, PKCE, redirect tampering, logout, multi-IdP collisions, first login, disabled user, group changes, locked-out admin recovery and publisher privilege boundaries. Test Store tokens are not reused as IDE sessions.

F. **CartridgeStore:** validate bundle, draft upload, unauthorized publish rejection, explicit publish confirmation, duplicate/version conflict, failed upload recovery, update and visibility behavior. Never publish a live public artifact merely to test without approval.

G. **Security/performance/accessibility:** malicious project files, oversized assets, zip-slip, path traversal, script injection, build sandbox escape attempts, cross-tenant reads, throttling, resource quotas, PWA offline start, screen reader/keyboard focus, browser memory and build latency.

H. **AudioStudio:** using keyboard-only controls and a screen reader where
available, create an instrument, an eight-voice soundtrack and several sound
effects; edit ADSR and stereo pan; solo/mute/preview voices; stop preview without
stuck notes; save/reload, duplicate, rename, delete, export and re-import assets;
attach them to a project; generate inspectable deterministic source; build a
PRG32 cartridge; and run it offline in the browser and in PRG32-QT. Test malformed,
oversized and version-mismatched audio assets, concurrent edits, ownership,
quotas, undo/history, autosave conflicts and missing assets. Confirm that neither
the UI nor generated code exposes a buzzer option.

## Cross-repository consistency checks

- Compare exact cartridge headers, metadata, ABI table/hash/version, instruction-set support and import conventions against PRG32 sources; test stale/mismatched ABI rejection.
- Compare the exact current audio ABI, voice count, voice numbering, waveform or
  instrument model, gate semantics, ADSR value ranges/timing, pan/routing, sample
  rate, sample representation, channel order, mixing/clipping, reset behavior and
  feature metadata across PRG32, PRG32-QT and the Construction Kit. Do not infer
  these values from old documentation.
- Trace audio end to end: AudioStudio/project asset -> versioned serialized format
  -> Blocks/validated IR -> deterministic generated source -> package manifest ->
  PRG32 cartridge -> runtime audio calls -> stereo samples. Verify missing or
  corrupt links fail clearly and never produce hidden nondeterministic content.
- Search every reviewed repository for obsolete buzzer definitions and distinguish
  dead historical material from reachable code. The audit must explicitly report
  whether buzzer support can still be selected, generated, compiled or executed.
- Inspect how PRG32-QT implements execution rate, stepping, pause, register/memory state and breakpoints. Identify whether browser uses the same core and where semantics diverge.
- Confirm Store endpoints, OAuth claims/scopes, publish permissions, bundle schema, validation and error codes against CartridgeStore source. Flag any fabricated or outdated contracts.
- Verify no incompatible duplicate definitions of cartridge schema, debug protocol, auth identity or asset encodings.
- Review licenses and provenance for bundled LLVM/WASM/Monaco/Blockly/Qt-related dependencies.

## Deliverables (write files in `audit/`)

1. `audit/EXECUTIVE_SUMMARY.md`: release recommendation **GO / CONDITIONAL / NO-GO**, critical blockers, verified coverage, limitations and concise risk summary.
2. `audit/REQUIREMENTS_MATRIX.md`: every matrix ID, score 0–4, status, evidence links, tests and missing proof; provide per-domain and total score with denominator and N/A handling.
3. `audit/FINDINGS.md`: prioritized findings **Critical / High / Medium / Low**, reproducible evidence, exact code references and actionable remedies. Do not bury security or compatibility blockers in a numeric score.
4. `audit/TEST_REPORT.md`: environment, exact commands, pass/fail/skip counts, logs, coverage where available, device/browser matrix, reproducibility instructions.
5. `audit/ARCHITECTURE_REVIEW.md`: dependency graph, API/ABI mismatches, data flow, trust boundaries, portability and maintainability.
6. `audit/SECURITY_REVIEW.md`: SSO/RBAC, cloud OAuth, guest access, sandboxing, privacy and threat-model findings.
7. `audit/REMEDIATION_PLAN.md`: sequenced fixes with owner role, estimated complexity (S/M/L), prerequisites, acceptance tests and suggested PR boundaries.
8. `audit/EVIDENCE_INDEX.md`: paths to test outputs, screenshots, fixtures, artifacts, commit hashes and upstream source citations.

The deliverables must give `AUD-01` through `AUD-04` their own scores and evidence,
not fold them into `WASM-02`. Recalculate the denominator after adding these four
rows. Include stereo PCM hashes or comparison reports, per-voice ADSR traces, an
eight-active-voice fixture, AudioStudio browser evidence, generated source and
packaged asset evidence, and the repository-wide buzzer-removal search result.

## Release gate

Recommend **NO-GO** for any exploitable critical auth/tenant isolation issue, unsafe arbitrary code execution on the server, fake cartridge compilation, materially incorrect ABI, missing core guest execution in a claimed WASM release, broken mandatory debugger functionality, fewer than eight functional SID-like ADSR voices, mono-only output, materially divergent stereo/ADSR behavior, missing AudioStudio core workflow, or any supported/reachable buzzer path. **CONDITIONAL** is appropriate only for clearly bounded, documented gaps with mitigations and no critical blockers. A high average score never overrides a critical finding.

## Final response format

Report: (1) inspected SHAs; (2) what was actually executed; (3) release recommendation; (4) top 10 findings with path:line and reproduction; (5) scored requirements coverage, including separate `AUD-01`–`AUD-04` scores; (6) exact missing evidence; (7) next implementation PRs; (8) an explicit audio verdict covering eight voices, ADSR, stereo parity, AudioStudio and buzzer removal. Clearly distinguish source inspection from executed validation. Do not claim PRG32 hardware, stereo hardware output, real-provider behavior or iOS validation unless performed.
