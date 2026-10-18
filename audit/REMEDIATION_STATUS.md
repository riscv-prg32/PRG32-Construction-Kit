# Remediation status

Tracks the audit findings (`FINDINGS.md`) against the remediation brief.
Statuses: implemented and verified, implemented but unverified, partial,
missing, blocked. The audit's recommendation stays **NO-GO** until every
release gate in `CLAUDE_REMEDIATION_BRIEF.md` holds.

| Finding | Phase | Status | Evidence |
| --- | --- | --- | --- |
| H-01 SSRF through publish profiles | 1 | Implemented and verified (automated, local servers only) | ADR-0008; `prg32_construction_kit/store_policy.py`, `publisher.py`; `tests/test_store_egress.py` (94 cases). The audit reproduction (student profile → loopback listener) was run before and after the fix: before, the listener received the upload and its answer was echoed; after, the profile is refused (400) and the seeded loopback profile is refused at publish (`insecure`), with no request reaching the listener. Not exercised against a live public Store. |
| H-02 Publisher role / confirmation | 2 | Implemented and verified (automated; browser check against a local test Store) | ADR-0009; `prg32_construction_kit/publishing.py`, `routes.py` (`_prepare_publish`, `/api/publish/review`, `/api/publish`), `templates/publish.html`, `static/js/publish.js`; `tests/test_publish_authorization.py` (22 cases). Reproduction before: role `user` published a `source_bundle` (200, one upload); after: 403 `not_publisher`, no upload. Draft/update/visibility: not applicable, CartridgeStore has only the upload-for-review endpoint. Not exercised against a live public Store. |
| H-03 Unsandboxed builds | 3 | Implemented and verified (automated in the Linux container, aarch64, with the production security options; x86_64 runs in CI; AppArmor hosts verified only through CI settings) | ADR-0010; `prg32_construction_kit/build_sandbox.py`, `build_guard.py`, `packager.py`, `docker/seccomp-kit.json`, Dockerfile, compose; `tests/test_build_sandbox.py` (19; the 6 escape tests need bubblewrap and skip on macOS). In the container: 77 passed (sandbox, concurrency, handwritten assembly, provenance, all real builds through bubblewrap) and `tools/check_build.py --students 2 --windows 2` built 8 real cartridges concurrently; a container without the profile refuses to start. Known gaps: no total disk quota per build, no per-build UID, AppArmor needs `apparmor=unconfined` today. |
| H-04 Full IDE incomplete | 8–9 | Missing | — |
| M-01 … M-06, L-01, L-02 | 4–11 | Missing / unchanged | — |

## Requirements matrix changes

Conservative: no score changes yet. SEC-01 stays 2 (H-03 still open);
STR-02 stays 1 (H-02 still open). Notes added below the matrix.
