# Remediation plan

| Priority | Area | Work | Acceptance evidence |
|---:|---|---|---|
| 1 | Evidence | Replace “this change”/stale guest-policy wording; retain immutable CI artifacts. | Documentation consistency and commit-specific records. |
| 2 | Identity integration | Exercise a real institutional IdP; define SCIM/provisioning and logout lifecycle where required. | Tenant PKCE, rotation, deactivation, collision and recovery matrix. |
| 3 | Store contract | Share/version cartridge and publication schemas; add controlled live conformance. | Duplicate/version/update/visibility/failure matrix. |
| 4 | Cloud | Add provider-neutral Drive and OneDrive adapters with least-privilege scopes and deterministic conflicts. | Revoke, expiry, disconnect, outage and concurrent-edit tests. |
| 5 | Platform security | Enforce total disk limits, per-build identity where feasible, AppArmor and DWARF fuzz limits. | Linux escape/resource suites and real builds. |
| 6 | Delivery/QA | Verify hardware, Qt import and iOS; screen reader, performance, restore, dependency locks and SBOM. | Device logs/hashes, accessibility report and restore drill. |
| 7 | Debugger polish | Improve optimized/inlined presentation and breakpoint persistence without guessing values. | Advanced fixtures and graceful-unavailable tests. |

Never weaken validation, cartridge/debug byte identity, private build directories, CSP, ownership, or the no-debug-ELF API boundary.
