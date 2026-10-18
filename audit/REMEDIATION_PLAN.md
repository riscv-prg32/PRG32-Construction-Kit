# Remediation plan

Order reflects release risk and dependency flow. Complexity: S/M/L.

| PR | Owner role | Size | Work | Prerequisites | Acceptance tests |
|---:|---|---:|---|---|---|
| 1 | Security/backend | M | Harden Store egress: admin allow-list, HTTPS-only, DNS/IP/redirect validation, response cap, timeouts. | Deployment Store origins. | Loopback, RFC1918, link-local, IPv6, rebinding/redirect and credential-URL tests all rejected; approved Store succeeds. |
| 2 | Auth/backend + UX | M | Enforce publisher scope; binary bundle preflight; draft/review/explicit-confirm/update/error-recovery workflow. | PR 1, shared Store contract. | Ordinary student receives 403; publisher sees immutable hash/version/visibility review; source-only rejected; retry is idempotent. |
| 3 | Platform/security | L | Execute each build in disposable no-network non-root sandbox with read-only SDK and cgroup/seccomp limits. | Container/runtime choice. | Escape, fork/memory/disk/CPU bombs, file-read and network attempts contained; normal three-mode builds pass concurrently. |
| 4 | Architecture/Store | M | Extract versioned shared cartridge/bundle schema and conformance fixtures from PRG32/Store; remove duplicated header constants where feasible. | Upstream agreement. | Stale ABI/hash/schema rejected; duplicate/version/visibility error codes match Store. |
| 5 | Frontend/platform | S | Vendor jQuery/Bootstrap/icons/Blockly, add CSP/SRI strategy, update service-worker cache. | License/provenance review. | Cold and warm offline PWA start/edit; no third-party network; cached-files-only invariant retained. |
| 6 | Identity/security | L | Implement ADR-0007: PKCE, issuer+subject, multiple IdPs, admin config/claim mapping, disabled/group lifecycle, recovery. | IdP test tenants/fixtures. | Full scenario E matrix including JWKS rotation, state/nonce/aud/iss, collisions and lockout recovery. |
| 7 | Accounts/backend | L | Guest policies A/B/C with IndexedDB, export/eviction; registered quotas, retention, autosave and conflict API. | Policy decisions. | Scenario A/B matrix, no guest server persistence, quota and concurrent-conflict tests. |
| 8 | IDE frontend | L | Responsive IDE shell: tree, tabs/panels, palette, keyboard/focus model; vendored Monaco. | PR 5. | IDE-01 accessibility/keyboard/mobile E2E suite; Blockly remains editable. |
| 9 | Language tooling | L | Deterministic C/assembly completion, diagnostics/navigation and SDK/ABI awareness. | PR 4 and 8. | Safe fixtures receive exact diagnostics/completions; unknown/unsafe APIs rejected; offline works. |
| 10 | Debug/toolchain | L | Debug profile with DWARF, C variables/call stack/watches; deterministic block/source/address maps; compressed-instruction fixture. | PR 4 and 9. | DBG-02/05/06 checkpoints equal Qt; graceful address-only fallback. |
| 11 | Cloud integrations | L | Drive then OneDrive behind provider interfaces; minimum scopes, refresh/revoke, conflicts. | PR 6/7. | Token expiry/revoke/network-loss/concurrent-edit tests in provider sandboxes. |
| 12 | Delivery/QA | M | Hardware transfer, Qt import and verified iOS contract/handoff with hashes; browser E2E, a11y/performance budgets, backups/restore and SBOM. | Device/app access and preceding PRs. | Mandatory scenarios C/D/G, restore drill, signed release evidence. |

Do not combine PRs 1-3: each needs focused security review and rollback. Do not begin cloud work before identity/storage semantics stabilize. Continue preserving generated C and assembly as inspectable teaching artifacts throughout PRs 8-10.
