# Findings

## Closed or materially improved

- All authoring modes now have retained real-toolchain builds for both targets, with cross-host deterministic hashes.
- C and assembly editing now receives the real compiler's line diagnostics after safe server validation.
- Canonical PRG32-QT delivery is recorded for Blocks-C, Blocks-assembly, Advanced C, handwritten assembly and AudioStudio audio-check cartridges.
- Disposable HTTP Kit/CartridgeStore processes now demonstrate shared accounts, one-time sign-on and publisher upload authorization.
- Tested SDK/Qt/QEMU patches make the intended audio migration concrete and reproducible.
- Documentation no longer uses ambiguous “this change” milestone rows.

## High

### H-00 — Deployment GDPR decisions and qualified review remain open

Technical implementation is now strong, but every deployment decision D-0 through
D-10 remains open at `docs/privacy/decisions.md:12-22`. The DPIA is explicitly
not done (`docs/privacy/children_dpia_dpo.md:40-43`), no DPO/counsel has reviewed
the material (`:59-61`), processor rows remain templates, and the only breach
exercise was an unstaffed technical rehearsal (`docs/privacy/exercises/README.md:3-8`).
Expected: named controller, applicable legal bases and Member-State rules,
completed DPIA/DPO decisions, contracts/transfers, staffed exercise and qualified
review for the actual deployment. Actual: maintainers' technically tested
template, correctly marked NO-GO. Complete and approve these records before use.

### H-00B — Closed: documentation and visual freshness are now evidenced

README, architecture, diagrams, screenshots and documentation gates now pass.
`tools/check_docs.py`, `tools/build_diagrams.py --check`, `tools/render_ropa.py
--check`, `docs/figures/manifest.json` and human review commits provide the
required reproducibility and freshness evidence.

### H-00C — Kit/CartridgeStore shared username contract regressed

Run `python3 -m pytest -q
tests/test_sso_with_cartridge_store.py::test_kit_user_can_sign_in_to_the_store`.
The Store accepts `ada@school.test` and the correct password, but `/api/me`
returns a generated `player-*` username instead of `ada`
(`tests/test_sso_with_cartridge_store.py:75`). Expected: the documented shared
account identity. Actual: authenticated account with a divergent username.
Decide whether pseudonymous Store usernames are now canonical; if so, migrate
the contract/docs/test explicitly. Otherwise preserve the Kit username through
the synchronization path.

### H-01 — Required audio changes are not canonical upstream

The buzzer-retirement, firmware-audio Qt integration and QEMU clock/reset fixes exist only as patches under `docs/upstream/`. The pinned SDK still publicly exports buzzer and released PRG32-QT still defaults to its divergent mixer. Submit, review and merge equivalent upstream changes before declaring ecosystem compatibility.

## Medium

### M-01 — Physical PRG32 remains unverified

No stereo console capture or physical transfer/launch record exists. The prepared comparator cannot substitute for a real I2S or acoustic recording.

### M-02 — QEMU frame-triggered effects retain one-buffer ambiguity

The patch aligns tracker-driven audio and most whole recordings, but effects invoked from cartridge frames can land 20 ms early or late because frame and audio schedules are independent.

### M-03 — Desktop import UX is not exercised

PRG32-QT web-API delivery is meaningful and produces screenshots, but the user-facing desktop Import workflow was not clicked and observed.

### M-04 — External delivery and tenant evidence remains incomplete

No iOS handoff, physical console, institutional identity tenant, Google Drive account or Microsoft account was exercised.

## Low

### L-01 — Human screen-reader evidence remains open

Automated accessibility and keyboard scenarios pass, but AudioStudio tasks 10–14 have not been completed with an identified assistive technology.

## Release conclusion

The expanded assessment scores **131/156**. The release remains **NO-GO** because
the actual-deployment GDPR decisions and qualified review are open. Documentation
freshness is closed; shared-account identity and audio/hardware blockers remain.
