# ADR-0011: The design baseline and the briefs that refine it

**Status:** Accepted (2026-10-18)

## Context

The audits name `CLAUDE_PRG32_CONSTRUCTION_KIT_IMPLEMENTATION.md` as the design
input and found it missing from the repository (audit L-02). It existed only
outside the repository. Three later briefs refined it.

## Decision

- All briefs are committed unchanged under `docs/briefs/` (the remediation
  brief stays in `audit/`, where the auditor maintains it).
- `CLAUDE_PRG32_CONSTRUCTION_KIT_IMPLEMENTATION.md` remains the **design
  baseline**. It is **not superseded**: later briefs add constraints and order
  the work; where they are stricter (for example "no live publication without
  explicit human authorization"), the stricter text applies.
- Precedence when texts disagree: `AGENTS.md` and accepted ADRs, then the most
  recent brief, then the baseline. A conflict is resolved by a new ADR, as
  ADR-0004 did for handwritten assembly.
- Briefs describe goals. Status claims live only in `docs/capabilities.json`
  (checked by `tests/test_capabilities.py`) and `docs/traceability.md`.
