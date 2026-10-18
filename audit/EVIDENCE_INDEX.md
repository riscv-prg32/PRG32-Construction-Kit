# Evidence index

## Repositories inspected

| Repository | Branch | HEAD | Working tree |
|---|---|---|---|
| PRG32-Construction-Kit | `development` | `6b7aac93554bcdbbeeb0c7b80fcad576b1a9bea6` | Pre-existing untracked `.claude/` and `CLAUDE_PRG32_QUALITY_IMPROVEMENT_ROUND.md`; untouched. Audit reports updated. |
| PRG32 | `main` | `679dfb58783bd007125de9ca0b75eaa077908739` | Pre-existing `.DS_Store` and `docs/pcb/`; untouched. |
| PRG32-QT | `main` | `f6d80addf49d0512c2e4390251a81d797a35b157` | Pre-existing `.DS_Store`/`.idea`; untouched. |
| CartridgeStore | `main` | `820f74bfe9364c8727db92cb0f15f3b9dd85feab` | Clean at inspection. |

Remotes match the audit brief. No network fetch was performed, so these are local checkout states. PRG32-iOS was unavailable.

## Primary evidence

- Editor/IDE gap: `templates/editor.html:63-140`; `docs/traceability.md:25-32`.
- Current declared gaps: `docs/implementation-status.md:52-64`; `docs/traceability.md:49-59`.
- Project format/history: `project_format.py`; `routes.py:311-564`; `tests/test_project_format.py`; `tests/test_project_revisions.py`; `tests/test_restore_relationships.py`.
- Build/sandbox/provenance: `build_sandbox.py`; `build_guard.py`; `packager.py:115-260`; `tests/test_build_sandbox.py`; ADR-0010.
- Publish policy/review: `store_policy.py`; `publisher.py`; `publishing.py`; `routes.py:990-1125`; `tests/test_store_egress.py`; `tests/test_publish_authorization.py`; ADR-0008/0009.
- OIDC/RBAC: `auth_adapters.py:41-81`; `auth.py:49-55`.
- WASM/runtime/debug: `static/wasm/BUILD.json`; `wasm/prg32_core_api.cpp`; `tests/test_wasm_runtime.py`; `static/js/prg32_debugger.js`.
- PWA/offline: `templates/base.html:12-13,60-61`; `templates/editor.html:137`; `static/service-worker.js:1-40`.
- CI/container: `.github/workflows/tests.yml`; `Dockerfile`; `docker-compose.yml`.

## Executed evidence

- Syntax checks: Python and all shipped JS passed.
- Targeted publisher/sandbox: 34 passed, 7 platform skips.
- WASM: 29 passed, 1 toolchain skip; exact rebuild blocked at Emscripten cache write.
- `sso_protocol.py` SHA-256 (both repos): `611d881247c2ca8bd074320a08e994aaac1db43844dcf7f6e11abd0ae249a593`.
- WASM SHA-256: `3ba378fb805cf9bfcfabe3c0334df7890719139dfed46c560ac137c045262b21`.

## Exact missing evidence

1. Named `CLAUDE_PRG32_CONSTRUCTION_KIT_IMPLEMENTATION.md` baseline.
2. Clean exact-Emscripten byte rebuild with writable cache.
3. Independently executed Linux bubblewrap/container escape suite and real three-mode builds.
4. Hardware transfer/launch with integrity evidence.
5. PRG32-iOS source/contract and executed handoff.
6. External IdP matrix: PKCE/state/nonce/JWKS/issuer/audience/logout/collisions/lifecycle/recovery.
7. Guest policy/IndexedDB behavior and Drive/OneDrive tenant tests.
8. Live Store draft/review/version/update/visibility/error-recovery conformance.
9. Browser E2E, cold-offline, accessibility, memory and latency results.
10. Coverage report, SBOM/license inventory, TLS/metrics proof and backup/restore drill.
