# Findings

## Closed or materially improved

- All authoring modes now have retained real-toolchain builds for both targets, with cross-host deterministic hashes.
- C and assembly editing now receives the real compiler's line diagnostics after safe server validation.
- Canonical PRG32-QT delivery is recorded for Blocks-C, Blocks-assembly, Advanced C, handwritten assembly and AudioStudio audio-check cartridges.
- Disposable HTTP Kit/CartridgeStore processes now demonstrate shared accounts, one-time sign-on and publisher upload authorization.
- Tested SDK/Qt/QEMU patches make the intended audio migration concrete and reproducible.
- Documentation no longer uses ambiguous “this change” milestone rows.

## High

### H-00 — Mandatory GDPR accountability and rights evidence is absent

No `docs/privacy/` program exists, and repository search/source inspection found
no complete ROPA, role/legal-basis matrix, notices, rights workflows,
processor/transfer records, DPIA/DPO determinations, breach exercise or legal
approval. Existing project export, retention and admin deletion functions do
not cover the complete personal-data lifecycle. Reproduce with
`find docs/privacy -type f` (no directory) and compare the limited project
export/account deletion paths at `prg32_construction_kit/project_format.py:183`
and `prg32_construction_kit/retention.py:120` with the required data stores.
Expected: current technical, operational and counsel/DPO evidence. Actual:
partial privacy-supporting controls only. Create the privacy evidence program
and implement/test end-to-end rights before reassessment.

### H-00B — README, architecture and visuals materially lag the product

`README.md:8-23` advertises the older Blocks and JavaScript-simulator workflow
but omits the Full IDE, real WASM guest, debugger and AudioStudio.
`docs/architecture.md:17-44` likewise shows a linear Blocks-to-simulator pipeline
without account, cloud, Store, privacy, build-isolation, debugger or audio trust
boundaries. The only README hero (`README.md:5`) has no recorded commit, capture
recipe or review date, and no visual freshness manifest/checker was found.
Expected: current, reproducible, accessible documentation tied to the audited
revision. Actual: extensive but materially stale entry-point and architecture
evidence. Refresh the documentation and add automated freshness gates.

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

The expanded assessment scores **127/156**. The release is **NO-GO** because
`GDPR-01` and `DOC-02` fail mandatory gates, independently of the remaining
audio/hardware blockers.
