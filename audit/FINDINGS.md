# Findings

## Critical

No confirmed unauthenticated critical exploit was demonstrated. The following High findings are release blockers under the requested gate.

## High

### H-01 — Authenticated SSRF through publish profiles

- Evidence: any signed-in user can create a profile with arbitrary `store_url` (`routes.py:261-280`; `publish.js:41-46`). Publishing joins it with `/api/publish/bundle` and performs a server-side `requests.post` (`publisher.py:10-16`). There is no scheme/host allow-list, DNS/IP revalidation, redirect policy, or private-network rejection.
- Reproduction: create a publish profile whose URL targets a loopback/RFC1918/link-local service, create/select a bundle, then `POST /api/publish`. The server makes the request and returns status/body metadata.
- Expected: only administrator-approved HTTPS Cartridge Store origins; reject credentials in URLs, non-HTTPS, private/link-local/loopback destinations and redirect escape.
- Impact: authenticated students can probe or mutate internal HTTP services from the server's network position.
- Remedy: administrator-managed Store allow-list, resolved-IP checks before every hop, redirects disabled or revalidated, response-size cap, and negative SSRF tests.

### H-02 — Publisher role is not enforced and publication lacks confirmation

- Evidence: roles include `publisher` (`auth.py:49-55`), but `api_publish` has no role decorator/check (`routes.py:985-1014`). The UI sends the publication immediately on one click (`publish.js:51-56`). It also lists and permits `source_bundle` (`publish.js:17-29`; `routes.py:996`).
- Reproduction: sign in as ordinary `user`, create a profile and bundle, invoke `/api/publish`; the Kit attempts publication.
- Expected: publisher/admin scope, immutable review summary, explicit confirmation, publishable binary bundle only, idempotency/retry state.
- Impact: students may publish without the intended academic approval boundary and may upload invalid source-only bundles.
- Remedy: enforce scoped authorization server-side, validate `metadata.publishable`, implement draft/confirm/update states, and test unauthorized rejection.

### H-03 — Untrusted compilers run without an OS sandbox

- Evidence: build commands execute directly via `subprocess.run` with inherited environment plus private TMPDIR (`packager.py:75-87,117-150`). C/assembly validators state they are not a sandbox (`source_project.py:64-70,141-146`). Timeouts and slots limit duration/concurrency but not filesystem, network, process, memory, or syscall access.
- Reproduction: submit adversarial but validator-accepted sources and observe compilation under the web-service identity. A compiler/toolchain vulnerability or validator bypass inherits service access.
- Expected: disposable container/namespace, read-only SDK, no network, non-root UID, cgroup CPU/RAM/PID caps, empty writable build volume, seccomp/AppArmor, killed process group.
- Impact: unsafe server-side processing of student-controlled compiler inputs; release-gate blocker for multi-user deployment.
- Remedy: isolate every build and retain validators as defense in depth; add escape/resource-exhaustion tests.

### H-04 — Full IDE claim is materially incomplete

- Evidence: C and assembly are plain `<textarea>` controls (`templates/editor.html:72-82`); traceability marks JetBrains shell, Monaco, and language services open (`docs/traceability.md:32`). No command palette, project tree, diagnostic navigation, completion, workspace tabs, or editor accessibility evidence exists.
- Reproduction: open `/projects/<id>` and choose C or Assembly.
- Expected: requirements IDE-01/03/04.
- Impact: release labeling would misrepresent the product and removes essential learning/debug workflows.
- Remedy: deliver G2 as bounded PRs with vendored/offline Monaco, deterministic SDK indexes, diagnostics, keyboard/focus tests, and responsive shell.

## Medium

### M-01 — OIDC contract is below the required academic profile

`auth_adapters.py:41-81` configures one Authlib client and links identity as provider `oidc` plus `sub`. The code does not explicitly configure PKCE, issuer+subject storage, multiple providers, admin claim mapping, or disabled-user/group-change behavior. The required negative IdP matrix was not executed. Implement accepted ADR-0007 and provider contract tests.

### M-02 — PWA offline mode depends on uncached third-party assets

Bootstrap CSS/icons/JS and jQuery are remote (`templates/base.html:12-13,60-61`), and Blockly is remote (`templates/editor.html:137`). The service worker caches only same-origin `/static/` files (`service-worker.js:4-18,29-40`). A cold offline start cannot render/run the authoring UI, and CDN assets lack SRI/CSP evidence. Vendor pinned assets, include them in the cache, add CSP/SRI, and run cold/warm offline tests.

### M-03 — Store bundle is not independently validated against Store contract

The packager constructs metadata locally (`packager.py:53-72,225-260`) and upload forwards Store responses. No preflight validation against the inspected Store schema/endpoints, duplicate version workflow, or recovery transaction was found. Add a shared schema/conformance suite and Store integration fixtures.

### M-04 — Account/storage requirements are incomplete

All normal pages require login (`auth.py:598-626`), while guest IndexedDB/policy is absent. Registered storage has ownership/history but lacks quotas, autosave, retention/deprovisioning, and semantic concurrent merges (`implementation-status.md:54-57`). Complete ACC-01/02 with tenant quota and eviction tests.

### M-05 — Debugger lacks source-level teaching features

Address-level debugging is strong, but DWARF locals/call stack/watches and Blockly active-block/source maps are explicitly open (`implementation-status.md:60-62`; `traceability.md:49-50`). Add a debug build profile and deterministic source maps; preserve graceful address-only fallback.

### M-06 — Deployment targets are described, not verified

There is no executed hardware transfer/launch, PRG32-QT user import, or iOS handoff evidence. PRG32-iOS source/contract was not available. Label these workflows unverified and add signed artifact/hash handoff tests before release.

## Low

### L-01 — Dependency reproducibility and quality gates are incomplete

Python dependencies are bounded but not hash-locked (`pyproject.toml`, `requirements*.txt`); there is no configured lint/type checker, coverage gate, browser E2E, accessibility scanner, or performance budget. CI does have syntax, pytest, WASM, dependency-review, container and real-build jobs.

### L-02 — The named design baseline is absent

`CLAUDE_PRG32_CONSTRUCTION_KIT_IMPLEMENTATION.md` was not found in the repository or immediate sibling repositories. The committed ADRs and implementation plan are useful, but the audit cannot resolve conflicts against the named baseline. Commit the approved baseline or document its supersession.
