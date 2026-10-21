# Remediation plan

| Priority | Owner | Size | Remaining work | Acceptance evidence |
|---:|---|:---:|---|---|
| 1 | PRG32 SDK/ABI | M | Remove or version out every legacy buzzer entry in the canonical portable ABI and regenerate all consumers. | Repository-family search and ABI fixture prove no supported authoring/runtime surface exposes buzzer; documented legacy cartridges remain safely silent or receive an explicit migration error. |
| 2 | Runtime/audio | L | Make PRG32-QT consume the canonical renderer, or explicitly remove it from the audio-reference set. | Same eight-voice fixture produces matching/tolerance-bounded L/R PCM, ADSR traces, clipping and stop/reset behavior. |
| 3 | Firmware/QEMU | M | Add deterministic stereo capture to the firmware/QEMU validation path. | Toolchain-built fixture and recorded tool revisions produce auditable channel hashes/waveforms. |
| 4 | Hardware QA | M | Exercise the complete AudioStudio -> cartridge -> device path. | Physical stereo capture verifies eight simultaneous voices, pan separation, envelopes, effects, tracks, silence/reset and no obsolete buzzer output. |
| 5 | Product/accessibility | S | Complete human keyboard/screen-reader review and preserve browser/audio artifacts in CI. | Recorded accessibility findings and downloadable PCM/trace/browser artifacts for failing conformance runs. |

These changes must preserve deterministic generation, server validation, cartridge/debug identity, ownership, quotas, CSP, offline classroom use and inspectable generated C/assembly.
