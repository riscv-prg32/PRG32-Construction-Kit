# Findings

## Resolved since audit `c0d115e`

- The browser now renders stereo PCM from the PRG32 firmware engine, not simple Web Audio oscillators.
- Eight concurrent voices with distinct SID-like waveforms, ADSR, volume and pan are exercised.
- Deterministic native/WASM PCM, envelope traces, separation, clipping, silence, pan/volume changes and busy-voice replacement are tested.
- AudioStudio provides instruments, effects, soundtracks, WAV samples, accessible preview, version conflicts, ownership/quotas, import/export, named Blocks and deterministic cartridge audio blocks.
- Reachable Kit paths reject or omit the buzzer; old cartridges remain silent and diagnosed.

## Critical

No exploitable critical security issue was confirmed.

## High

### H-01 — Canonical SDK still advertises the obsolete buzzer

- Evidence: ADR-0021 and `docs/capabilities.json` explicitly record that PRG32 SDK revision `679dfb5` still lists the buzzer in its portable ABI.
- Kit mitigation: `tests/test_no_buzzer.py` ensures no normal Kit UI/code path offers it and validators reject its use.
- Impact: the ecosystem contract remains contradictory; other SDK consumers can create cartridges using a removed feature.
- Remedy: remove buzzer functions/types/import slots from the canonical SDK through an ABI-versioned migration, update firmware/Qt behavior, then regenerate the Kit language index and fixtures.

## Medium

### M-01 — Stereo reference parity stops at native/WASM builds of the same engine

`tests/test_audio_conformance.py` proves deterministic identity between native and WASM builds, but not an independent firmware/QEMU or physical-device capture. PRG32-QT's current floating-point mixer lacks the firmware ADSR semantics. Update PRG32-QT to the canonical engine or clearly retire it as an audio reference, enable QEMU capture, and compare the same fixture across targets.

### M-02 — AudioStudio has no QEMU/hardware playback evidence

The generated AUD0 block and PRG32 cartridge are tested structurally and in the browser engine, but no recorded PRG32/QEMU or hardware stereo result demonstrates the full authoring-to-device chain.

### M-03 — Audio fixture reproduction is toolchain-dependent

`tools/build_audio_fixtures.py --check` could not run on this host because the PRG32 toolchain is absent. CI must preserve the toolchain-built fixture and PCM evidence as immutable artifacts.

### M-04 — External delivery and cloud evidence remains incomplete

Physical-device transfer, end-user Qt import, iOS handoff and real Google/Microsoft tenant runs remain unverified.

## Low

### L-01 — AudioStudio UI coverage is strong but not a recorded screen-reader session

Keyboard and axe checks pass; retain a short human screen-reader session for the new envelope, tracker grid and status announcements.

### L-02 — Legacy buzzer behavior needs an ecosystem migration note

The Kit refuses new source and silently renders old cartridges without buzzer sound while counting calls. Document the ABI/version transition for non-Kit cartridges and SDK users before upstream removal.

## Release conclusion

The AudioStudio classroom preview is credible. The complete audio release remains **NO-GO** until the canonical SDK no longer exposes buzzer support and stereo/ADSR behavior is demonstrated against an independent firmware/QEMU or device reference, with PRG32-QT aligned or explicitly de-scoped.
