# Evidence index

## Repositories inspected

| Repository | Branch/state | HEAD | Notes |
|---|---|---|---|
| PRG32-Construction-Kit | `development`, equals `origin/development` | `2ea8616f04e1b134d23e786acba2e536e6eef1e7` | Includes audit commit `3f96903` and H-01 remediation. Pre-existing untracked `.claude/` and `CLAUDE_PRG32_QUALITY_IMPROVEMENT_ROUND.md`; untouched. |
| PRG32 | `main`, equals `origin/main` | `679dfb58783bd007125de9ca0b75eaa077908739` | Pre-existing untracked `.DS_Store` and `docs/pcb/`; untouched. |
| PRG32-QT | `main`, equals `origin/main` | `f6d80addf49d0512c2e4390251a81d797a35b157` | Matches WASM build record; pre-existing `.DS_Store`/`.idea`; untouched. |
| CartridgeStore | `main`, local status reports behind 1 | `820f74bfe9364c8727db92cb0f15f3b9dd85feab` | `sso_protocol.py` identical; remote was not fetched. |

Repository URLs were read from Git remotes and match the audit brief. PRG32-iOS was not available locally and no interface is claimed.

## Primary source evidence

- Product status/gaps: `docs/implementation-status.md:6-16,52-64`; `docs/traceability.md:30-58`.
- IDE UI: `templates/editor.html:63-140`; `templates/base.html:12-13,60-61`.
- Ownership/public redaction: `prg32_construction_kit/routes.py:72-187`.
- Build execution/isolation/provenance: `prg32_construction_kit/packager.py:75-161,164-260`.
- Source safety: `prg32_construction_kit/source_project.py:64-98,107-191`.
- Publish/SSRF: `prg32_construction_kit/publisher.py:10-30`; `routes.py:974-1014`; `static/js/publish.js:41-56`.
- Store egress remediation: `prg32_construction_kit/store_policy.py`; `publisher.py`; `routes.py:120-124,1008-1029`; `tests/test_store_egress.py`; `docs/adr/0008-store-egress-policy.md`.
- OIDC/RBAC: `prg32_construction_kit/auth_adapters.py:41-81`; `auth.py:49-55`.
- Auth guard: `prg32_construction_kit/auth.py:596-626`.
- WASM provenance: `static/wasm/BUILD.json`; `wasm/prg32_core_api.cpp:221-542`.
- Differential tests: `tests/test_wasm_runtime.py:96-163,179-234,336-380`.
- Service worker: `static/service-worker.js:1-40`.
- CI: `.github/workflows/ci.yml` (Python 3.11/3.12, WASM rebuild/golden tests, dependency review, toolchain container and real cartridges).

## Executed outputs

- Reassessment JUnit files were written outside the repository to `/tmp/prg32-kit-reaudit-pytest.xml` and `/tmp/prg32-kit-reaudit-core.xml`; they may be ephemeral. Counts and exact environment failures are preserved in `audit/TEST_REPORT.md`.
- `tests/test_store_egress.py`: 94 passed with loopback sockets permitted.
- WASM SHA-256:
  - `static/wasm/prg32-core.js`: `5896c2100b666a4ae0b4f21519764380f360f9ae80180e38b88219e9f83c59fd`
  - `static/wasm/prg32-core.wasm`: `3ba378fb805cf9bfcfabe3c0334df7890719139dfed46c560ac137c045262b21`
- No screenshots, newly built cartridges, hardware logs, iOS artifacts, or publication records were produced.

## Missing evidence

1. `CLAUDE_PRG32_CONSTRUCTION_KIT_IMPLEMENTATION.md`.
2. Clean exact-Emscripten reproducible rebuild in a writable cache/container.
3. Locally executed real Blocks/C/assembly cartridge builds and their ELF/header/ABI inspection.
4. Hardware transfer/launch evidence and integrity handshake.
5. PRG32-iOS source, documented import contract, and handoff execution.
6. Live IdP tests for PKCE/state/nonce/JWKS/issuer/audience/MFA/logout/multi-provider lifecycle.
7. Drive and OneDrive implementation/tenant tests.
8. Live CartridgeStore draft/publish/update/visibility/error-recovery tests; no public artifact was published.
9. Guest-policy/IndexedDB behavior.
10. Browser E2E, screen-reader/keyboard, cold-offline, memory, latency and performance measurements.
11. Coverage report, SBOM/license inventory, restore drill, TLS/metrics operational evidence.
