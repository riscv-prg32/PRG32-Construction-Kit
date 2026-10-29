# Claude refinement brief after audit `7a700ba`

Refine **PRG32-Construction-Kit** from audited revision
`7a700bab3f1b5cefb1bcf0e5cad392596396c12f`. Read `AGENTS.md`,
`audit/AUDIT_7A700BA.md`, ADR-0026, ADR-0027 and the applicable earlier ADRs before editing.
Preserve deterministic generation, inspectable teaching C/assembly, strict CSP, fixed project
types, guest non-persistence, ownership/version checks and build isolation. Do not execute or
compile arbitrary unvalidated student Python. Do not change auditor-owned scores merely because
work is planned.

## Current verdict

**NO-GO — 136/172 (79.1%).**

PRG32 Python scores 3/4 and internationalization 2/4. Documentation freshness regressed to
3/4 because the architecture/status text contradicts the fourth authoring mode and existing CI
quality gates. The new unified Deploy and scientific Evaluate requirements are both missing
(0/4). Simplified Chinese is now part of I18N-01 and is missing. The operational GDPR gate and
earlier ecosystem/delivery gaps remain open.

Fresh audit execution: the focused new-feature/consistency selection passed 555 tests with
3 skips. The broad suite produced 1,544 passed, 109 skipped, 5 failed and 18 sandbox errors;
the 18 loopback errors plus the related HTTPS failure passed as 106/106 with loopback permission.
Three failures are the known mismatch with canonical unpatched CartridgeStore. The remaining
WASM rebuild could not be judged because the local Homebrew Emscripten cache/path installation
failed; rerun it in the pinned CI environment rather than treating it as a product failure or pass.

## Priority 0 — restore truthful audit and documentation records

1. Keep I18N-01, PY-01, DEP-04 and EVAL-01 in the canonical audit matrix and totals. Add DEP-04
   and EVAL-01 to the capability/status system with honest missing/planned state, and extend
   I18N-01 to Simplified Chinese. Name the audited revision and separate fresh execution from
   retained evidence. Keep `docs/capabilities.json` as the source for the rendered capability
   page, but only the auditor assigns `audit_score`.
2. Correct `docs/architecture/current-state.md`:
   - real builds now cover Blocks, C, assembly **and Python**;
   - CI does have Ruff lint, an 88% coverage floor and browser performance budgets;
   - remove the stale statement that DOC-02 material is merely “being refreshed.”
3. Extend documentation checks so these claims are derived or asserted, rather than allowing
   another semantically stale status page to pass link/ID checks.

Acceptance: every requirement ID appears exactly once in the current matrix and architecture
status; generated capability docs are unchanged when rendered; no status page contradicts CI or
the supported source modes.

## Priority 0 — produce exact-revision Python reference evidence

Run mandatory scenario L on Linux CI with the real PRG32 toolchain and the canonical pinned
PRG32-QT revision. Preserve machine-readable evidence and hashes for:

- create/save/reload/archive/import/package of a Python project;
- arithmetic, control flow, helpers, graphics, input and eight-voice stereo audio;
- validator, build and runtime diagnostics mapped to exact Python ranges;
- inspectable commented C, RV32IM assembly, source map and provenance;
- browser run/debug plus canonical PRG32-QT execution of the same cartridge;
- repeated clean-process builds and all six UI locales producing identical normalized IR,
  generated C, generated assembly, debug map and PRG32 cartridge hashes;
- malicious/unsupported imports, dynamic execution, filesystem/network/process/native access,
  recursion and resource-exhaustion attempts being rejected without executing student code.

Do not award 4/4 from unit tests alone. Link the retained evidence from capabilities and audit
records only after the exact audited commit passes.

## Priority 1 — complete I18N-01

Move user-facing server/API validation, PRG32 Python diagnostics and safe compiler/build messages
to stable message codes with localized presentation. Load supported Blockly and Monaco UI locale
packs from `static/vendor/`; preserve strict CSP and offline operation. Translate the classroom
documentation required by the audit, not only the quick start.

