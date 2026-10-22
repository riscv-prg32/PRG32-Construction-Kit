# Handoff after the audit of bb2b062

This answers `audit/CLAUDE_REFINEMENT_AFTER_AUDIT_BB2B062.md` (131/156, NO-GO). Scores are
the auditor's; `docs/capabilities.json` was not changed by this work.

**Boundary.** Hard gate 1 (the deployment's GDPR decisions) is the controller's, with its DPO
or counsel. Nothing here fills those decisions in, and nothing claims GDPR certification or
legal compliance. **The deployment stays NO-GO.** Synthetic people only, everywhere.

## Commits

| Repository | Commit | Note |
|---|---|---|
| PRG32-Construction-Kit | `557ab64` | the auditor's update (audit files, brief) |
| PRG32-Construction-Kit | this commit | hard gate 2: shared identity contract, tests, docs, Store patch |
| CartridgeStore | `4a3138b` (`main`) | canonical head; needs `docs/upstream/cartridge-store-shared-identity.patch` |
| CartridgeStore | `820f74b` | the kit's CI pin (`contracts/prg32-store-contract-1.json`), unchanged |
| PRG32 SDK | `679dfb5` | pinned (`static/wasm/BUILD.json`); PRs #45, #46 open, not merged |
| PRG32-QT | `f6d80ad` | pinned; PR #1 open, not merged |

The sibling working trees were not edited. The Store change was made and tested in a
clone and is delivered as a patch (`docs/upstream/README.md` §6.1).

## Hard gate 1: deployment privacy decisions (not done here)

`docs/privacy/decisions.md` D-0 to D-10 are still **open**. Each needs the deploying
school or operator, with its DPO or qualified counsel: the named controller, contact and
DPO; legal bases and national rules; the DPIA; retention; named processors, roles and
regions; Article 28 and transfer terms; the choice on optional services for minors; breach
contacts and a staffed tabletop; and the dated review recorded in the privacy changelog.
None of these are facts this repository can supply.

## Hard gate 2: shared identity (done, pending the Store merge)

**Model, chosen by the project owner (raffmont, 2026-10-22): shared username, private
handle.**

- The account **username** is the shared sign-in name. The Store returns it only to its
  owner (`/api/me`); the kit as before.
- The Store's **public handle** is the only name other people see; it is pseudonymous and
  never made from the username or email for an SSO import.
- Accounts are matched by **email**, never by username or handle. A username already used
  by another Store account is never joined: the kit's account gets its own Store account
  named by its email.
- Unchanged: `sso_protocol.py` (byte-identical, ABI unchanged), single-use tickets,
  issuer+subject identities for school sign-in, roles, scopes, and the kit's publisher check.

**Cause of the audit's failure.** CartridgeStore `4a3138b` made `/api/me`'s `username` the
public handle, redirected `/api/me` (and every `/api/` call) to its notice page until
acknowledged, and answered an unsigned API `POST` with a CSRF `400`. The patch fixes all
three in the Store; the kit's live tests now sign in on the Store's forms as a browser does
(CSRF token from the page, the notice acknowledged once) instead of relying on a Store
without those protections.

**New tests.**

| Where | Test | Proves |
|---|---|---|
| kit | `test_sso_with_cartridge_store.py::test_the_username_is_shared_and_the_store_handle_stays_public_only` | `/api/me` username = kit username; the handle is neither it nor the email |
| kit | `…::test_a_store_only_account_with_the_same_username_is_never_joined` | collision: two accounts, each signs in to its own, the other password fails |
| Store (patch) | `tests/test_shared_identity.py` (10 tests) | contract; SSO ticket sign-in; others see only the handle (scores, multiplayer); collision; rename onto a taken username; a handle equal to another username; migration of pre-handle accounts; notice gate in JSON and once per version; CSRF order |

**Acceptance runs (2026-10-22, macOS, Python 3.12.10).** Each Store is a fresh clone of the
canonical repository.

```bash
PRG32_CARTRIDGE_STORE_SOURCE=<clone> PRG32_LIVE_STORE=local PRG32_REQUIRE_STORE=1 \
  python3 -m pytest -q tests/test_store_contract.py tests/test_store_live.py \
  tests/test_sso_with_cartridge_store.py tests/test_sso.py tests/test_sso_live.py \
  tests/test_publish_authorization.py
```

| Store | Store's own tests | Kit cross-repository suite |
|---|---|---|
| `820f74b` (CI pin) | n/a | **89 passed** |
| `4a3138b`, unpatched | 81 passed | 6 failed, 83 passed (the defects above) |
| `4a3138b` + patch | **91 passed** | **89 passed** |

The brief's four-file command alone: 51 passed against `4a3138b` + patch.

**To close the gate:** the Store maintainers merge the patch; then move
`store_reference.checked_against` to the merged commit, regenerate `tests/fixtures/contract/`
(`tools/build_contract_fixtures.py`) and run the command above.

## Full kit suite

`python3 -m pytest -q` (2026-10-22, macOS, Python 3.12.10, no Chromium, so the browser
suites skip; no `PRG32_LIVE_STORE`): **3 failed, 1,330 passed, 56 skipped**. The three
failures are the identity tests in `tests/test_sso_with_cartridge_store.py`, run against the
default `../CartridgeStore` checkout at `4a3138b` *without* the patch; with
`PRG32_CARTRIDGE_STORE_SOURCE` pointing at `4a3138b` + patch they pass (table above). No
other product failure.

## Remaining ecosystem gates (not feasible here)

1. Merge PRG32 #45/#46 and PRG32-QT #1 upstream, then move the pins and regenerate the audio
   evidence (`docs/upstream/README.md` §1–3).
2. The frame/audio scheduling of effects and whole-recording alignment beyond the recorded
   conformance hashes.
3. Physical PRG32 transfer and stereo capture with the eight-voice ADSR/pan cartridge.
4. The visible PRG32-QT desktop Import workflow.
5. AudioStudio with a named screen reader, with OS, browser and AT versions.
6. Institutional OIDC, Google, Microsoft and GitHub with test-owned tenants (only the
   in-process fakes and the disposable Keycloak run here).

PRG32-iOS remains unsupported; no delivery interface is offered.

Request the reassessment only after the decision owners have acted on hard gate 1 and the
Store has merged the identity patch.
