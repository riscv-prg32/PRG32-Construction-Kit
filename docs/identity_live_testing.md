# Testing school sign-in against a real identity provider

`tests/test_identity_live.py` runs the kit's school sign-in (OpenID Connect,
ADR-0016) against a real provider. It is **opt-in**: normal test runs skip it.

## With Keycloak (no account needed)

Keycloak is an OpenID Connect provider many universities run. The suite starts
it in Docker with a test realm (`tests/fixtures/oidc/school-realm.json`: three
test users and a test client secret, nothing real) and removes it afterwards.

```bash
PRG32_LIVE_OIDC=keycloak python3 -m pytest -q -rs tests/test_identity_live.py
```

Needs Docker and Chrome (or Playwright's Chromium); port 8080 and 5155 free. In
CI it runs only when started by hand (*Actions → Run workflow*, job
*Live identity provider*), and keeps `live-identity-results-<sha>`.

## With your institution's tenant

Ask the identity team for a **test** client and a **test** pupil account. Register
`http://127.0.0.1:5155/auth/oidc/school/callback` as a redirect address. Nothing
is committed; everything comes from the environment:

```bash
PRG32_LIVE_OIDC=external PRG32_LIVE_OIDC_ISSUER=https://login.school.example/realms/students PRG32_LIVE_OIDC_CLIENT_ID=prg32-kit-test PRG32_LIVE_OIDC_SECRET=... PRG32_LIVE_OIDC_USER=test.pupil PRG32_LIVE_OIDC_PASSWORD=... PRG32_LIVE_OIDC_EMAIL=test.pupil@school.example python3 -m pytest -q -rs tests/test_identity_live.py
```

If the provider's login form uses other fields, set
`PRG32_LIVE_OIDC_FORM="#user;#pass;#submit"`. Tests that need provider
administration (key rotation, switching a user off at the school, role claims)
run only with Keycloak.

## What it checks

| Check | How |
| --- | --- |
| Discovery, JWKS, real browser login | the full flow through the provider's own sign-in page |
| PKCE is enforced by the provider | the kit sends a wrong verifier: the provider refuses the code |
| State | the provider returns to a browser whose kit session never started that sign-in |
| Expiry and audience | the kit's clock moved an hour ahead; a client id that is not the token's audience |
| Accounts by issuer + subject | the stored identity is the provider's issuer and subject |
| Collision and explicit linking | an existing kit account with the same email is refused, then linked from Account, then unlinked |
| Deactivation and recovery | switched off in the kit (sessions end at once, sign-in refused), switched on again (same account); switched off at the school (the provider refuses) |
| Key rotation | the provider gets a new signing key; the kit fetches it and verifies |
| Role claims | `faculty` gives the academic role `teacher`, never a global role |
| Logout | signing out of the kit reports that the school session was not ended |

Recorded runs are in `implementation-status.md`.
