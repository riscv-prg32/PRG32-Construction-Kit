# ADR-0002: Evolve the Flask backend instead of rewriting it

**Status:** Accepted

## Context

The backend is ~6k lines of tested Python (187 tests), with build isolation,
ownership checks, SSO shared with CartridgeStore and a published container.
`AGENTS.md` fixes the CRUD and action routes.

## Decision

Keep Flask, SQLAlchemy and the generic `/api/<resource>` CRUD. Add new
capabilities as focused modules and routes (`project_format.py`, later
revisions, guest policy, OIDC providers). Move to PostgreSQL through the
existing `DATABASE_URL` support rather than a new data layer. Object storage
is introduced only when bundle sizes or multi-node deployment require it.

## Consequences

No migration of clients is needed. The IDE shell (G2) is a new page that
talks to the same API.
