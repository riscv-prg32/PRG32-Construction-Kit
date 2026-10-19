# Remediation plan

| PR | Owner | Size | Work | Acceptance tests |
|---:|---|:---:|---|---|
| 1 | Docs/release | S | Update phase-4 HEAD wording and preserve browser/container/fixture CI artifacts for independent audits. | Docs/capability consistency plus downloadable evidence. |
| 2 | Identity/security | L | PKCE, issuer+subject, multi-IdP admin config, claims lifecycle/recovery and scoped academic RBAC. | Full mandatory scenario E and cross-issuer/privilege tests. |
| 3 | Accounts/storage | L | Guest policies/IndexedDB/export/eviction; registered quotas, autosave, retention, deprovisioning and conflicts. | Scenarios A/B, migration/rollback and no guest server persistence. |
| 4 | Store/architecture | M | Shared versioned cartridge/bundle contracts and controlled live conformance. | ABI/schema/version/duplicate/update/visibility/recovery matrix. |
| 5 | Cloud | L | Drive and OneDrive with minimum scopes and provider-neutral conflicts. | Expiry/revoke/disconnect/network-loss/concurrent-edit tenant tests. |
| 6 | Platform/security | M | Total build quota, per-build identity where feasible, AppArmor profile, DWARF fuzz limits and x86_64/aarch64 evidence. | Sandbox/debug escape and resource suites plus real three-mode builds. |
| 7 | Debugger/UX | M | Improve optimized/inlined-code presentation and breakpoint persistence/enable controls without guessing unavailable values. | Advanced optimized C fixtures and graceful fallback tests. |
| 8 | Delivery/QA | M | Hardware, Qt and verified iOS workflows; screen reader, performance budgets, backup/restore, hash locks/SBOM. | Mandatory C/G evidence, device hashes/logs and restore drill. |

Do not start cloud work before identity and conflict semantics stabilize. Never weaken cartridge/debug identity checks or expose debug ELFs.
