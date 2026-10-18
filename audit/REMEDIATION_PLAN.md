# Remediation plan

| PR | Owner | Size | Work | Acceptance tests |
|---:|---|:---:|---|---|
| 1 | QA/CI | S | Add `tests/test_ide_browser.py` to the browser CI job; publish results. | All 10 Chrome tests run on every push/PR. |
| 2 | Docs/architecture | S | Refresh `current-state.md`, SHAs, implementation test history and capability wording after phases 1–2. | Capability/doc consistency test catches stale claims. |
| 3 | IDE/tooling | L | Offline deterministic C and RISC-V completion, hover/navigation, SDK/ABI awareness and exact diagnostics. | Exact fixture outputs; unsafe APIs/directives rejected; no host paths. |
| 4 | Debug/toolchain | L | DWARF profile, locals/call stack/watches, CSR/stack, source breakpoints, compressed-step fixture and block→IR→source→address maps. | Full mandatory scenario D with Qt snapshots and deterministic fallback. |
| 5 | Identity/security | L | PKCE, issuer+subject, multi-IdP admin config, claims/lifecycle/recovery and scoped academic RBAC. | Full mandatory scenario E and privilege-boundary tests. |
| 6 | Accounts/storage | L | Configurable guest policies/IndexedDB/export/eviction plus quotas, autosave, retention and conflict API. | Mandatory scenarios A/B; no guest server persistence; migration/rollback tests. |
| 7 | Store/architecture | M | Shared versioned cartridge/bundle schema and controlled live conformance. | ABI/schema/version/duplicate/update/visibility/recovery matrix. |
| 8 | Cloud | L | Drive and OneDrive with minimum scopes and provider-neutral conflicts. | Expiry/revoke/disconnect/network-loss/concurrent-edit tenant tests. |
| 9 | Platform/security | M | Total build quota, per-build identity where feasible, AppArmor profile and cross-architecture sandbox evidence. | Escape/resource tests on x86_64/aarch64; real three-mode builds. |
| 10 | Delivery/QA | M | Hardware, Qt and verified iOS handoffs; performance budgets; screen reader; backup/restore; hash locks/SBOM. | Mandatory C/G evidence, device hashes/logs and restore drill. |

Keep generated C/assembly visible and deterministic. Do not begin cloud work before identity and conflict semantics stabilize.
