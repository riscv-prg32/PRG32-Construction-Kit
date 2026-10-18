# Findings

## Resolved in refinement phases 0–2

- **IDE shell prototype gap:** closed for shell scope. Chrome demonstrated tree, tabs, panels, palette, keyboard-only editing/save/build command, responsive layout and axe checks.
- **Offline/CDN/CSP gap:** closed. Runtime libraries are locally vendored, strict CSP is active, the service worker caches static files only, and Chrome demonstrated cold-offline Blockly and real-cartridge execution.
- **Missing baseline/traceability:** substantially closed by ADR-0011, committed briefs and machine-checked `docs/capabilities.json`.
- Prior Store SSRF, publish authorization and production sandbox findings remain closed.

## Critical

No exploitable critical issue was confirmed.

## High

### H-01 — Mandatory source-level debugger functionality is missing

- Evidence: no DWARF locals, call stack, watches, conditional/source breakpoints, CSR/stack view, or Blockly active-block mapping (`docs/implementation-status.md:61-63`; `docs/capabilities.md:20-24`).
- Reproduction: load a cartridge in Player; machine-address debugging works, but mandatory scenario D's source/block state cannot be performed.
- Impact: explicit NO-GO release gate for mandatory debugger behavior.
- Remedy: deterministic block→IR→source→address artifacts, debug/DWARF profile, source breakpoints, variables/call stack/watches and graceful fallback.

### H-02 — Academic identity, scoped roles and guest policy remain incomplete

- Evidence: one environment OIDC provider without explicit PKCE or issuer+subject identity; guest IndexedDB/policy is absent (`docs/capabilities.md:25-30`).
- Reproduction: mandatory scenarios A/E cannot be run as specified.
- Impact: incomplete tenant isolation/lifecycle model for institutional classroom deployment.
- Remedy: ADR-0007 implementation, scoped academic RBAC, guest policies and full negative IdP matrix.

## Medium

### M-01 — Monaco language intelligence is incomplete

C and assembly syntax/editing/markers work, but completion, hover, navigation, SDK declarations and register/instruction/ABI completion do not (`docs/capabilities.md:12-13`). This keeps IDE-03/04 partial.

### M-02 — Google Drive and OneDrive are absent

No implementation or provider test environment exists; token lifecycle, scopes, revocation, conflicts and network loss cannot be assessed.

### M-03 — Registered storage lacks quotas and conflict semantics

Autosave, search, quotas, retention/deprovisioning and robust concurrent-edit recovery remain absent (`docs/implementation-status.md:55-56`).

### M-04 — Delivery targets remain unverified

No physical PRG32 transfer/launch, end-user PRG32-QT import, or verified iOS handoff was executed.

### M-05 — Store validation is not a shared live contract

The kit locally checks manifest/magic/hashes, but there is no shared versioned schema or live duplicate/version/update/visibility conformance evidence.

### M-06 — Build-sandbox operational gaps remain

No total build-folder quota or per-build UID; AppArmor hosts require an exception. Linux escape tests were not rerun in this audit environment.

### M-07 — IDE browser regression suite is omitted from CI

- Evidence: `.github/workflows/tests.yml:169` runs only `test_browser_offline.py` and `test_frontend_offline.py`, not `test_ide_browser.py`.
- Reproduction: inspect the browser job command.
- Impact: keyboard, Monaco, responsive and axe regressions can merge despite passing locally.
- Remedy: add `tests/test_ide_browser.py` to the browser job and publish its result.

## Low

### L-01 — Current-state architecture documentation contradicts shipped code

`docs/architecture/current-state.md:55-60` still says the IDE shell, Monaco and offline app shell are not implemented, despite phases 1–2. Its Construction Kit SHA at line 13 is also stale. Update it in the same PR as capability changes.

### L-02 — Quality/reproducibility gates remain incomplete

No lint/type/coverage threshold, performance budget, dependency hash lock, complete SBOM/security inventory, or real screen-reader session exists.

### L-03 — Earlier audit totals used the wrong denominator

The required matrix contains 33 rows, not 32. Its denominator is 132 points. This edition corrects the total without changing any individual requirement definition.

## Release conclusion

Recommendation remains **NO-GO**. The IDE shell/offline work is implemented and demonstrated, but H-01 is a mandatory debugger release-gate failure and H-02 blocks the required classroom identity/guest scenarios.
