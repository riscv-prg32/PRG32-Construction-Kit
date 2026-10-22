# Requirements matrix

Scores: 0 missing, 1 prototype, 2 partial, 3 implemented/tested with an evidence gap, 4 reference-verified.

| ID | Score | State | Audit observation |
|---|---:|---|---|
| IDE-01 | 3 | Implemented/tested | Blockly/C/assembly modes and conversion are covered. |
| IDE-02 | 3 | Implemented/tested | Monaco shell, accessibility and responsive browser flows pass. |
| IDE-03 | 4 | Reference-verified | Portable-ABI completion/navigation and validator ranges are backed by the real PRG32 compiler after every validated save. |
| IDE-04 | 4 | Reference-verified | RV32IMC/Zicsr, ABI/labels/navigation and safe validation are backed by the real PRG32 assembler/compiler after every save. |
| PRJ-01 | 3 | Implemented/tested | Deterministic project model, revisions and archive/import are covered. |
| BLD-01 | 4 | Reference-verified | Retained Docker evidence rebuilds Blocks-C, Blocks-assembly, Advanced C and handwritten assembly for both targets; hashes match macOS builds. |
| BLD-02 | 3 | Implemented/tested | Isolation/provenance/diagnostics/debug identity; Linux rerun unavailable. |
| WASM-01 | 4 | Reference-verified | Committed browser core and golden execution tests. |
| WASM-02 | 4 | Reference-verified | Browser graphics/input/timing/offline evidence remains strong; its firmware-engine PCM is now compared with retained real-firmware QEMU output. |
| AUD-01 | 4 | Reference-verified | Eight simultaneous SID-like voices and independent ADSR/waveform/volume/pan pass native/WASM tests and retained real-firmware QEMU sample comparison. |
| AUD-02 | 3 | Implemented/tested | Native/WASM PCM is deterministic and a tested Qt patch is bit-identical; canonical Qt remains unpatched, QEMU event timing differs and no console capture exists. |
| AUD-03 | 4 | Reference-verified | Real-browser CRUD/keyboard/archive/compile paths pass; a real-toolchain AudioStudio cartridge and its AUD0 data run through retained firmware/QEMU evidence. |
| AUD-04 | 2 | Partial | Kit UI/index/generation refuse buzzer and legacy cartridges are silent, but the canonical PRG32 SDK still lists buzzer in its portable ABI. |
| DBG-01 | 4 | Reference-verified | Address debugger and execution controls covered. |
| DBG-02 | 4 | Reference-verified | Breakpoints and compressed stepping covered. |
| DBG-03 | 3 | Implemented/tested | Registers, memory, CSR and stack views; physical target not used. |
| DBG-04 | 3 | Implemented/tested | Accessible debugger browser UI covered. |
| DBG-05 | 4 | Reference-verified | Source/block maps, locals, watches and safe fallback covered. |
| DBG-06 | 4 | Reference-verified | Browser/native state agreement covered. |
| ACC-01 | 4 | Reference-verified | IndexedDB guest projects, migration, capacity, import/export and local-only policy pass browser scenarios. |
| ACC-02 | 4 | Reference-verified | Ownership, atomic conflicts, autosave, quotas, retention and deprovisioning are covered. |
| SSO-01 | 4 | Reference-verified | PKCE and issuer+subject pass signed fake-provider tests and nine live Keycloak scenarios. |
| SSO-02 | 4 | Reference-verified | Multi-IdP, role claims, collision/linking, recovery, deactivation and documented local logout pass live/provider tests. |
| SSO-03 | 4 | Reference-verified | Academic/class RBAC and scoped token denial paths are covered. |
| SSO-04 | 3 | Implemented/tested with regression | Sign-on and tickets work, but the fresh adjacent-repository test fails because CartridgeStore returns a generated `player-*` username instead of the Kit's shared username. |
| CLD-01 | 3 | Implemented/tested | Drive provider, least privilege, encrypted tokens and conflicts pass fake/browser tests; no real Google account run. |
| CLD-02 | 3 | Implemented/tested | OneDrive provider, app-folder scope, encrypted tokens and conflicts pass fake/browser tests; no real Microsoft account run. |
| STR-01 | 4 | Reference-verified | Versioned contract and deterministic fixtures pass against CartridgeStore code and a throwaway live Store. |
| STR-02 | 3 | Implemented/tested | Store egress and confirmation boundaries pass 94 tests. |
| DEP-01 | 0 | Missing | Physical PRG32 transfer/launch not verified. |
| DEP-02 | 3 | Implemented/tested | Canonical PRG32-QT stored, launched and drew five hashed Kit cartridges through its web API; desktop Import-menu workflow remains untested. |
| DEP-03 | 0 | Missing | iOS handoff not verified. |
| SEC-01 | 3 | Implemented/tested | SSRF/sandbox boundaries tested; per-build UID/AppArmor/disk limit gaps remain. |
| SEC-02 | 4 | Reference-verified | Credential/session controls, retention, auditing, throttling, CSP, hash-locked dependencies and SBOM are covered. |
| GDPR-01 | 3 | Implemented/tested; operational gate open | Generated field-level ROPA, notices, complete export/erasure/restriction, backup re-erasure, processor/transfer templates and technical breach rehearsal pass meaningful tests. Actual controller/legal bases, Member-State rules, DPIA, DPO/counsel review, contracts/transfers and staffed exercise remain explicitly open release blockers. |
| OPS-01 | 4 | Reference-verified | CI/deployment/migrations and a tested backup/restore drill are documented and exercised. |
| DOC-01 | 4 | Reference-verified | Capability IDs, generated status, traceability and commit-named milestones pass consistency tests with no ambiguous “this change” rows. |
| DOC-02 | 4 | Reference-verified | Current README/architecture, generated diagrams, synthetic screenshots, visual manifest, human review records and CI checks for links/images/alt text/orphans/names/IDs/freshness all pass. |
| QLT-01 | 3 | Implemented/tested with regression | Broad coverage and quality gates remain strong, but the fresh feasible suite has one reproducible adjacent-repository SSO contract failure; browser rerun was unavailable locally. |

Domain totals: IDE 14/16; Project 3/4; Build 7/8; WASM 8/8; Audio 13/16; Debug 22/24; Accounts 8/8; SSO 15/16; Cloud 6/8; Store 7/8; Delivery 3/12; Security 7/8; GDPR 3/4; Operations 4/4; Documentation 8/8; Quality 3/4.

**Total: 131/156 (84.0%).**
