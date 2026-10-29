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
9. Treat current GDPR compliance as a hard release requirement, not a documentation
   aspiration. Verify the actual controller/processor roles, processing purposes,
   Article 6 legal bases, special-category and children's-data rules, transparency,
   consent where relied upon, data-subject rights, retention/erasure, portability,
   recipients/subprocessors, international transfers, records of processing,
   privacy by design/default, security, breach handling, DPIA/DPO decisions and
   accountability evidence against the current applicable EU and Member-State
   framework. A code audit alone must not claim legal certification: unresolved
   applicability or legal-basis questions require qualified privacy counsel/DPO
   sign-off and remain release blockers.
10. Treat documentation freshness as a hard release requirement. Audit and update
    the root `README.md`, every related guide/API/ADR/tutorial, screenshots,
    images, diagrams and architectural schemas so they describe the same current
    UI, routes, trust boundaries, data flows, build/audio behavior and deployment.
    Require reproducible provenance or a documented manual refresh procedure,
    alt text/captions, link/image validation and a test that detects stale version,
    route, label, screenshot and architecture references.

## Required audit matrix

Score each row 0–4: **0 missing; 1 prototype/stub; 2 partial; 3 implemented with meaningful tests; 4 implemented, tested and demonstrated against reference.** Mark N/A with justification; do not inflate a score because a feature is planned.

| ID | Requirement / proof to demand |
|---|---|
| IDE-01 | JetBrains-inspired shell: project tree, tabs, panels, command palette, responsive UI, keyboard and accessibility |
| IDE-02 | Blockly remains editable; canonical block project, stable generation and block-to-source mapping |
| IDE-03 | C editing: Monaco syntax, completion, diagnostics, navigation and SDK awareness |
| IDE-04 | RISC-V Assembly editing: syntax, instruction/register/ABI completion, diagnostics |
| I18N-01 | Complete, accessible internationalization for English, Italian, Spanish, French, German and Simplified Chinese (`zh-Hans`) across the IDE, guest/auth flows, validation/build/debug/evaluation messages, help and classroom documentation; locale selection and fallback work offline, Chinese typography and input work correctly, and locale never changes saved project semantics, measurements or deterministic artifacts |
| PY-01 | Python project mode with an explicit, versioned project schema; safe validation and deterministic translation/build to a real ABI-compatible **PRG32 cartridge**; inspectable generated C and RISC-V assembly; editor intelligence, run/debug, import/export and packaging parity; no arbitrary unvalidated Python executes on the server |
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
| DEP-04 | A unified **Deploy** tool in the top menu deploys the selected, validated **PRG32 cartridge** to a physical PRG32 device, QEMU or PRG32-QT; target discovery/configuration, explicit confirmation, integrity/version checks, progress, cancellation, launch, logs, retries and safe failure recovery are tested without confusing simulation with physical-device proof |
| EVAL-01 | A science-oriented **Evaluate** tool in the top menu runs a versioned performance-test protocol for the same **PRG32 cartridge** on a physical device, QEMU and PRG32-QT; records target/build/toolchain/protocol provenance, warm-up, repeated trials, timing sources, sample sizes, units and uncertainty; compares targets without misleading equivalence claims; and produces accessible publication-quality downloadable charts plus raw machine-readable data |
| SEC-01 | Threat model: untrusted builds, uploads, OAuth, SSRF, XSS, CSRF, IDOR, tenant isolation |
| SEC-02 | Secrets management, rate limiting, audit logs, retention/deprovisioning, dependency security |
| GDPR-01 | Current, demonstrable GDPR compliance for the complete processing lifecycle: roles, inventory/ROPA, purposes and legal bases, minimisation, transparency, children's safeguards, consent where used, data-subject rights, retention/erasure/export, processors/subprocessors, international transfers, privacy by design/default, security and breach response, DPIA/DPO decisions and accountable operational evidence; unresolved legal applicability requires qualified counsel/DPO review |
| OPS-01 | CI, container deployment, migrations, TLS, backup/restore, logging/metrics |
| DOC-01 | Architecture ADRs, developer/admin/user docs, examples, API contracts, traceability |
| DOC-02 | The root README and all related documentation, screenshots, images and architecture schemas are current, mutually consistent, accessible, linked correctly and verified against the running product and deployed architecture |
| QLT-01 | Test reliability, regression coverage, code quality, error handling, accessibility/performance |

## Required Python compilation architecture

Treat Python as an authoring language, not as a cartridge runtime. Do not embed
CPython or MicroPython and do not execute student Python during validation or
builds. The required ahead-of-time pipeline is:

