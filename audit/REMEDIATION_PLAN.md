# Remediation plan

| Priority | Owner | Size | Remaining work | Acceptance evidence |
|---:|---|:---:|---|---|
| 1 | PRG32 SDK | M | Apply an ABI-versioned buzzer retirement, reserving old indices as silent compatibility slots. | Canonical headers/JSON/generated ABI/examples/docs expose no supported buzzer; migration fixtures pass. |
| 2 | PRG32-QT | M | Merge the firmware-engine integration upstream and make the released runtime use it. | Clean canonical checkout builds; headless hashes match; desktop stereo playback is exercised. |
| 3 | PRG32 firmware | M | Advance QEMU audio state from rendered samples rather than emulated elapsed time. | Whole-recording QEMU/browser PCM and event timelines match the same fixtures. |
| 4 | Hardware QA | S | Run the prepared console check on stereo-wired PRG32 hardware. | Delivery record, firmware config/revision, I2S WAV and passing comparison JSON are retained. |
| 5 | Accessibility | S | Complete a human AudioStudio screen-reader session. | Dated results for tasks 10–14 in `docs/accessibility_session.md`. |

Do not weaken validation, deterministic generation, inspectable teaching source, CSP, ownership, quotas, build isolation, offline use or debug/cartridge identity.
