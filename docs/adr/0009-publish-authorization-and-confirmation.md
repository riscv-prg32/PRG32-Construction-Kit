# ADR-0009: Publishing needs the publisher role and a confirmed review (audit H-02)

**Status:** Accepted (2026-10-18)

## Context

`POST /api/publish` accepted any signed-in user, any `store_bundle` or
`source_bundle`, and the Publish page sent it on one click (audit H-02).

CartridgeStore's actual contract (`app.py` `publish_bundle_request`,
unchanged upstream): one upload endpoint, `POST /api/publish/bundle`, that
creates a **pending submission**; Store editors verify or reject it. There is
no draft, update, visibility or idempotency-key API, and errors come back as
`400 {"ok": false, "error": "..."}`. Both services share the role ladder in
`sso_protocol.ROLES`: `reader < user = player < publisher < admin`.

## Decision

1. **Permission.** Publishing from the kit needs role `publisher` or
   `admin` (`role_at_least(role, "publisher")`), checked in the backend on
   both the review and the confirm step. The Store still applies its own
   login and editor review; the kit's check is the classroom approval step
   before anything leaves the school.
2. **Only real cartridges.** The bundle must be a `store_bundle` with
   `metadata.publishable`, inside the kit's data folders, a valid zip with a
   `prg32-metadata-1.0` manifest whose every architecture file exists in the
   zip and starts with the `PRG2` cartridge magic. When the bundle came from
   a kit build, each cartridge's SHA-256 must equal the build provenance.
3. **Review, then confirm.** `POST /api/publish/review` returns a
   server-made summary (Store origin and host, authentication used, cartridge
   id/title/version, architectures with file sizes and SHA-256, bundle
   SHA-256 and size, what happens at the Store) and a `review_token`: the
   SHA-256 of that summary, the user, profile and bundle ids, signed with the
   server's secret, valid 15 minutes. `POST /api/publish` needs that token and
   `"confirm": true`; it rebuilds the summary and refuses (`409`) if anything
   differs, so a bundle or profile cannot be swapped after review.
4. **States and retries.** Each confirmed review is one *publish attempt*
   (`publish_attempts` table, unique per summary digest): `uploading` →
   `submitted` (Store answered OK: pending review there) or `failed`
   (recoverable: retry with the same token while it is valid, or review
   again). Confirming a review that is already `submitted` returns the stored
   result without uploading again; a second confirm while `uploading` gets
   `409`. Draft, update and visibility states are **not applicable**: the
   Store has no such API (not invented here).
5. **Audit.** `publish_review` (allowed/refused) and `publish` with
   `metadata.stage` (`refused`, `upload`, `submitted`, `failed`,
   `duplicate`), never tokens.

## Consequences

- `POST /api/publish` keeps its route but now answers `428` without a
  review token (documented migration). Scripts must call review first.
- Students without the publisher role can build and download, not publish;
  a teacher grants `publisher` on the Users page (synced with the Store).