```text
saved Python source
  -> parse only with a pinned grammar and resource limits
  -> allow-listed, statically checked PRG32 Python AST
  -> deterministic language-neutral game IR
  -> inspectable commented C and, on request, RISC-V assembly
  -> existing sandboxed PRG32 toolchain
  -> PRG32 cartridge
```

Define and version a small **PRG32 Python** language. Its first version should
support explicit `init`, `update` and `draw` lifecycle functions; fixed-width
integer and Boolean values; statically typed variables and functions; arithmetic,
comparisons and Boolean expressions; assignments; conditionals; bounded loops;
fixed-size collections where sizes and element types are known at compile time;
and a single `prg32` module exposing only validator-approved portable ABI calls
for graphics, input, sprites, assets and eight-voice stereo audio.

Document exact cartridge semantics rather than inheriting incompatible dynamic
Python behavior. In particular, specify signed and unsigned 32-bit ranges,
overflow, negative division and remainder, evaluation order, short-circuiting,
truth values, string limits and loop/resource bounds. Reject unsupported or
ambiguous behavior with a diagnostic tied to the original source range.

The parser must never import or execute the program. Apply limits to source
bytes, AST node count, nesting, symbols, functions, control-flow complexity,
generated IR and build output. Use an explicit AST allow-list and reject arbitrary
imports, `eval`, `exec`, reflection, dynamic attribute access, filesystem,
network, processes, threads, native extensions, dynamic allocation, unbounded
collections, coroutines, generators and other syntax outside the documented
subset. Server validation remains authoritative; browser language services may
provide earlier feedback but never weaken it.

Every IR node must retain stable Python source provenance. Extend debugger maps
as `Python source range -> IR node -> generated C/assembly lines -> cartridge
address`, without marker text changing generated files or cartridge bytes.
Generated C and assembly must include per-line teaching comments, use stable
symbol ordering and contain no timestamps, host paths, random identifiers or
locale-dependent text.

Use a versioned fixed project representation such as `source_mode: "python"`,
`source_python` and `python_language_version`. The Python source is authoritative;
generated C, assembly and maps are artifacts. Adding this mode requires an ADR
and schema migration because the current project contract permits only Blocks,
C and assembly. A project's type remains fixed and may change only through the
explicit conversion workflow. Record grammar, language, IR, ABI and toolchain
versions plus input/output hashes in build provenance.

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

I. **GDPR and privacy operations:** build a field-level personal-data inventory
covering accounts, external identities, academic roles/classes, projects/assets,
cloud tokens, API tokens, audit/security logs, IP/user-agent data, Store tickets,
backups and support/diagnostic artifacts. Map every item to purpose, controller/
processor role, legal basis, recipients, storage location, retention/deletion,
access controls and transfer safeguard. Exercise authenticated access,
rectification, restriction/objection where applicable, portable export and
erasure across primary storage, artifacts, cloud copies, Store integration,
logs and backups; prove identity verification, deadlines, exceptions and audit
records. Verify privacy notices at collection, age-appropriate language and
Member-State rules for students/minors, consent withdrawal when consent is the
basis, processor contracts/subprocessors, transfer mechanisms, breach detection/
72-hour workflow, DPIA and DPO determinations. Use synthetic users only. Obtain
qualified counsel/DPO approval for legal judgments that tests cannot establish.

J. **Documentation and visual truth:** compare the running product and current
architecture with the root `README.md`, docs index, setup/deployment/admin/user
guides, ADRs, API contracts, tutorials, screenshots, images and diagrams. Refresh
every stale visual at a named viewport/theme/locale with synthetic data; ensure
no secrets or personal data appear. Verify alt text/captions, readable diagrams,
source/provenance, internal/external links, route/label/version references and
that architecture schemas include current auth, privacy, cloud, Store, build,
WASM, AudioStudio and retention flows. Run automated link/image/reference checks
and retain a visual review checklist.

K. **Multi-language:** exercise English, Italian, Spanish, French, German and
Simplified Chinese (`zh-Hans`) as
guest, student, teacher and administrator. Change locale before and during an
editing session; reload and work offline; cover the IDE, Blockly, Sprite Lab,
AudioStudio, debugger, Deploy, Evaluate, sign-in, settings, validation/build
errors, publishing, privacy notices and classroom help. Verify keyboard and
screen-reader behavior, pluralization, interpolation, long-text layouts, CJK
font fallback/line breaking/input, fallback for missing keys and that no
untranslated user-facing strings remain. Build and evaluate the same saved
project in every locale and prove byte-identical generated source and cartridge
output and locale-neutral raw measurement data.