Add complete Simplified Chinese (`zh-Hans`) catalogs, CJK-capable local fonts,
line-breaking/input tests and translated classroom material. Exercise English,
Italian, Spanish, French, German and Simplified Chinese as guest, student, teacher and admin. Cover
locale changes before/during editing, reload/offline behavior, long strings, interpolation,
plurals, missing-key fallback, privacy/auth flows, IDE, Blockly, Sprite Lab, AudioStudio,
debugger and publishing. Record synthetic per-locale screenshots and a human keyboard/screen-reader
session. Prove again that locale never changes saved semantics or artifact bytes.

## Priority 1 — add the unified Deploy tool

Add **Deploy** to the project-aware top menu. It must deploy the selected validated
**PRG32 cartridge** to an explicitly selected physical PRG32 device, QEMU or canonical
PRG32-QT. Keep target adapters behind one explainable interface while preserving target-specific
truth: an emulator run is never physical-device evidence. Provide discovery/configuration,
cartridge and target identity, ABI/version and integrity checks, explicit confirmation, slot
selection, progress, cancellation, logs, launch, timeout/retry and safe recovery. Never overwrite
an unnamed device slot. Add negative tests for disconnects, stale builds, hash mismatch, full
targets, unsupported ABI and launch failure, plus real evidence for all three targets.

## Priority 1 — add the scientific Evaluate tool

Add **Evaluate** to the project-aware top menu and define a versioned PRG32 performance-evaluation
contract/API. Run the same hashed performance cartridge and protocol on a physical device, QEMU
and canonical PRG32-QT. Capture raw repeated measurements with warm-up, units, timing source,
sample size, target/build/toolchain/protocol provenance, host configuration for simulated targets,
exclusions and failures. Report suitable descriptive statistics and uncertainty, and prominently
explain that emulator timings are not physical-hardware equivalents.

Make raw CSV and JSON downloadable. Generate deterministic, accessible, publication-quality SVG
and PDF/PNG charts with labelled axes and units, titles, legends, captions, colour-blind-safe
styles, accessible descriptions and embedded/referenced provenance. Support reproducible chart
regeneration from the raw dataset, offline use, keyboard/screen-reader operation, bounded inputs,
locale-safe numeric export and clear handling of missing or incomparable measurements. The chart
layer must consume evaluation API data; it must not fabricate, smooth away or silently discard
samples.

## Priority 1 — close external gates without weakening local safeguards

- Obtain the controller's D-0 through D-10 decisions, DPIA and qualified DPO/counsel review;
  execute and record the staffed breach exercise. These are external decisions, not defaults for
  maintainers to invent.
- Merge/pin the CartridgeStore shared-identity contract and rerun the unpatched adjacent-store
  suite against the canonical revision.
- Merge/pin the SDK buzzer retirement/audio-clock changes and PRG32-QT firmware-engine changes;
  regenerate contracts, indexes and fixtures and rerun clean upstream conformance.
- Capture physical PRG32 stereo transfer/launch evidence, including integrity, eight voices,
  pan, ADSR, silence/reset and no buzzer output.
- Verify only an actual documented PRG32-iOS interface; otherwise keep DEP-03 at 0.
- Run Drive and OneDrive live suites with throwaway test accounts and only environment-provided
  credentials, deleting only data created by the suite.
- Address or formally isolate the remaining shared-host-UID build risk.

## Required verification before handoff

```text
python3 -m ruff check .
python3 tools/build_i18n.py --check
python3 tools/build_language_index.py --check
python3 tools/render_capabilities.py --check
python3 tools/service_worker_lock.py --check
python3 tools/check_docs.py
python3 tools/build_diagrams.py --check
python3 tools/render_ropa.py --check
python3 -m pytest -q
PRG32_REQUIRE_BROWSER=1 python3 -m pytest -q -rs tests/test_*browser*.py
```

Also run the production-image/toolchain jobs, the Store contract suite, canonical PRG32-QT
delivery, unified three-target deployment/evaluation, and the new six-locale Python scenario in CI. Report exact commands, revisions,
pass/fail/skip totals, artifact hashes and links. Never convert a skip or retained result into a
fresh pass.

## Handoff back to the auditor

Return a short evidence index mapping each changed requirement to source, negative tests,
reference run and retained artifact. List unresolved external dependencies separately. Do not
claim release readiness until GDPR operational decisions and every claimed reference integration
have objective evidence.
