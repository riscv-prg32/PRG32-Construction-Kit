# ADR-0018: One versioned Store contract for the kit and the Cartridge Store

**Status:** Accepted (2026-10-20, priority 3 of the brief after audit `e2d0cef`)

## Context

The kit made Store bundles from its own idea of the manifest and checked them with
its own rules (`publishing.inspect_bundle`). The Cartridge Store has its own rules in
its own code. Nothing proved that the two agree, and a Store refusal reached students
as raw text. There was no live test against a real Store.

## Decision

1. **One machine-readable contract**, `contracts/prg32-store-contract-1.json`: the
   bundle rules, the manifest as a JSON Schema, architectures and aliases, the
   versioning rule, the publish endpoint and its answer, an error catalogue
   (code, status, message pattern, student message, retryable), token behaviour,
   and the kit's cartridge artifact metadata. Its name carries the version; a
   breaking change is a new file (`-2`).
2. **The kit enforces it before upload.** `store_contract.validate_manifest` when a
   bundle is made; `store_contract.validate_bundle` at review, after the kit's own
   checks, refusing with `contract_<code>`. A publish therefore happens completely
   or not at all.
3. **Store answers become contract codes.** `store_contract.classify` turns a status
   and message into `error_code` and `retryable` on the publish result.
4. **The manifest version follows the project:** `0.1.<project version>`.
5. **Generated fixtures** (`tools/build_contract_fixtures.py`, deterministic zips)
   are run through both the kit and the Store's own bundle code; the Store's
   patterns, metadata ABI and architectures must equal the contract's. CI checks out
   CartridgeStore at `store_reference.checked_against` and fails if it is missing.
6. **Live conformance is opt-in and throwaway.** `tests/test_store_live.py` runs only
   with `PRG32_LIVE_STORE=local`, starts a CartridgeStore on loopback with temporary
   data, and allows egress to that address only. There is no mode that targets a
   remote Store: publishing to a real Store stays a human decision through the
   signed review and confirmation (ADR-0008).
7. **Store gaps are recorded, not hidden**: repeated id/version
   (`versioning.duplicate_identity_version`) and tokens without expiry
   (`tokens.expiry`). The live suite asserts the recorded behaviour, so a Store
   change forces a contract update.

## Consequences

- A change to the Store's bundle rules or messages fails the kit's CI until the
  contract is updated; the kit keeps the egress allow-list, SSRF checks and the
  signed review unchanged.
- CartridgeStore can adopt the same file; until then the kit carries it and the
  proposals in `docs/store_contract.md`.
