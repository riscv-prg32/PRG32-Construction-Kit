# Claude refinement brief after audit `e3cf7ce`

Refine **PRG32-Construction-Kit** from audited revision
`e3cf7cecf8361bc188e2e7ef227b1778731d55cc`. Read `AGENTS.md`,
`audit/AUDIT_E3CF7CE.md`, ADR-0026 through ADR-0028, the evaluation protocol and the relevant
privacy decisions before changing code. Preserve deterministic generation, inspectable teaching
C/assembly, strict CSP, fixed project types, guest non-persistence, explicit target/slot
confirmation and truthful emulator-versus-physical evidence.

## Current verdict

**NO-GO — 140/172 (81.4%).**

Deploy and Evaluate are now meaningful 3/4 implementations with retained QEMU and canonical
PRG32-QT evidence. They remain short of reference verification because there is no physical PRG32
record. Six-language work is broad, but current Color Picker and responsive-menu regressions keep
I18N-01 at 2/4. The broad suite is not green, visual freshness fails, GDPR operational decisions
remain open and canonical Store/audio integration is unresolved.

## P0 — restore mandatory quality gates

1. Add every Color Picker template and script key to `static/i18n/en.json`, translate it in
   Italian, Spanish, French, German and Simplified Chinese, regenerate catalogs with
   `tools/build_i18n.py`, and keep placeholders identical. Do not whitelist English copies as
   translations unless the term is genuinely language-independent and documented.
2. Fix the top navigation breakpoint/layout so every supported language stays one row at the
   tested desktop widths and uses the collapsed menu below the chosen breakpoint. Re-run all
   eight widths, all six locales and the longest admin menu.
3. Add `tests/test_color_picker_browser.py` to the CI browser job. Preserve
   `PRG32_REQUIRE_BROWSER=1`, so missing Chromium is a failure rather than a skip.
4. Refresh the 12 stale IDE/game/locale screenshots from synthetic data with
   `tools/capture_visuals.py`, or use the documented manifest acknowledgement only after a human
   confirms the image is still truthful. Record capture and review commits.

Acceptance: the complete broad suite, every browser suite, `tools/check_docs.py`, catalog checks,
service-worker lock, Ruff and the coverage gate all pass at one exact commit.

## P0 — repair canonical ecosystem checks

1. Rebase `docs/upstream/prg32-sdk-retire-buzzer.patch` and related audio work against the exact
   canonical SDK revision the kit claims. Prefer merged upstream changes and updated pins over
   carrying a perpetually rebased patch. Regenerate ABI/index/fixtures and pass all four
   `test_upstream_sdk_patches.py` checks from a clean clone.
2. Land and pin the CartridgeStore shared-identity contract so the default adjacent canonical
   Store returns the private shared username separately from its pseudonymous public handle.
   Re-run all cross-repository collision and recovery cases without patching the Store in place.

## P1 — close DEP-04 with physical PRG32 evidence

Use a disposable, explicitly named console slot and the same Deploy API/UI path. Record target
identity, firmware/ABI, cartridge SHA-256, slot before/after, progress log, launch proof and
screenshot. Exercise cancellation, disconnect, changed slot, stale build, hash mismatch,
unsupported ABI, capacity and failed launch without overwriting an unnamed slot. Preserve the
record under `docs/evidence/deploy/` and make its checker fail if evidence is mislabeled.

Do not convert QEMU or PRG32-QT evidence into physical-device evidence.

## P1 — close EVAL-01 scientifically

Run the versioned protocol through Evaluate on a physical PRG32 using the exact cartridge hash
already compared on QEMU and PRG32-QT, or clearly version the protocol if the workload changes.
Record clock source, firmware/SDK/ABI, host details where applicable, warm-up, repetitions,
individual broker results, failures/exclusions, units, statistics and uncertainty. Preserve CSV,
JSON, deterministic SVG/PDF charts and the three-target comparison.

Add/retain a dedicated real-browser workflow for Deploy and Evaluate covering keyboard use,
downloads, cancellation, errors, chart descriptions and axe-core. Conduct and record a human
screen-reader session. Keep the scientific caveat prominent: emulator timings are host-dependent
and are not console performance. If frame-level distributions are required, version the broker
and protocol; never relabel per-run summaries as frame samples.

## P1 — finish I18N and documentation truth

After fixing the immediate failures, audit every new Deploy/Evaluate/Color Picker message in all
six locales. Keep Chinese font fallback, line breaking and committed input behavior offline.
Translate additional student-facing reference material where the matrix requires it, while
leaving technical ADRs in English when explicitly scoped. Run a human keyboard/screen-reader
session across Chinese, Deploy, Evaluate and chart downloads.

## External release gates

- The deploying controller must decide D-0 through D-10, complete the DPIA and obtain qualified
  DPO/counsel review; run a staffed breach exercise. Claude must not invent legal decisions.
- Capture physical stereo/audio and delivery evidence on the actual PRG32.
- Run Drive and OneDrive live suites with throwaway accounts and environment-only secrets.
- Verify only a real documented PRG32-iOS interface; otherwise keep DEP-03 at 0.
- Address or formally isolate the remaining shared-host-UID build risk.

## Required verification and handoff

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

Also run the pinned production-image/toolchain, Python-reference, Store-contract, Deploy and
Evaluate evidence jobs. Return exact revisions, commands, pass/fail/skip totals, target identities,
artifact hashes and evidence paths. Keep auditor-owned scores unchanged during implementation;
return evidence for an independent rescore.
