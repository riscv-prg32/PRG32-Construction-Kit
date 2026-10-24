# Independent audit of `7a700ba`

Audit date: 2026-10-24 (Europe/Rome)

Audited repository: **PRG32-Construction-Kit**, branch `ide/refine-after-e2d0cef`,
revision `7a700bab3f1b5cefb1bcf0e5cad392596396c12f`.

## Verdict

**NO-GO — 136/172 (79.1%).**

The new PRG32 Python implementation is substantial, constrained, deterministic and well
tested at source/IR level. The five-language layer is also broad, but deliberately incomplete.
Neither addition closes the existing release blockers. Deployment-specific GDPR decisions and
qualified review remain open, and the canonical Store/audio ecosystem changes, physical-device
evidence, iOS handoff, live cloud-provider runs and human screen-reader work are still absent.

This audit scores the requirements added to the governing brief through the
2026-10-24 scope expansion:

| ID | Score | State | Evidence-based observation |
|---|---:|---|---|
| I18N-01 | 2 | Partial | Five complete, placeholder-consistent catalogs cover kit templates, scripts, blocks, offline pages and privacy summaries; locale selection/fallback/offline caching and locale-independent generation have tests. Simplified Chinese is missing. Server/API/compiler diagnostics, Blockly and Monaco menus and most long-form documentation remain English. No six-locale role matrix, per-locale visual record or human screen-reader session exists. |
| PY-01 | 3 | Implemented/tested; reference demonstration pending | The versioned, fixed project mode parses without importing/executing student code, applies explicit AST/type/resource limits, lowers deterministically to the shared game IR, emits inspectable C and assembly, carries Python source mappings and provenance, and round-trips archives/packages. Local tests cover rejection, fresh-process determinism and C/assembly semantic parity. Real-toolchain cases skipped on this host, and there is no retained exact-HEAD browser/Qt/toolchain demonstration of mandatory scenario L. |
| DEP-04 | 0 | Missing | There is no unified top-menu Deploy tool for physical PRG32, QEMU and PRG32-QT. Existing delivery helpers and retained PRG32-QT evidence do not satisfy the cross-target UI, confirmation, integrity, cancellation, launch and recovery requirement. |
| EVAL-01 | 0 | Missing | There is no top-menu Evaluate tool, versioned three-target performance protocol, raw scientific dataset or downloadable publication-quality chart workflow. Existing browser performance budgets are CI quality gates, not cartridge evaluation APIs or a student-facing scientific analysis tool. |

The preceding audit's scores otherwise carry forward except `DOC-02`, reduced from 4 to 3.
The current architecture document contradicts the implementation and CI: it lists real builds
from only Blocks/C/assembly at `docs/architecture/current-state.md:104` and says the quality
gates lack lint, coverage and performance budgets at lines 152–153. The workflow contains lint,
coverage and browser performance jobs, and Python is now the fourth authoring mode. The
requirements matrix has now been expanded to 43 rows, including the missing Deploy and Evaluate
requirements requested after the initial audit run.

## Findings

### F-01 — Deployment GDPR gate is still open (release blocker)

`docs/privacy/decisions.md:6-22` explicitly leaves controller identity, legal bases,
Member-State rules, DPIA, DPO/counsel review, retention choices, processor/transfer decisions
and a staffed breach exercise open. This is appropriately documented and cannot be closed by
code or by this audit.

### F-02 — The capability/status record does not cover the current requirements (high)

The governing brief adds I18N-01, PY-01, DEP-04 and EVAL-01. The capability record now carries
the audited I18N-01 and PY-01 scores, and I18N-01 names missing Simplified Chinese coverage.
The canonical audit matrix contains all 43 rows, but the generated capability/status system must
still add DEP-04 and EVAL-01 with honest missing/planned status and keep the audited revision
explicit without claiming implementation.

### F-03 — Internationalization is not complete end to end (high)

`docs/capabilities.json:840` and `docs/architecture/current-state.md:143-146` accurately admit
that server-written messages, Python compiler refusals, compiler logs, Blockly/Monaco menus and
long-form documentation remain English. This falls short of mandatory scenario K, which demands
five locales across roles, validation/build/debug output, help, offline operation, accessibility
and visual/layout evidence.

### F-04 — Python lacks exact-revision end-to-end reference evidence (high)

ADR-0026 defines the correct safe architecture (`docs/adr/0026-prg32-python-projects.md:18-58`).
The focused local selection passed, but three toolchain-dependent cases skipped and no retained
artifact demonstrates the exact audited revision through real cartridge build, browser run/debug,
canonical PRG32-QT execution, packaging, six-locale hash equality and source-level debugging.
The implementation merits 3/4, not 4/4, until scenario L is recorded on CI/reference systems.

### F-05 — Documentation freshness regressed (medium)

`docs/architecture/current-state.md:98-105` describes Python and then claims real builds from
only the older three modes. Lines 152–153 claim no lint, coverage or performance budgets, while
`.github/workflows/tests.yml:325-357` implements lint and coverage and the browser job includes
performance tests. Automated documentation checks passed but do not detect these semantic
contradictions, so DOC-02 is 3/4.

### F-06 — Existing ecosystem and delivery gaps remain (release blockers for claimed parity)

The prior evidence remains applicable: the shared Kit/CartridgeStore identity patch and the
SDK/PRG32-QT audio/buzzer changes are not demonstrated as canonical merged revisions; no physical
PRG32 stereo transfer/launch evidence or supported iOS handoff exists; Drive and OneDrive lack
live-tenant runs; and no human screen-reader session has been recorded. Network access to the
GitHub API was unavailable during this audit, so upstream PR state was not independently refreshed.

## Verification performed

- `python3 -m pytest -q tests/test_python_project.py tests/test_py_generator.py tests/test_i18n.py tests/test_project_menu.py tests/test_project_format.py tests/test_project_starters.py tests/test_capabilities.py tests/test_doc_consistency.py tests/test_settings.py tests/test_api.py`
  — **555 passed, 3 skipped**.
- `python3 tools/build_i18n.py --check` — passed.
- `python3 tools/render_capabilities.py --check` — passed.
- `python3 tools/service_worker_lock.py --check` — passed.
- `python3 tools/check_docs.py` — passed its link, SVG, manifest, naming and capability-ID checks.
- `python3 -m ruff check .` — passed.
- `git diff --check` — passed.
- Broad `python3 -m pytest -q` — **1,544 passed, 109 skipped, 5 failed, 18 errors**.
  Eighteen loopback-server setup errors and one HTTPS test failure were caused by the restricted
  audit sandbox; the affected delivery/Store-egress selection passed **106/106** when rerun with
  loopback permission. Three failures reproduce the canonical unpatched CartridgeStore username
  mismatch. The remaining WASM rebuild failed in the local Homebrew Emscripten installation:
  its global cache was unwritable in the sandbox, while an isolated writable cache exposed broken
  relative system-library paths. This is an audit-host/tool installation limitation, not a
  demonstrated product regression, and the rebuild is not counted as a pass.

The working tree contained pre-existing untracked `.claude/` and refinement/audit notes. They
were not treated as product evidence and were not modified.

## Score

The prior 39-row score was 132/156. Add I18N-01 2/4 and PY-01 3/4, add missing
DEP-04 and EVAL-01 at 0/4, and reduce DOC-02 by one:

**132 + 2 + 3 + 0 + 0 - 1 = 136 points out of 172 (79.1%).**

