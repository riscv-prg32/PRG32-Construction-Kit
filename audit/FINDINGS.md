# Findings

## Closed or materially improved

- All authoring modes now have retained real-toolchain builds for both targets, with cross-host deterministic hashes.
- C and assembly editing now receives the real compiler's line diagnostics after safe server validation.
- Canonical PRG32-QT delivery is recorded for Blocks-C, Blocks-assembly, Advanced C, handwritten assembly and AudioStudio audio-check cartridges.
- Disposable HTTP Kit/CartridgeStore processes now demonstrate shared accounts, one-time sign-on and publisher upload authorization.
- Tested SDK/Qt/QEMU patches make the intended audio migration concrete and reproducible.
- Documentation no longer uses ambiguous “this change” milestone rows.

## High

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

The Construction Kit itself is increasingly release credible and scores **126/148**. The complete ecosystem audio/hardware release remains **NO-GO** until upstream patch adoption and physical stereo evidence.
