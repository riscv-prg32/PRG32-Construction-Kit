# ADR-0017: Guest and registered storage policy

**Status:** Accepted (2026-10-19, refinement phase 6 of the brief after audit `5dd98a9`, objective 3)

## Context

Audit H-02 and scenarios A/B: guests have one offline scratchpad in
`localStorage`; registered students have no quota, no autosave, no protection
against two windows overwriting each other's save, and nothing is ever cleaned
up (soft-deleted projects, old builds and their folders stay for ever).

## Decision

### Guests: this browser only

1. **No server storage for guests, ever.** Guest projects live in the
   browser's IndexedDB (`static/js/guest_store.js`, database `prg32-kit-guest`).
   The guest workspace is the static offline page, so it also works with no
   server at all.
2. **Policy:** `PRG32_GUEST_MODE` = `local` (default: the sign-in page offers
   "Try without an account") or `off` (no such link). Option C of the design
   baseline, temporary server storage for guests, is **not offered**: it would
   need server-side quotas, expiry and abuse handling for anonymous users.
3. **Capacity:** the page shows `navigator.storage.estimate()` and asks for
   persistent storage; a full disk (`QuotaExceededError`) keeps the old copy and
   tells the student to save the project as a file.
4. **Export/import:** each project as a `prg32-construction-kit-project-1.0`
   JSON file, the format the dashboard already imports.
5. **After sign-in:** the dashboard finds guest projects in this browser and
   offers to move them into the account. Each is created on the server first and
   deleted locally only after the server confirmed it; a failure (for example a
   full quota) leaves it in the browser.
6. **Clearing** asks first, offers the export, and never runs by itself.
   The old scratchpad becomes a guest project the first time the page opens.

### Registered students

7. **Conflict-safe saves:** every project has a `version`, incremented by every
   change. A save may send `expected_version`; the server applies it only if the
   version still matches (a conditional `UPDATE`), otherwise it answers
   `409 {"code": "version_conflict", "current": ...}` and changes nothing. The
   IDE and the editor always send it: nothing is ever overwritten silently, and
   the student chooses to keep their version as a copy, take the saved one, or
   save over it on purpose.
8. **Autosave:** the IDE saves 5 seconds after the last change (and when the
   window is hidden), with `expected_version` and `"autosave": true`. Autosaves
   add to the History only when the newest revision is older than
   `PRG32_KIT_AUTOSAVE_SNAPSHOT_MINUTES` (10); explicit saves always do (as before).
   A conflict stops autosave until the student decides.
9. **Quotas** per account (administrators exempt): `PRG32_KIT_QUOTA_PROJECTS`
   (200) and `PRG32_KIT_QUOTA_MB` (200 MB, counting projects, revisions, sprites,
   assets, artifact texts and the files of their artifacts). Creating, importing,
   saving or compiling past them answers `413 {"code": "quota_exceeded"}`.
   `GET /api/storage` reports usage. `0` means no limit.
10. **Retention** (`retention.py`, `flask prg32-retention`, `POST
    /api/admin/retention`, dry run first): projects in Recently deleted for
    `PRG32_KIT_TRASH_DAYS` (30) are purged; each project keeps its newest
    `PRG32_KIT_KEEP_BUILDS` (10) builds, older builds lose their folder and
    artifacts; build folders no build refers to are removed. Builds are pruned
    for the project after every compile, the rest when an administrator runs it.
11. **Deprovisioning:** a switched-off account (ADR-0016) keeps its items;
    retention lists switched-off accounts for review but never deletes accounts
    by itself. `DELETE /api/users/<id>?with_items=1` deletes an account and its
    items and build folders, for an administrator who has exported what is needed.

## Consequences

- New column `projects.version` (added at start-up; old projects start at 0).
- Every build still uses only its own `<build_id>/` folder; retention deletes
  whole build folders only, after their database rows.
- The guest workspace keeps working offline; `guest_store.js` is cached by the
  service worker.
