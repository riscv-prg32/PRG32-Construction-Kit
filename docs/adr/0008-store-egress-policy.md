# ADR-0008: Store egress policy (closing audit finding H-01, SSRF)

**Status:** Accepted (2026-10-18)

## Context

Any signed-in user could save a publish profile with any `store_url`, and
`POST /api/publish` then made the server POST a bundle there and returned the
answer. That let a student reach services on the server's network
(loopback, school LAN, cloud metadata addresses): an authenticated SSRF
(audit H-01). CartridgeStore's contract is one endpoint,
`POST <store>/api/publish/bundle` (multipart `bundle`), answering JSON such as
`{"ok", "status": "pending", "submission_id", "id", "version", "submitted"}`
(CartridgeStore `app.py` `publish_bundle_request`, unchanged in its current
upstream).

## Decision

1. **Allow-list of Store origins, set by the deployment administrator.**
   `PRG32_STORE_ALLOWED_ORIGINS` (comma-separated `scheme://host[:port]`).
   When unset it is the origin of `PRG32_STORE_URL` plus the origin of
   `PRG32_SSO_PEER_URL`, both of which only the administrator sets. Profiles
   whose URL is not on the list cannot be saved, and are refused again at
   publish time (the list may change).
2. **URL shape.** Only `https`, or `http` when trusted-local mode is on (see
   4). No user name/password, query or fragment; a valid port; a host name in
   IDNA/ASCII form or a canonical IP literal. Ambiguous numeric hosts
   (`2130706433`, `0x7f000001`, `0177.0.0.1`, `127.1`), IPv6 zone ids and
   trailing dots are refused.
3. **Destination addresses.** The host is resolved once; *every* address
   must be public: loopback, private (RFC 1918, ULA), link-local (incl.
   169.254.169.254), multicast, unspecified, reserved, shared (100.64/10),
   documentation/benchmark ranges and IPv4-mapped forms of those are refused.
   The connection is then made **to that checked address** (TLS still
   verifies the host name), so a second DNS answer (rebinding) cannot change
   where the bundle goes.
4. **Trusted local Store (explicit).** `PRG32_STORE_TRUSTED_LOCAL=1` allows a
   Store on a private or loopback address (a classroom LAN or a developer
   laptop). Plain `http` additionally needs `PRG32_KIT_ENV` other than
   `production`. Allow-listing is still required.
5. **No redirects**, connect timeout 5 s, read timeout 30 s, at most 64 KiB
   of response read; an answer that is not JSON or too large is reported as
   "unexpected answer".
6. **Student-safe results.** The browser gets `ok`, the HTTP status, a short
   message, and only known Store fields (`status`, `submission_id`, `id`,
   `version`, `submitted`, `review_required`, `error`). Never resolved
   addresses, raw bodies, headers or tokens.
7. **Audit.** Every allowed and refused attempt is audited with a reason code
   and the Store host; never the token.

## Consequences

- Deployments must list their Store (one variable). A laptop with a Store on
  `http://127.0.0.1:5080` needs `PRG32_STORE_TRUSTED_LOCAL=1` (and not
  production).
- Proxies (`HTTPS_PROXY`) are not used for Store uploads; the kit connects
  directly so it can pin the checked address.
- Publishing authorization and confirmation (H-02) and build isolation
  (H-03) are separate decisions and changes.
