# ADR-0007: OIDC with PKCE, issuer+subject linking, wider roles

**Status:** Superseded by ADR-0016 (implemented 2026-10-19; roles became kit-only academic roles and classes so the CartridgeStore sync stays unchanged)

## Context

The kit has `user`/`admin` roles plus groups, mirrored from CartridgeStore,
and one environment-configured OIDC provider without PKCE that links users by
`("oidc", sub)`.

## Decision

- Add Authorization Code + PKCE (`code_challenge_method=S256`) and validate
  issuer, audience and nonce.
- Link external accounts by **immutable issuer + subject**, never by email.
- Support several providers configured by an admin; client secrets are
  referenced from the environment or a secret file, never shown or logged.
- Add roles `guest`, `student`, `teaching_assistant`, `teacher`,
  `publisher`, `admin` only together with CartridgeStore, because roles are
  synchronised through `sso_protocol.py` (which must stay identical).
- Never grant admin or publisher from an email domain alone.
