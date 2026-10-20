# Architecture review

The validated educational pipeline remains intact. ADR-0018 adds a versioned Store contract validated before upload and checked with deterministic fixtures against the referenced CartridgeStore implementation. ADR-0019 adds optional signed-in cloud storage behind one provider interface; both cloud implementations reuse local project versions and archive determinism rather than creating another project model.

Cloud credentials remain server-side and encrypted, authorization uses PKCE and single-use state, providers are limited to fixed HTTPS hosts, and replacement requires explicit expected local/cloud revisions. Guests and ordinary offline classroom work remain independent of cloud accounts. Store live tests can target only a disposable loopback Store.

Current revisions: Kit `fea31c02348af2adc28e96c3795d38ae18a8f8e9`; PRG32 `679dfb58783bd007125de9ca0b75eaa077908739`; PRG32-QT `f6d80addf49d0512c2e4390251a81d797a35b157`; CartridgeStore `820f74bfe9364c8727db92cb0f15f3b9dd85feab`.

Remaining architecture gaps are externally verified cloud adapters, delivery integrations, stronger host build isolation and upstream resolution of the Store lifecycle gaps recorded by the contract.
