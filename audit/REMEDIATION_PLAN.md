# Remediation plan

| Priority | Area | Work | Acceptance evidence |
|---:|---|---|---|
| 1 | Documentation | Remove stale “no live Store/IdP” and “cloud open” statements. | Documentation/capability consistency. |
| 2 | Cloud validation | Run opt-in suites against dedicated Google and Microsoft accounts; preserve created-file-only cleanup. | Refresh, revoke, conflict, outage and least-privilege tenant evidence. |
| 3 | Delivery | Verify physical PRG32, end-user Qt import and iOS handoff. | Device logs, artifact hashes and reproducible instructions. |
| 4 | Build security | Total disk budget, per-build identity, confined AppArmor and DWARF fuzzing. | Linux escape/resource and real-build suites. |
| 5 | Store lifecycle | Coordinate expiring tokens and duplicate pending id/version behavior with CartridgeStore. | Shared contract v1-compatible migration and live tests. |
| 6 | QA/operations | Screen reader, performance budgets, restore drill, dependency locking and SBOM. | Recorded reports and restoration exercise. |
| 7 | Debugger polish | Breakpoint persistence and honest optimized/inlined presentation. | Advanced fixtures and graceful-unavailable tests. |

Preserve validation, deterministic teaching sources, private build directories, cartridge/debug identity, CSP, ownership, offline use and explicit conflict choices.
