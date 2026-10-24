# Design briefs

The briefs that steered the Full IDE work, kept unchanged so that decisions can
be traced back to the text they answer (ADR-0011).

| Brief | Received | Role |
| --- | --- | --- |
| `CLAUDE_PRG32_CONSTRUCTION_KIT_IMPLEMENTATION.md` | 2026-10-18 | **Design baseline**: target architecture, gates G0–G8, definition of done. |
| `CLAUDE_PRG32_QUALITY_IMPROVEMENT_ROUND.md` | 2026-10-18 | Quality round 1: admin bootstrap, provenance, restore identity, throttling, audit log. |
| `../../audit/CLAUDE_REMEDIATION_BRIEF.md` | 2026-10-18 | Remediation of the first independent audit (H-01..H-04 and phases 1–11). Kept with the audit. |
| `CLAUDE_PRG32_FULL_IDE_REFINEMENT.md` | 2026-10-18 | Refinement after the second audit (phases 0–9). |
| `CLAUDE_PRG32_REFINEMENT_AFTER_AUDIT_731E378.md` | 2026-10-19 | After the audit of 731e378: IDE browser suite in CI, documentation drift, language intelligence (phase 3) onward. |
| `CLAUDE_PRG32_REFINEMENT_AFTER_AUDIT_5DD98A9.md` | 2026-10-19 | After the audit of 5dd98a9: evidence drift, academic identity, storage policies, contracts, cloud, isolation, debugger polish, delivery. |
| `CLAUDE_PRG32_REFINEMENT_AFTER_AUDIT_E2D0CEF.md` | 2026-10-19 | After the audit of e2d0cef: release records, live IdP harness, shared Store contracts, cloud storage, build hardening, delivery, debugger polish. The current work order. |
| `CODEX_PRG32_CONSTRUCTION_KIT_QUALITY_AUDIT_AUDIOSTUDIO.md` | 2026-10-21 | Current independent audit specification, including hard audio, GDPR and documentation/visual freshness gates. |
| `CLAUDE_PRG32_GDPR_DOCUMENTATION_REFINEMENT_AUDIT_951F782.md` | 2026-10-21 | Refinement work order for GDPR accountability, privacy operations, the main README, screenshots, images and architecture schemas. |
| `CLAUDE_PRG32_REFINEMENT_AFTER_AUDIT_BB2B062.md` | 2026-10-22 | Refinement note after the audit of bb2b062 (NO-GO, 131/156): the controller's GDPR decisions, the Kit/Cartridge Store shared-identity contract, and the remaining ecosystem gates. |
| `CLAUDE_PRG32_REFINEMENT_AFTER_AUDIT_FE2E2C4.md` | 2026-10-23 | Refinement note after the audit of fe2e2c4 (NO-GO, 131/156): merge and pin the Store identity contract, prove the Docker process-limit repair on Linux, the controller's GDPR decisions. The current work order. |

The briefs are inputs, not evidence: what is implemented is recorded in
`../capabilities.json` / `../capabilities.md`, `../traceability.md` and the
tests.
