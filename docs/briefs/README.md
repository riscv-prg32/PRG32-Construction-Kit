# Design briefs

The briefs that steered the Full IDE work, kept unchanged so that decisions can
be traced back to the text they answer (ADR-0011).

| Brief | Received | Role |
| --- | --- | --- |
| `CLAUDE_PRG32_CONSTRUCTION_KIT_IMPLEMENTATION.md` | 2026-10-18 | **Design baseline**: target architecture, gates G0–G8, definition of done. |
| `CLAUDE_PRG32_QUALITY_IMPROVEMENT_ROUND.md` | 2026-10-18 | Quality round 1: admin bootstrap, provenance, restore identity, throttling, audit log. |
| `../../audit/CLAUDE_REMEDIATION_BRIEF.md` | 2026-10-18 | Remediation of the first independent audit (H-01..H-04 and phases 1–11). Kept with the audit. |
| `CLAUDE_PRG32_FULL_IDE_REFINEMENT.md` | 2026-10-18 | Refinement after the second audit (phases 0–9). |
| `CLAUDE_PRG32_REFINEMENT_AFTER_AUDIT_731E378.md` | 2026-10-19 | After the audit of 731e378: IDE browser suite in CI, documentation drift, language intelligence (phase 3) onward. The current work order. |

The briefs are inputs, not evidence: what is implemented is recorded in
`../capabilities.json` / `../capabilities.md`, `../traceability.md` and the
tests.
