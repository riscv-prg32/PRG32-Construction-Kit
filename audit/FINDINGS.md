# Findings

## Resolved release blockers

- **R-01 (former H-01, Store SSRF): closed.** Approved origins, IP/DNS checks, address pinning, no redirects, TLS verification and bounded responses are implemented in `store_policy.py` and `publisher.py`; adversarial tests exist in `tests/test_store_egress.py`.
- **R-02 (former H-02, unauthorized publishing): closed.** `_prepare_publish` rejects roles below publisher and non-publishable bundles; review tokens bind user/profile/artifact/content; confirmation and attempts are enforced (`routes.py:1004-1125`; `publishing.py:149-228`). Targeted tests passed.
- **R-03 (former H-03, unsandboxed compilation): closed in design and automated Linux evidence.** Production requires bubblewrap; the build gets isolated namespaces, read-only dependencies, one writable build directory, cleared environment, seccomp and rlimits (`build_sandbox.py:1-20,219-239`; `packager.py:140-160`). Linux escape tests were not independently executable on this macOS host.

## High

### H-01 — The claimed Full IDE core is absent

- Evidence: C and assembly remain plain textareas (`templates/editor.html:72-82`); traceability marks the JetBrains-style shell, Monaco and language services open (`docs/traceability.md:32`).
- Reproduction: open a C or Assembly project; there is no project tree, multi-file tab model, palette, completion, diagnostic navigation or SDK-aware editor.
- Impact: IDE-01/03/04 are missing and the product cannot accurately ship as the audited Full IDE.
- Remedy: deliver the shell and vendored editor first, retaining inspectable generated C/assembly and Blockly editability.

### H-02 — Mandatory source-level debugger behavior is missing

- Evidence: DWARF locals/call stack/watches and Blockly active-block mapping are explicitly open (`docs/traceability.md:49-50`; `docs/implementation-status.md:60-63`).
- Reproduction: load a cartridge in Player; address-level state exists, but scenario D's locals, call stack, watches, source breakpoint and active block checks cannot be performed.
- Impact: the audit release gate treats broken mandatory debugger functionality as NO-GO.
- Remedy: deterministic block→source→address maps plus a DWARF debug profile and graceful address-only fallback.

### H-03 — Academic identity and guest access contract is incomplete

- Evidence: OIDC is one environment-configured provider with no explicit PKCE and links `("oidc", sub)` (`auth_adapters.py:41-81`); guest IndexedDB/policy is only planned (`docs/implementation-plan.md:39`).
- Reproduction: inspect configured login registration and attempt scenario A/E; multi-IdP issuer identity, claim mapping, guest policy and recovery paths do not exist.
- Impact: required guest classroom use and academic tenant/role assurance are unavailable.
- Remedy: implement ADR-0007 and guest policies with the full negative IdP and isolation matrix.

## Medium

### M-01 — Cloud sync is absent

Google Drive and OneDrive are explicitly open (`docs/traceability.md:59`). Scenario B token expiry, revocation, conflicts and network loss cannot run.

### M-02 — Offline authoring depends on third-party CDNs

Bootstrap/icons/jQuery and Blockly load remotely (`templates/base.html:12-13,60-61`; `templates/editor.html:137`), while the service worker only caches same-origin static files (`static/service-worker.js:4-18,29-40`). A cold disconnected editor is not demonstrated and there is no CSP/SRI evidence.

### M-03 — Store validation is local rather than shared-contract conformance

The kit duplicates Store manifest constants and checks magic/hashes (`publishing.py:40-45,84-132`). No shared schema, live duplicate/version/visibility test, or public Store conformance run was performed.

### M-04 — Registered storage lacks quotas and robust concurrency policy

History/soft delete work, but autosave and search remain open (`docs/implementation-status.md:54-57`); quotas, retention/deprovisioning and semantic conflict handling are not enforced.

### M-05 — Delivery targets are unverified

No physical board transfer/launch, user-facing PRG32-QT import, or PRG32-iOS handoff was executed. iOS source was unavailable, so no interface is claimed.

### M-06 — Production sandbox still has documented operational gaps

There is no total build-directory quota or per-build UID, and AppArmor hosts require an exception (`docs/build_sandbox.md:65-76`). The current boundary is a strong improvement but needs operational hardening and independent x86_64/aarch64 evidence.

## Low

### L-01 — Reproducibility and quality gates are incomplete

Dependencies are range-pinned rather than hash-locked (`requirements.txt`, `requirements-production.txt`); CI lacks lint/type/coverage thresholds, browser E2E, automated accessibility and performance budgets.

### L-02 — Required baseline and some architecture facts are stale

`CLAUDE_PRG32_CONSTRUCTION_KIT_IMPLEMENTATION.md` is absent. `docs/architecture/current-state.md:11,43,76-104,113` still describes old commits and capabilities (for example WASM/debug/sandbox as absent or planned), weakening traceability.

## Release conclusion

No new exploitable critical issue was confirmed. The recommendation remains **NO-GO** because H-01 and H-02 are mandatory product/release-gate failures, not because the resolved security work is discounted.
