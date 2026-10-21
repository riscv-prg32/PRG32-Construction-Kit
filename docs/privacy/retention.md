# Retention and deletion

**Version 1.0, 2026-10-21.** The defaults below are what the kit does when nobody changes
them. The controller confirms or changes each period (decision D-5 in
[decisions.md](decisions.md)).

## What is kept, for how long, and what deletes it

| Data | Kept for (default) | Setting | What deletes it |
|---|---|---|---|
| Accounts and everything they own | while the account exists | none | Erasure request, or the administrator's delete with items |
| Switched-off accounts | until reviewed | none | Listed by the retention run for an administrator to decide (never deleted automatically) |
| Projects in "Recently deleted" | 30 days | `PRG32_KIT_TRASH_DAYS` | Retention run: the project with its history, assets, builds, artifacts and folders |
| Builds and their files | the newest 10 per project | `PRG32_KIT_KEEP_BUILDS` | Retention run and every compile |
| Uploaded files | as long as their artifact | none | Deleting the artifact removes its file (`retention.delete_artifact`) |
| Interrupted build folders | 1 hour | none | Retention run |
| Audit log | 365 days | `PRG32_KIT_AUDIT_DAYS` | Retention run. Erasure pseudonymises the person in it at once and drops their address. |
| Sign-up links | 1 day after expiry or use | none | Retention run |
| Sign-in attempt counters (hashed) | their window (minutes) | none | Start-up and the next attempt |
| Single sign-on tickets | minutes | none | Expiry |
| Cloud tokens (encrypted) | until disconnected | none | Disconnect, or erasure (revoked at Google; Microsoft offers no revocation) |
| Notice records | while the account exists | none | Erasure |
| Rights requests | kept under a pseudonym after erasure, as accountability evidence | the controller decides (D-5) | Not yet automated: open item R-1 |
| Session cookie | a fixed time from sign-in | `PERMANENT_SESSION_LIFETIME` | Sign-out, "end all sessions", erasure |
| Browser storage (guests, unsaved work) | until the person clears it | none | The person |
| **Backups** | **35 days** | `PRG32_KIT_BACKUP_DAYS` | `python3 tools/backup_restore.py prune --folder <backups> --keep-days 35`, run daily |
| Web server and proxy logs | **set by the operator; recommended 14 days** | the server's | Log rotation (outside the kit) |

Run the retention policy daily:

```bash
flask --app app prg32-retention --apply
```

`--apply` deletes. Without it, the command only shows what it would delete.

## Erasure and backups

An erasure removes the person from the running kit at once. Their data stays in the backups
made before it, until those backups are pruned. The erasure result says by which date
(`backups_expire_by`).

Restoring a backup could bring an erased person back. So:

1. Keep the **erasure register** outside the backups. Refresh it after every erasure:
   `flask --app app prg32-privacy-erasures --out /secure/erasures.json`. It holds
   pseudonyms only.
2. After restoring a backup, erase those people again:
   `flask --app app prg32-privacy-reapply --register /secure/erasures.json`.

`tests/test_privacy_rights.py::test_a_restored_backup_does_not_bring_an_erased_student_back`
proves this end to end.

## Open items

- **R-1:** the request register has no automatic retention. The controller sets the period
  (D-5); until then, administrators delete old entries by hand.