L. **Python projects:** create, save, reload, import/export, run, debug and package
a Python project containing arithmetic, control flow, functions, graphics,
input and eight-voice stereo audio. Verify editor completion/diagnostics and map
runtime, validator and build errors back to Python source. Inspect the generated
C and RISC-V assembly with explanatory source mappings, and prove repeat builds
are deterministic and ABI-compatible. Reject unsupported syntax, imports,
dynamic code execution, filesystem/network/process access, native extensions,
unbounded resource use and attempts to escape the validator or build sandbox.
Confirm a project's type is fixed and can change only through the documented,
explicit conversion workflow.

For determinism, build identical Python fixtures repeatedly, in clean processes
and under all six UI locales. Compare normalized AST/IR, generated C, generated
assembly, debug-map and PRG32 cartridge hashes. For semantic parity, compare
Python and equivalent Blocks fixtures through the same IR and compare C and
assembly execution traces using the existing RV32 harness. Verify that errors
report stable codes and accurate Python ranges without leaking source or secrets
into logs.

M. **Unified deployment:** from the top-menu **Deploy** command, deploy one
validated cartridge in turn to a disposable physical PRG32 device, QEMU and
canonical PRG32-QT. Verify target discovery/configuration, explicit target and
cartridge identity, SHA-256 before/after transfer where supported, ABI/version
refusal, slot selection, progress, cancellation, timeout, retry, disconnect,
full target, failed launch and recovery. Capture target-native evidence that the
expected cartridge launched. A QEMU or PRG32-QT run must never be reported as a
physical-device result, and tests must never overwrite an unnamed device slot.

N. **Scientific performance evaluation:** from the top-menu **Evaluate** command,
run the same versioned performance cartridge and protocol on a physical PRG32
device, QEMU and canonical PRG32-QT. Record cartridge hash, target identity and
configuration, SDK/ABI/tool versions, host details for simulated targets, clock
source, units, warm-up, repetitions, individual samples, exclusions and failure
states. Report descriptive statistics and uncertainty appropriate to the sample;
do not imply hardware equivalence from emulator timings. Download raw CSV and
JSON plus publication-quality SVG and PDF/PNG charts with titles, labelled axes,
units, legends, captions, accessible descriptions, colour-blind-safe styling and
reproducible chart metadata. Verify deterministic chart construction from a fixed
dataset, locale-safe numeric export, keyboard/screen-reader use, bounded data,
offline operation and clear handling of missing or incomparable measurements.

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
- Compare privacy behavior and documentation across Construction Kit,
  CartridgeStore, configured identity/cloud providers and deployment examples.
  Identify the controller, processor or joint-controller role for each flow and
  reject contradictory retention, rights, subprocessors or transfer claims.
- Trace personal data end to end, including browser/IndexedDB, SQLite, build
  folders, artifacts, logs, backups, OAuth/token stores, Store tickets and cloud
  copies. Verify deletion/export boundaries and documented exceptions.
- Verify every README/docs visual and architecture schema against the same
  audited revision. Treat a polished but stale screenshot or diagram as failed
  evidence, not cosmetic debt.
- Compare locale catalogs for English, Italian, Spanish, French, German and
  Simplified Chinese (`zh-Hans`);
  require identical key sets, safe interpolation, documented fallback behavior,
  accessibility review and tests that catch untranslated or stale UI strings.
- Trace Python end to end: versioned source project -> restricted parser and
  validator -> deterministic game IR -> inspectable generated C and optional
  RISC-V assembly -> real toolchain -> PRG32 cartridge -> browser/Qt execution.
  Prove that locale choice cannot affect this pipeline or its artifact hashes.
- Verify that Python, Blocks, generated C and generated assembly share one
  documented IR contract rather than separate behavioral implementations. Check
  fixed-width arithmetic edge cases, negative division/remainder, evaluation
  order, short-circuiting, loop bounds, asset references and every portable ABI
  call against the C/assembly generators and PRG32/PRG32-QT references.
- Review the Python compiler threat model separately. Parsing must not cause
  imports or execution; diagnostic rendering must escape student text; compiler
  limits must resist deeply nested ASTs and size/complexity denial of service;
  and no code path may pass student-produced Python or C directly to a host
  interpreter/compiler outside the existing isolated build pipeline.

## Deliverables (write files in `audit/`)

1. `audit/EXECUTIVE_SUMMARY.md`: release recommendation **GO / CONDITIONAL / NO-GO**, critical blockers, verified coverage, limitations and concise risk summary.
2. `audit/REQUIREMENTS_MATRIX.md`: every matrix ID, score 0–4, status, evidence links, tests and missing proof; provide per-domain and total score with denominator and N/A handling.
3. `audit/FINDINGS.md`: prioritized findings **Critical / High / Medium / Low**, reproducible evidence, exact code references and actionable remedies. Do not bury security or compatibility blockers in a numeric score.
4. `audit/TEST_REPORT.md`: environment, exact commands, pass/fail/skip counts, logs, coverage where available, device/browser matrix, reproducibility instructions.
5. `audit/ARCHITECTURE_REVIEW.md`: dependency graph, API/ABI mismatches, data flow, trust boundaries, portability and maintainability.
6. `audit/SECURITY_REVIEW.md`: SSO/RBAC, cloud OAuth, guest access, sandboxing, privacy and threat-model findings.
7. `audit/REMEDIATION_PLAN.md`: sequenced fixes with owner role, estimated complexity (S/M/L), prerequisites, acceptance tests and suggested PR boundaries.
8. `audit/EVIDENCE_INDEX.md`: paths to test outputs, screenshots, fixtures, artifacts, commit hashes and upstream source citations.

