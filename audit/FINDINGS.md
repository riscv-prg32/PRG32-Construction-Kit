# Findings

## Closed or materially improved

- Real PRG32 firmware/QEMU captures now confirm the browser engine's stereo samples between cartridge events.
- A tested PRG32-QT patch replaces the divergent floating-point mixer with the firmware engine and produces bit-identical hashes.
- AudioStudio's keyboard-only, archive and Compile workflows run in real Chrome, with PCM/traces and failure screenshots retained by CI.
- A real-toolchain AudioStudio cartridge, AUD0 block and strict physical-capture comparison tool are committed.
- The discovered soundtrack delta-timing defect was fixed and regression-tested.

## High

### H-01 — Canonical SDK still supports the obsolete buzzer

The SDK at `679dfb5` still declares and exports buzzer calls at portable ABI indices 5, 7 and 8. The Kit refuses new C/assembly use and makes legacy calls silent, but `docs/upstream/README.md` is only a proposal. Remove/version the feature upstream, reserve the indices safely and regenerate every consumer.

## Medium

### M-01 — Stereo parity changes are not canonical upstream

`docs/upstream/prg32-qt-firmware-audio.patch` is well tested, but the released PRG32-QT checkout still uses its non-ADSR mixer. Merge an equivalent change upstream and test the released artifact.

### M-02 — QEMU event timing diverges

The firmware/QEMU path advances envelopes and the tracker by emulated wall time while emitting fixed 20 ms buffers, so events occur early. Fix the upstream QEMU audio clock to advance from rendered sample count, then require whole-recording parity.

### M-03 — Physical stereo path remains unverified

The cartridge, capture procedure and comparator are ready, but `docs/hardware_audio_check.md` explicitly records that no console capture exists. Run it on a stereo-wired ESP32-C6 PRG32 and retain delivery, firmware and I2S evidence.

### M-04 — Local fixture reproduction unavailable

The audit host lacks the PRG32 RISC-V toolchain, so the committed audio fixture rebuild checks skipped. CI documents an equipped job, but this audit independently verified only stored hashes and tests.

## Low

### L-01 — Human assistive-technology evidence remains open

Keyboard and automated accessibility scenarios pass. Complete the AudioStudio tasks in `docs/accessibility_session.md` with a human screen-reader session.

## Release conclusion

The Construction Kit's AudioStudio classroom workflow is credible and reference-tested through browser and firmware/QEMU. Complete ecosystem audio release remains **NO-GO** until upstream buzzer removal, canonical Qt integration, corrected QEMU timing and physical stereo capture are complete.
