# Remediation plan

| Priority | Owner | Size | Remaining work | Acceptance evidence |
|---:|---|:---:|---|---|
| 1 | Deploying controller + DPO/counsel | M | Complete decisions D-0–D-10: controller/contact, legal bases, Member-State children's rules, DPIA, DPO review, retention, processors, transfers and service enablement. | Signed/dated deployment-specific record with no material release blocker open. |
| 2 | Controller incident team | S | Fill contacts/authority and run the breach tabletop with incident lead, privacy lead, DPO and school leadership. | Dated staffed exercise, 72-hour decision trace, findings and closure owners. |
| 3 | Kit + CartridgeStore maintainers | S | Reconcile shared username semantics: preserve the Kit username or document/version a pseudonymous Store identity migration. | `test_kit_user_can_sign_in_to_the_store` and all SSO/ticket/publisher tests pass against pinned canonical repos. |
| 4 | PRG32/PRG32-QT maintainers | M | Upstream buzzer retirement, firmware Qt engine and QEMU clock/reset fixes. | Canonical commits/PRs, clean upstream tests, updated pins and regenerated Kit artifacts. |
| 5 | Hardware QA | S | Run the prepared AudioStudio stereo-console capture and physical delivery. | Cartridge hash, firmware/config, delivery log, I2S WAV and passing comparison JSON. |
| 6 | Audio runtime | M | Resolve the frame/audio scheduling boundary for effects. | Whole-recording QEMU/browser event positions and stereo PCM match deterministically. |
| 7 | Delivery/accessibility/integrations | M | Exercise Qt desktop import, named screen reader and safe real cloud/OIDC/GitHub scenarios. | Dated hashes, versions and test-owned evidence for each boundary. |

Preserve deterministic generation, source visibility, validation, CSP, ownership, quotas, isolation, debug/cartridge identity and offline classroom behavior.
