# Security review

## Overall

No new critical exploit was confirmed. The language services and source debugger were designed with fail-closed boundaries and retain server-side validation and existing execution semantics.

## Language services

The generated index is static/browser-only, records input hashes and ABI provenance, suggests only portable ABI functions and validator-approved constructs, and is checked byte-for-byte. Live diagnostics only add feedback; they cannot bypass server validation. Compiler messages are normalized to remove host paths. Corpus tests compare client/server acceptance for unsafe and generated sources.

## Debug information

Debug wrappers are per-build and operate inside the existing sandbox. A retained ELF must match the PRG32 cartridge's loadable image exactly. The API serves bounded JSON maps/source, never the ELF, and requires readable ownership of cartridge, build and artifacts. File paths are reduced to basenames; damaged/oversized/unmatched data becomes unavailable. Source maps are hash-bound to the served source. Browser expression evaluation uses the constrained debugger evaluator rather than arbitrary JavaScript execution.

Residual risks:

- wrapper behavior depends on upstream tool naming/invocation;
- real Linux sandbox/debug builds were not rerun here;
- no total build-directory quota or per-build UID;
- complex DWARF inputs deserve continued fuzz/limit testing;
- source itself is intentionally shown to its owner, while shared-project policy must remain consistent.

## Identity, storage and external systems

OIDC remains below the academic profile and guest/cloud storage is absent. Registered quotas/retention/deprovisioning are missing. Store tokens remain reversibly stored. These are the largest remaining deployment-security and privacy gaps. Browser CSP, dependency vendoring, authentication, ownership, throttling, Store egress and publish confirmation remain in place.
