# Remediation plan

| Priority | Owner | Size | Remaining work | Acceptance evidence |
|---:|---|:---:|---|---|
| 1 | PRG32/PRG32-QT maintainers | M | Upstream buzzer retirement, firmware Qt engine and QEMU clock/reset fixes. | Canonical commits/PRs, clean upstream tests, updated pins and regenerated Kit artifacts. |
| 2 | Hardware QA | S | Run the prepared AudioStudio stereo-console capture and physical delivery. | Cartridge hash, firmware/config, delivery log, I2S WAV and passing comparison JSON. |
| 3 | Audio runtime | M | Resolve the frame/audio scheduling boundary for effects. | Whole-recording QEMU/browser event positions and stereo PCM match deterministically. |
| 4 | Delivery QA | S | Exercise the visible PRG32-QT desktop Import workflow and validate evidence state association. | Human steps, screenshots/logs and hashes for all source modes. |
| 5 | Accessibility | S | Complete AudioStudio tasks 10–14 with a named screen reader. | Dated record with browser/AT versions, announcements and resolved defects. |
| 6 | Integrations | M | Execute safe real Google/Microsoft, institutional OIDC and iOS handoff tests. | Least-privilege tenant/device evidence with only test-owned data. |

Preserve deterministic generation, source visibility, validation, CSP, ownership, quotas, isolation, debug/cartridge identity and offline classroom behavior.
