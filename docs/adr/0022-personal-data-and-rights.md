# ADR-0022: Personal data: one inventory, rights the kit can carry out, the school decides

**Status:** Accepted (2026-10-21, after the GDPR and documentation audit of `7c83e71`)

## Context

The audit's new gate GDPR-01 failed (0/4). The kit had useful controls: guests local-only,
ownership, encrypted cloud tokens, retention, backups. It had no record of processing, no
notices, no complete rights workflows and no incident procedure. Project archives and the
administrator's account delete were not a personal-data export or a complete erasure. The
kit is software that schools run. The legal decisions (roles, legal bases, DPIA, DPO,
processors, transfers) belong to each deploying school or operator, not to the kit's makers.

## Decision

1. **The school or operator is the controller.** `docs/privacy/` describes exactly what the
   kit does. Every legal decision is a *proposal* in `decisions.md`, with an owner and a
   status. While a release-blocking decision is open, the deployment is NO-GO, and
   `tests/test_privacy_records.py` refuses any claim that the gate passes.
2. **One inventory, checked against the code.** `docs/privacy/ropa.json` names every
   column of every table exactly once, with its purpose, legal basis, access, recipients,
   location, retention, deletion, transfers and review owner, plus the stores outside the
   database. `privacy.PERSONAL_TABLES`/`NOT_PERSONAL` classify every table. A new table or
   column fails the tests until it is classified.
3. **Rights the kit carries out** (`prg32_construction_kit/privacy.py`):
   - a structured personal-data export, without secrets;
   - a request register with one-month deadlines, extensions with reasons, and
     identity-check notes;
   - restriction (read and download only, HTTP 423 otherwise);
   - erasure in a fixed order:
     - cloud tokens revoked;
     - items, folders and files removed;
     - every row naming the person removed;
     - the audit log pseudonymised;
     - the account deleted, and the Store told;
   - a result that lists what stays outside the kit.

   Self-service requests need a signed-in browser, never an API token. An erasure needs a
   confirmation naming the account.
4. **Erasures survive restores.** Backups record their date and are pruned after
   `PRG32_KIT_BACKUP_DAYS`. The erasure register (pseudonyms) is kept outside the backups and
   re-applied after a restore.
5. **Notices where data is collected,** with versions (`privacy_notices.json`,
   `docs/privacy/notices/`). The version each person was shown is recorded.
6. **Incidents.** Local sign-ins and their failures are audited, with the address and never
   the typed text. A playbook with the 72-hour clock. `tools/breach_rehearsal.py` rehearses
   the technical steps on a throwaway kit.

## Consequences

- New tables: `privacy_requests`, `privacy_notice_records`. New column:
  `users.restricted_at` (idempotent migration).
- Deleting an artifact now deletes its file in the artifact folder, unless another artifact
  uses it. Before, uploads stayed on disk.
- Retention also expires the audit log (`PRG32_KIT_AUDIT_DAYS`, 365) and old sign-up links.
- Open items are recorded, not hidden:
  - Store bearer tokens are stored in clear (S-1);
  - reads are not audited (S-5);
  - there is no alerting (S-6).
