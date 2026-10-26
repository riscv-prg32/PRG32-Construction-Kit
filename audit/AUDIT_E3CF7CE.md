# Independent audit of `e3cf7ce`

Audit date: 2026-10-26 (Europe/Rome)

Audited repository: **PRG32-Construction-Kit**, branch `ide/refine-after-e2d0cef`,
revision `e3cf7cecf8361bc188e2e7ef227b1778731d55cc`.

## Verdict

**NO-GO — 140/172 (81.4%).**

The refinement implements the expanded matrix's three requested areas credibly:

- Simplified Chinese joins the five existing interface languages, including server messages,
  editor packs, CJK font/input/layout behavior, lessons, offline use and deterministic builds.
- Deploy is a single project-menu workflow for a physical PRG32 adapter, QEMU and PRG32-QT,
  with explicit target/slot confirmation, ABI/hash/staleness checks, cancellation and recovery.
- Evaluate defines a versioned performance protocol, retains every broker result per run, computes
  reproducible statistics and exports deterministic CSV, JSON, SVG and PDF artifacts.

Deploy and Evaluate each score **3/4**: retained evidence verifies QEMU and canonical PRG32-QT,
but there is no physical PRG32 deployment or evaluation record. I18N-01 remains **2/4** because
the current revision has fresh untranslated Color Picker keys and multilingual layout failures.

The release remains NO-GO independently of the numerical score: deployment-specific GDPR
decisions and qualified review remain open, the documentation visual-freshness hard gate fails,
the mandatory broad/browser quality gates fail, the adjacent canonical CartridgeStore identity
contract still disagrees, and the SDK audio-retirement patches no longer apply to the current
adjacent SDK checkout.

## Fresh scoring changes

| ID | Previous | Current | Observation |
|---|---:|---:|---|
| I18N-01 | 2 | 2 | Chinese and six-language infrastructure are implemented, but Color Picker keys are absent from the catalogs and Italian makes the menu two rows at 1400, 1440 and 1600 px. Twelve locale/IDE screenshots are stale; no human screen-reader session exists. |
| DEP-04 | 0 | 3 | Unified implementation, negative tests and retained QEMU/PRG32-QT evidence pass. Physical PRG32 evidence is absent. |
| EVAL-01 | 0 | 3 | Versioned protocol, raw exports, reproducible charts and QEMU/PRG32-QT evidence pass. Physical timings and human chart accessibility evidence are absent; measurements are per-run broker summaries, not per-frame samples. |
| DOC-02 | 3 | 2 | `tools/check_docs.py` reports 12 stale screenshots, so the explicit documentation freshness gate fails. |
| QLT-01 | 3 | 2 | The broad suite has ten failures and four errors, including local product/CI regressions as well as external integration failures. |

Net change: **136 + 3 + 3 - 1 - 1 = 140/172 (81.4%)**.

## Findings

### F-01 — GDPR deployment decisions remain open (release blocker)

`docs/privacy/decisions.md` still leaves controller identity, legal bases, Member-State rules,
DPIA, DPO/counsel review, retention, processor/transfer decisions and the staffed breach exercise
open. The repository correctly treats this as NO-GO; an implementation agent must not invent
these decisions.

### F-02 — New Color Picker strings bypass the six-language catalogs (high)

Fresh failures:

- `tests/test_i18n.py::test_every_key_a_template_uses_exists`
- `tests/test_i18n.py::test_every_script_message_exists_with_the_same_english`

`templates/color_picker.html` uses 23 `tools.*` keys absent from the English source catalog, and
`static/js/color_picker.js` uses `js.tools.*` keys with no matching English catalog entries.
Because English is the source catalog, all six generated catalogs and their placeholder checks
are stale until these keys are added and translated.

### F-03 — The localized top menu wraps at supported desktop widths (high)

`tests/test_i18n_browser.py::test_the_menu_bar_is_one_row_in_every_language` fails for Italian at
1400, 1440 and 1600 px: the navbar is 93 px high instead of remaining a single row. Deploy,
Evaluate and other new top-menu commands increased pressure on the responsive breakpoint.

### F-04 — A browser suite is omitted from CI (high)

`tests/test_frontend_offline.py::test_ci_runs_every_browser_suite_and_forbids_skipping` reports
that `tests/test_color_picker_browser.py` is not named by the browser job in
`.github/workflows/tests.yml`. CI therefore does not satisfy the rule that every browser suite
runs with `PRG32_REQUIRE_BROWSER=1`.

### F-05 — Documentation visual freshness gate fails (high)

`python3 tools/check_docs.py` reports 12 stale files: the main IDE image, five game-editor images
and all six locale IDE screenshots. Their manifest commits predate subsequent template, IDE,
CSS or catalog changes. Refresh them with synthetic data or explicitly review/acknowledge the
changes using the manifest workflow; do not merely silence the check.

### F-06 — Deploy and Evaluate lack physical-device proof (high)

Retained records under `docs/evidence/deploy/` and `docs/evidence/evaluate/` prove QEMU and
canonical PRG32-QT runs and clearly label both as emulator evidence. No physical PRG32 was
available. Consequently DEP-01 remains 0/4, while DEP-04 and EVAL-01 cannot exceed 3/4.

### F-07 — Evaluate's scientific evidence has bounded but material gaps (medium)

The protocol records per-case summaries returned by performance broker ABI 1, not individual
frame measurements. Statistics are therefore over repeated run summaries. This is documented
and not falsified as frame-level raw data, but physical-device timing, human review of chart
accessibility and a recorded real-browser workflow remain necessary for reference verification.

### F-08 — Upstream audio patches no longer apply to the adjacent SDK (high)

Four `tests/test_upstream_sdk_patches.py` cases error because
`docs/upstream/prg32-sdk-retire-buzzer.patch` no longer applies to the current adjacent PRG32
checkout (`prg32.h`, `prg32_audio.c` and audio documentation changed). Rebase or retire the patch
against the pinned canonical SDK state and rerun its generated ABI, slot-retirement, public-header
and example checks. AUD-04 remains 2/4.

### F-09 — CartridgeStore shared identity still fails (high)

The same three `tests/test_sso_with_cartridge_store.py` assertions fail: canonical Store returns
generated `player-*` handles instead of the shared private username contract. SSO-04 remains 3/4
until the compatible Store change is canonical and the default adjacent-repository suite passes.

### F-10 — Human accessibility and external delivery gaps remain (medium)

No human screen-reader session covers Chinese, Deploy, Evaluate or the charts. Drive and OneDrive
still lack live-tenant evidence; physical PRG32 stereo/delivery and PRG32-iOS handoff remain
unverified; canonical upstream audio integration remains unresolved.

## Verification

- Focused Deploy/Evaluate rerun with disposable loopback targets: **47 passed**.
- Broad `python3 -m pytest -q`: **2,335 passed, 60 skipped, 10 failed, 4 errors** in 360.38 s.
- Mandatory browser tests executed in that broad run and exposed the menu failures.
- `build_i18n`, rendered capabilities and service-worker lock checks passed before the broad run.
- `ruff` and later generated-document checks were not reached by the chained command because
  `tools/check_docs.py` stopped at the 12 stale visuals.
- GitHub returned no workflow run for the exact local audited SHA; exact-revision CI is therefore
  not claimed.

The working tree already contained unrelated untracked refinement files. They were preserved.

