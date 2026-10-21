# Security of processing (Article 32): review

**Version 1.0, reviewed 2026-10-21 by the kit's maintainers. Not yet reviewed by the controller
or its DPO (D-8).**

| Measure | What the kit does | Evidence |
|---|---|---|
| Access control | Every page and API needs a signed-in account, except sign-in, static files, docs, `/privacy` and discovery. Items belong to their owner. Teachers can only read their classes' work. Admin routes need the admin role. API tokens are checked against their scopes. | `tests/test_auth.py`, `tests/test_authorization.py`, `tests/test_privacy_rights.py` |
| Authentication | Passwords hashed. Sign-in attempts throttled (counters keyed by a hash). Sessions end a fixed time after sign-in, and "end all sessions" exists. School sign-in uses PKCE, single-use state and nonce, and full ID-token checks. | `tests/test_security_controls.py`, `tests/test_identity.py`, live Keycloak suite |
| Confidentiality of secrets | Token hashes only. Cloud tokens encrypted (Fernet). Secrets never logged, never returned, never exported. | `tests/test_cloud_storage.py`, `tests/test_privacy_rights.py` |
| Browser security | Strict CSP: no inline scripts, no `unsafe-eval`. Every library is vendored. Cross-site POSTs blocked. The `user_changed` refusal. | `tests/test_frontend_offline.py`, browser suites |
| Isolation of builds | Each build runs in its own folder, in a sandbox (bubblewrap, AppArmor) with disk budgets and no network. | `tests/test_build_sandbox.py`, CI Linux jobs |
| Minimisation | Guests store nothing on the server. School sign-in keeps issuer, subject and email only. Cloud access is limited to the app's folder. | ADR-0016, ADR-0017, ADR-0019 |
| Availability and resilience | Online backups, verified restore, and a restore drill. | `tests/test_backup_restore.py`, `docs/backup_restore.md` |
| Integrity | Optimistic version checks: no silent overwrite. Deterministic builds. | ADR-0017 tests |
| Accountability | Audit log of security and privacy actions. Notice records. The request register. | `security.py`, `privacy.py` |
| Testing | CI on every push, including real browsers, the toolchain container, and the Linux sandbox. Live suites against throwaway services. | `.github/workflows/tests.yml`, `docs/live_testing.md` |
| Incident response | [breach_playbook.md](breach_playbook.md), and a rehearsal in [exercises/](exercises/) | |

## Open items

| Id | Item | Risk | Proposal | Status |
|---|---|---|---|---|
| S-1 | Store bearer tokens (`publish_profiles.bearer_token`) are stored in clear in the database. They are never returned by the API. | Someone who reads the database file or a backup can publish as that profile. | Encrypt them like cloud tokens, and keep backups encrypted. | open (D-11) |
| S-2 | Backups contain everything, including the secret key | Exposure of all data | Encrypt the backup archives and store them in the EEA (operator) | operator's configuration |
| S-3 | Web-server logs are outside the kit's retention | Addresses kept longer than needed | Rotate at 14 days (operator) | operator's configuration |
| S-4 | No independent penetration test | Unknown weaknesses | Commission one before a large deployment | open |
| S-5 | Ordinary reads of projects are not audited (rehearsal finding F-3) | The extent of a breach is harder to establish | Keep server access logs for 14 days; consider auditing reads by API tokens | open |
| S-6 | No alert on sign-ins from new addresses (rehearsal finding F-2) | Late detection | Alerting outside the kit (log monitoring), or a future kit feature | open |
