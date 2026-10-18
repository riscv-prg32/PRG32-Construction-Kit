# Remediation plan

Complexity: S/M/L. Completed security phases remain listed because they are prerequisites and need release evidence.

| PR | Owner | Size | Work | Acceptance evidence |
|---:|---|:---:|---|---|
| 1 | Security/platform | S | Release-evidence pass for completed SSRF, publish authorization and sandbox controls on Linux x86_64/aarch64; close AppArmor documentation drift. | Full Store-egress suite; bubblewrap escape/resource tests; three-mode concurrent real builds; refusal without sandbox. |
| 2 | Architecture/docs | S | Replace stale current-state facts; commit or formally supersede the missing approved design baseline. | Traceability SHAs/capabilities match source; documentation test. |
| 3 | Frontend/platform | M | Vendor Bootstrap/jQuery/icons/Blockly, add CSP, update service-worker cache. | Cold/warm offline authoring; no third-party requests; cached-files-only invariant. |
| 4 | IDE frontend | L | Responsive shell: tree, tabs/panels, palette, keyboard/focus model and vendored Monaco. | IDE-01/03/04 browser E2E, keyboard, screen-reader and mobile checks. |
| 5 | Language/toolchain | L | Deterministic C/assembly completion, SDK navigation and diagnostics. | Offline fixture suite with exact safe/unsafe diagnostics and completion results. |
| 6 | Debug/toolchain | L | DWARF profile, locals/call stack/watches, source breakpoints and deterministic Blockly maps. | Full mandatory scenario D including compressed instruction and Qt snapshot parity. |
| 7 | Identity/security | L | ADR-0007: PKCE, issuer+subject, multi-IdP admin config, claims, lifecycle and recovery; course-scoped roles. | Full scenario E negative matrix and publisher boundaries. |
| 8 | Accounts/backend | L | Guest policy/IndexedDB/export/eviction; registered quotas, retention, autosave and conflicts. | Scenarios A/B; no unintended guest persistence; quota/conflict/deprovision tests. |
| 9 | Architecture/Store | M | Shared versioned cartridge/bundle schema and live Store sandbox conformance. | Stale ABI/schema, duplicate/version/visibility, interrupted upload and update behavior. |
| 10 | Cloud | L | Drive then OneDrive with minimum scopes and provider-neutral conflict model. | Expiry/revoke/network-loss/concurrent-edit tenant tests. |
| 11 | Delivery/QA | M | Physical board, Qt and verified iOS handoffs; browser performance/a11y; backup/restore; SBOM/hash locks. | Scenarios C/G, device logs/hashes, iOS contract evidence, restore drill and quality gates. |

Keep generated C and assembly visible and deterministic throughout PRs 4–6. Do not begin cloud integration before identity and project-conflict semantics stabilize.
