# Security review

## Overall assessment

No new critical exploit was confirmed. Store egress, publishing authorization and production build isolation remain materially improved and covered by negative tests. Refinement phase 1 additionally removes runtime CDN trust, vendors browser dependencies, adds strict CSP and proves static-only offline caching in Chrome.

## Browser security

The browser loaded only same-origin resources in the executed page matrix; no CSP violation was recorded. CSP avoids inline script, `unsafe-inline` and `unsafe-eval`. Vendored manifests record versions, hashes and licenses. The service worker caches only static resources, not authenticated pages or APIs; Chrome verified this. Remaining work includes a complete recurring dependency/SBOM vulnerability process and real screen-reader/performance testing.

## Authentication and authorization

Local credential/token hashing, throttling, ownership checks, stale-window refusal and audit records remain in place. Publishing enforces publisher scope and content-bound explicit confirmation. OIDC still lacks the required explicit PKCE, issuer+subject key, multi-provider administration, academic claim lifecycle and negative IdP execution. Course-scoped student/TA/teacher authorization is absent.

## Build and upload boundary

Source allow-lists remain defense in depth. Production configuration requires bubblewrap with isolated namespaces, no network, read-only toolchain/SDK, cleared environment, seccomp and resource limits. The Linux escape suite was not executable here. Known gaps remain: total build-directory quota, per-build UID and AppArmor portability.

Store SSRF/TLS/DNS/redirect/response-bound tests passed 94/94. No live Store was contacted. Publish tokens remain reversibly stored in the database; encryption or short-lived delegated credentials are preferable.

## Privacy and lifecycle gaps

The offline scratchpad is local and useful, but it is not the requested administrator-controlled guest policy with IndexedDB export/eviction guarantees. Registered quotas, retention/deprovisioning and conflict behavior are missing. Drive/OneDrive are absent, so OAuth scopes, refresh/revoke and provider privacy cannot be evaluated.
