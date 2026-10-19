# Executive summary

Audit date: 2026-10-19 (Europe/Rome)

Audited revision: `ide/refine-after-5dd98a9` at `e2d0cef834bbe75e1fd3fd5c2ea69ce7f1560954`

Recommendation: **NO-GO for the complete Full IDE scope; CONDITIONAL GO for a bounded classroom deployment**

Refinement phases 5–6 close the previous High account/identity/guest-policy finding and the registered-storage finding. OIDC now uses Authorization Code + PKCE, verified issuer/subject identities and explicit account linking. Multiple administrator-configured providers, academic/class roles, scoped tokens, session epochs and deprovisioning are implemented. Guest projects stay in IndexedDB and support export/import and safe account migration. Registered storage now has atomic conflict detection, autosave, quotas and retention.

The new controls passed unit, authorization, browser and storage scenarios. The SSO score remains below full because no external institutional IdP, provisioning system or IdP-initiated logout was exercised. The complete product remains NO-GO because Drive/OneDrive are absent, Store conformance is local rather than shared/live, and hardware/Qt/iOS delivery lacks end-to-end evidence.

## Executed evidence

- Feasible broad suite excluding Store egress and exact WASM rebuild: **710 passed, 42 skipped, 1 deselected**.
- Required Chrome suites with `PRG32_REQUIRE_BROWSER=1`: **74 passed**, no skips.
- Store-egress suite: **94 passed**.
- Python and JavaScript syntax, service-worker lock, capability rendering and language-index reproducibility: passed.
- Capability/document consistency after reassessment: passed.
- `sso_protocol.py` is byte-identical to the checked-out CartridgeStore copy.

## Limitations

No external institutional IdP, SCIM feed, Drive/OneDrive tenant, live public Store, physical PRG32 hardware, iOS target, exact Emscripten rebuild, local real cartridge build or Linux bubblewrap run was used. Browser behavior was independently executed with Chromium. Toolchain- and Linux-only tests skipped cleanly.

Scored coverage is **93/132 (70.5%)** across all 33 requirements.
