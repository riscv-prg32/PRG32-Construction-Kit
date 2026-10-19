# ADR-0016: Academic identity with PKCE, issuer+subject accounts, scoped roles

**Status:** Accepted (2026-10-19). Implements ADR-0007, adapted so that the user
sync with CartridgeStore (`sso_protocol.py`, which must stay identical) is unchanged.

## Context

Audit H-02 and scenario E: one environment-configured OIDC provider through an
optional library, no PKCE, and accounts **linked by matching email**, so an identity
provider (or anyone who can register that address there) could take over a kit
account. Roles stop at the global ladder shared with CartridgeStore
(`reader` < `user`/`player` < `publisher` < `admin`); teachers cannot see their
students' work without being administrators; API tokens can do everything their
owner can; a session stays valid after a password change or a deactivation.

## Decision

1. **OIDC Authorization Code + PKCE** (`oidc.py`, no optional library): per
   flow a random `state`, `nonce` and PKCE verifier (`S256`) kept in the server-
   signed session, single use, expiring after 10 minutes; the return page is
   chosen at the start (`safe_next`), never from the callback. The ID token from
   the token endpoint is verified: algorithm in RS256/PS256/ES256 (never `none`
   or HMAC), key from the provider's JWKS by `kid` (fetched again once when an
   unknown `kid` appears: key rotation), signature, `iss` equal to the configured
   issuer, `aud` containing the client id (`azp` when several), `exp`, `iat`,
   `nonce`. Discovery, JWKS and token requests use https only (plain http only for
   loopback test providers), no redirects, timeouts and a size limit.
2. **Several providers**, configured by an administrator (`/admin/identity`,
   `/api/admin/identity_providers`): slug, name, issuer, client id, where the
   client secret lives (`env:NAME` or `file:/path`, never the secret itself),
   scopes, claim mapping. `PRG32_OIDC_*` still configures one provider (`oidc`).
3. **Accounts by issuer + subject** (`external_identities`, unique on
   `(issuer, subject)`). The first sign-in of a new identity creates a new account
   unless an account already uses that email: then sign-in is **refused** with an
   explanation, and the person signs in the usual way and links the school account
   from **Account** (the only way two identities meet: a deliberate act by the
   signed-in owner). Unlinking keeps at least one way to sign in. SAML uses the
   same table (issuer = IdP entity id, subject = NameID).
4. **Scoped roles.** The global roles stay exactly as in CartridgeStore and are
   still synchronised. Two kit-only layers sit beside them:
   - an **academic role** per account (`kit_role`): `student` (default),
     `teacher`, `facilitator`, or `service` (API tokens only, no interactive
     sign-in). Only an administrator sets it; an identity provider claim can map
     to `student`/`teacher`/`facilitator` for new accounts, never to a global role;
   - **classes** with members as `student`, `teacher` or `facilitator`. Teachers
     create classes and add or remove students in their own classes; facilitators
     and teachers can **read** (never change) their students' projects, sprites,
     builds and artifacts; administrators manage everything.
5. **Scoped API tokens:** `read`, `write`, `build`, `publish`, `admin` (old
   tokens keep full access), optional expiry; checked on every token request
   before any route runs.
6. **Sessions:** every session carries the account's `session_epoch` and its
   sign-in time. Changing the password, a role or the academic role, deactivating
   the account or **Sign out everywhere** raises the epoch, so older sessions end;
   sessions also end after `PRG32_KIT_SESSION_HOURS` from sign-in, however active.
7. **Deprovisioning:** an administrator deactivates an account: no sign-in, its
   sessions end, its tokens stop working, its items stay (retention is the storage
   policy's business). Reactivation restores access. Deleting stays as before.
8. **Audit:** sign-in by provider (success, refused and why), identity link and
   unlink, provider changes, class and membership changes, academic-role changes,
   deactivation, session revocation, token creation (with scopes) and revocation.
   No token, secret, code or ID token is ever logged.

## Consequences

- New tables `external_identities`, `identity_providers`, `classes`,
  `class_members` and new columns (`users.kit_role`, `users.disabled_at`,
  `users.session_epoch`, `api_tokens.scopes`, `api_tokens.expires_at`), added at
  start-up idempotently. Old `users.external_provider/external_id` values become
  identities with issuer `legacy:<provider>`.
- `cryptography` becomes a dependency (ID token signatures).
- Class roles and academic roles are not sent to CartridgeStore; a teacher in the
  kit is a `user` there unless an administrator gives them more.
- Not done here: SCIM provisioning, front-channel/back-channel logout from the
  identity provider (signing out of the kit does not sign out of the school).

## Amendment (2026-10-19, after the audit of `e2d0cef`): provisioning and logout

- **Provisioning: no SCIM.** Accounts are created just in time at the first
  school sign-in and switched off by a kit administrator (deprovisioning). A
  provisioning feed is not required for the classroom deployment and is not
  offered; adding one later means idempotent create/update/deactivate keyed by
  (issuer, subject), audited like the other account changes.
- **Switching a person off at the school** stops new kit sign-ins at once (the
  provider refuses them). A kit session that already exists lasts until it ends
  (`PRG32_KIT_SESSION_HOURS` from sign-in) unless a kit administrator switches the
  account off, which ends it immediately.
- **Logout is local only.** Signing out ends the kit session; it does not sign
  the person out of the school's provider (no RP-initiated, front- or
  back-channel logout). The sign-out answer says so (`school_session_ended:
  false`) and the page warns about shared computers.
- Evidence: `tests/test_identity_live.py` against Keycloak 26.0.7
  (`docs/identity_live_testing.md`), opt-in locally and in CI.
