# Remediation status

Tracks the audit findings (`FINDINGS.md`) against the remediation brief.
Statuses: implemented and verified, implemented but unverified, partial,
missing, blocked. The audit's recommendation stays **NO-GO** until every
release gate in `CLAUDE_REMEDIATION_BRIEF.md` holds.

| Finding | Phase | Status | Evidence |
| --- | --- | --- | --- |
| H-01 SSRF through publish profiles | 1 | Implemented and verified (automated, local servers only) | ADR-0008; `prg32_construction_kit/store_policy.py`, `publisher.py`; `tests/test_store_egress.py` (94 cases). The audit reproduction (student profile → loopback listener) was run before and after the fix: before, the listener received the upload and its answer was echoed; after, the profile is refused (400) and the seeded loopback profile is refused at publish (`insecure`), with no request reaching the listener. Not exercised against a live public Store. |
| H-02 Publisher role / confirmation | 2 | Missing | — |
| H-03 Unsandboxed builds | 3 | Missing | — |
| H-04 Full IDE incomplete | 8–9 | Missing | — |
| M-01 … M-06, L-01, L-02 | 4–11 | Missing / unchanged | — |

## Requirements matrix changes

Conservative: no score changes yet. SEC-01 stays 2 (H-03 still open);
STR-02 stays 1 (H-02 still open). Notes added below the matrix.
