# Architecture review

The core pipeline remains sound: browser editors feed authenticated Flask APIs; Blocks JSON becomes validated IR; deterministic C or RV32IM assembly is built in a private build directory; artifacts are executed by the pinned PRG32 core or reviewed before Store publication.

Phases 5–6 add two coherent boundaries. Identity providers are configuration records whose secrets remain environment/file references; verified `(issuer, subject)` identities attach to accounts only through sign-in or an explicit owner-controlled link. Global Store-compatible roles remain separate from kit academic roles and class membership. Guest storage remains entirely browser-side, while registered project versions use conditional database updates. Quotas and retention account for database and artifact/build data without sharing build folders.

Trust boundaries remain layered: strict same-origin/CSP browser code; authenticated and scope-checked APIs; owner/class authorization; validator-controlled generation; sandboxed builds; owner-scoped debug JSON; controlled Store egress. `sso_protocol.py` remains identical to CartridgeStore.

Cross-repository revisions: Kit `e2d0cef834bbe75e1fd3fd5c2ea69ce7f1560954`; PRG32 `679dfb58783bd007125de9ca0b75eaa077908739`; PRG32-QT `f6d80addf49d0512c2e4390251a81d797a35b157`; CartridgeStore `820f74bfe9364c8727db92cb0f15f3b9dd85feab`.

Remaining architectural gaps are provider-neutral cloud storage, one shared versioned Store/cartridge contract, operational sandbox quotas/identity, and end-to-end delivery adapters. External IdP lifecycle integration is not yet demonstrated.
