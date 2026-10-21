# Remediation plan

| Priority | Owner | Size | Remaining work | Acceptance evidence |
|---:|---|:---:|---|---|
| 1 | Privacy lead + DPO/counsel | L | Establish processing inventory/ROPA, role/legal-basis and children's-data decisions, retention, subprocessors/transfers, DPIA/DPO determination and review ownership. | Dated/versioned privacy evidence with qualified approval and explicit unresolved questions. |
| 2 | Backend/security | L | Implement authenticated full-account access/portable export, rectification, erasure propagation, restriction/objection where applicable, provider revocation and auditable partial-failure handling. | Synthetic end-to-end tests across SQLite, files, logs, backups, cloud and Store boundaries. |
| 3 | Operations/security | M | Publish notices and implement breach, processor, transfer and backup-deletion procedures. | Notice-version records, tabletop evidence, 72-hour decision timeline, DPA/transfer register and deletion ageing proof. |
| 4 | Documentation/UX | M | Rewrite README and documentation map; refresh screenshots and architecture/data-flow diagrams with synthetic data. | Running-product comparison, meaningful alt text/text equivalents, capture recipes and human review record. |
| 5 | Documentation tooling | M | Add link/image/alt/reference/capability and visual-freshness CI gates. | CI failures demonstrated for stale/missing targets and a reviewed visual manifest tied to a commit. |
| 6 | PRG32/PRG32-QT maintainers | M | Upstream buzzer retirement, firmware Qt engine and QEMU clock/reset fixes. | Canonical commits/PRs, clean upstream tests, updated pins and regenerated Kit artifacts. |
| 7 | Hardware QA | S | Run the prepared AudioStudio stereo-console capture and physical delivery. | Cartridge hash, firmware/config, delivery log, I2S WAV and passing comparison JSON. |
| 8 | Audio runtime | M | Resolve the frame/audio scheduling boundary for effects. | Whole-recording QEMU/browser event positions and stereo PCM match deterministically. |
| 9 | Delivery/accessibility/integrations | M | Exercise Qt desktop import, named screen reader, safe real cloud/OIDC and iOS scenarios. | Dated hashes, versions and test-owned evidence for each boundary. |

Preserve deterministic generation, source visibility, validation, CSP, ownership, quotas, isolation, debug/cartridge identity and offline classroom behavior.
