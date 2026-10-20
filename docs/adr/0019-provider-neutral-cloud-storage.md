# ADR-0019: Provider-neutral cloud storage (Google Drive, OneDrive)

**Status:** Accepted (2026-10-20, priority 4 of the brief after audit `e2d0cef`)

## Context

Students want to continue a project at home. The capability table listed Google Drive
and OneDrive as missing. Identity (ADR-0016) and conflict-safe versions and quotas
(ADR-0017) are now stable, so cloud copies can reuse them instead of inventing new
rules.

## Decision

1. **Optional and server-side.** Off unless an administrator configures a provider.
   Only signed-in accounts use it; guests and offline use are unchanged. Tokens are
   kept on the server so the browser never holds them.
2. **One small interface**, `CloudProvider` in `cloud_storage.py`: `account`, `list`,
   `metadata`, `load`, `find`, `create`, `save(expected_revision)`,
   `delete(expected_revision)`, `revoke`. `GoogleDrive` and `OneDrive` implement it;
   consent, tokens, retries, conflicts and quotas are shared.
3. **Least privilege:** Drive `drive.file`; OneDrive `Files.ReadWrite.AppFolder`,
   `User.Read`, `offline_access`. Authorization Code with PKCE (S256), single-use
   state bound to the kit user, 10 minutes. The student ticks a consent box that says
   what the permission means before the provider is contacted.
4. **Tokens** are Fernet-encrypted with a key derived (HKDF) from
   `PRG32_CLOUD_TOKEN_KEY` or `SECRET_KEY`, never returned by the API and never
   logged. They are refreshed before expiry and once after a `401`; a refused refresh
   marks the account *needs reconnect* and changes nothing. Disconnect revokes at
   Google; Microsoft offers no per-app revocation, so the kit forgets the tokens and
   says so.
5. **Fixed egress:** HTTPS to the providers' own hosts only, no redirects, bounded
   answers, timeouts. Retries: reads and conditional writes at most 3 attempts
   (0.5 s, 1 s, `Retry-After` up to 8 s) on 429/5xx/connection errors; creates are not
   repeated blindly, and the next attempt first looks for the file
   (Drive: `appProperties` project id + SHA-256; OneDrive: the deterministic name
   `<title>-<project id>.prg32project.zip` and its content).
6. **Deterministic sync metadata.** The cloud file is the project archive
   (`project_format.export_archive`, byte-reproducible). A link records the kit
   project version, the cloud revision (Drive `version`, OneDrive `eTag`) and the
   archive's SHA-256 at the last sync. A new revision with the same bytes (a rename)
   is not a change.
7. **Never overwrite silently.** Both sides changed → `409 cloud_conflict` with the
   choices `copy`, `take_remote`, `overwrite`, the same three as a registered
   project conflict. `take_remote` must name the local `expected_version`, keeps the
   local version in History and replaces it conditionally (a restore now also claims
   a new project version); `overwrite` must name the cloud revision the student saw.
   A cloud file deleted elsewhere is never recreated silently (`remote_missing`,
   choice `copy`). A link made with another cloud account of the same provider is
   never written (`other_account`, choice `copy`). Deleting moves a file to the
   provider's trash and must name its revision.
8. **Tests:** one contract suite against in-process fakes of both providers, a real
   browser test, and an opt-in suite against a real test account configured only
   from the environment.

## Consequences

- Google Drive has no conditional upload; the check-then-write window is documented.
- OneDrive uploads are limited to 4 MB (simple upload).
- No live tenant was available while this was written: CLD-01/CLD-02 stay *partial*
  until the opt-in suite runs against real test accounts.