The security review must contain a dedicated GDPR section with a processing
inventory/ROPA summary, legal-basis and role matrix, rights/retention/transfer/
processor evidence, DPIA and DPO decisions, breach workflow, counsel/DPO review
status and explicit unresolved legal questions. The evidence index must include
privacy notices, policies, processor/subprocessor records, rights-request test
artifacts and the documentation/visual freshness manifest.

The deliverables must give `AUD-01` through `AUD-04`, `I18N-01`, `PY-01`, `DEP-04` and `EVAL-01` their own scores and evidence,
not fold them into `WASM-02`. Recalculate the denominator after adding these four
audio rows and the mandatory `GDPR-01`, `DOC-02`, `I18N-01`, `PY-01`, `DEP-04`
and `EVAL-01` rows. Include stereo PCM
hashes or comparison reports, per-voice ADSR traces, an
eight-active-voice fixture, AudioStudio browser evidence, generated source and
packaged asset evidence, the repository-wide buzzer-removal search result,
six-locale catalog/visual/accessibility evidence, locale-independent artifact
hashes and Python grammar/semantics, parser and validator limits, typed IR,
source-map, provenance, malicious-input and real-toolchain evidence. Include a
three-target deployment record and a three-target evaluation bundle containing
raw samples, protocol/provenance, statistics, uncertainty and downloadable
publication-quality chart artifacts.

## Release gate

Recommend **NO-GO** for any exploitable critical auth/tenant isolation issue,
unsafe arbitrary code execution on the server, fake cartridge compilation,
materially incorrect ABI, missing core guest execution in a claimed WASM
release, broken mandatory debugger functionality, fewer than eight functional
SID-like ADSR voices, mono-only output, materially divergent stereo/ADSR
behavior, missing AudioStudio core workflow, any supported/reachable buzzer
path, a material GDPR compliance failure, an unmitigated high-risk privacy
processing operation, missing required DPIA/DPO/counsel determination, or
documentation/visuals that materially misrepresent security, privacy,
installation, APIs, architecture or supported behavior. Also recommend
**NO-GO** for a claimed multi-language release with incomplete English, Italian,
Spanish, French, German or Simplified Chinese coverage or locale-dependent build
output, for a Deploy tool that can silently target or overwrite the wrong device,
for an Evaluate tool that loses raw data/provenance or presents incomparable
emulator and hardware timings as equivalent, and for a
claimed Python project mode that executes unvalidated code, bypasses the game IR,
hides generated teaching source, produces non-deterministic artifacts or lacks
real PRG32 cartridge evidence. **CONDITIONAL** is
appropriate only for clearly bounded, documented gaps with mitigations and no
critical blockers. A high average score never overrides a critical finding or
legal release gate.

## Final response format

Report: (1) inspected SHAs; (2) what was actually executed; (3) release
recommendation; (4) top 10 findings with path:line and reproduction; (5) scored
requirements coverage, including separate `AUD-01`–`AUD-04`, `GDPR-01` and
`DOC-02`, `I18N-01`, `PY-01`, `DEP-04` and `EVAL-01` scores; (6) exact missing evidence; (7) next implementation PRs;
(8) an explicit audio verdict covering eight voices, ADSR, stereo parity,
AudioStudio and buzzer removal; (9) an explicit GDPR verdict that distinguishes
technical evidence from legal counsel/DPO determinations; and (10) a
documentation/visual freshness verdict covering the main README, screenshots,
images and architecture schemas; (11) a multi-language verdict for English,
Italian, Spanish, French, German and Simplified Chinese; (12) a Python-project verdict covering
validation, deterministic generation, inspectable C/assembly, debugging,
packaging and sandbox boundaries; (13) a Deploy verdict for physical PRG32,
QEMU and PRG32-QT; and (14) an Evaluate verdict covering scientific protocol,
provenance, raw data, uncertainty and downloadable publication-quality charts.
Clearly distinguish source inspection from
executed validation. Do not claim PRG32 hardware, stereo hardware output,
real-provider behavior, iOS validation or legal certification unless actually
performed and appropriately approved.
