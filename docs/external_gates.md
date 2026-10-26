# Gates the kit cannot close by itself

Some requirements need a decision by the school, a merge in another repository, a real device or a
real account. Code cannot close them, and the kit never pretends it has: each one keeps its
capability `partial` or `missing` until the evidence named here exists. This page says, for each
gate, who closes it, what the kit already has ready, and what evidence closes it.

## 1. Personal data: the controller's decisions (GDPR-01)

| | |
| --- | --- |
| Who | the school or operator running the kit (the controller), its DPO or counsel |
| Open | D-0 to D-10 in [privacy/decisions.md](privacy/decisions.md): controller and DPO named, the DPIA, the national law and the age, consent for optional services, legal bases (including the new deployment and evaluation records, `ropa.json` item `deployment`), retention, cloud and Store roles, the DPO's review of `docs/privacy/`, processor agreements, breach contacts and a **staffed** breach exercise |
| Ready | field-level record of processing (`ropa.json`), notices with versions, the rights workflows (export, register, restriction, erasure across every table and folder), the breach playbook and a technical rehearsal (2026-10-21) |
| Closes it | each D-line filled in with who decided, when and how, and a staffed exercise recorded under `privacy/exercises/`. Maintainers never fill in a decision: proposed defaults stay proposals |

## 2. Cartridge Store: the shared identity contract (STR-01, ACC-*)

| | |
| --- | --- |
| Who | the Cartridge Store maintainers |
| Ready | [upstream/cartridge-store-shared-identity.patch](upstream/cartridge-store-shared-identity.patch); the kit's side of the contract and its tests |
| Closes it | the patch (or an equivalent) merged into CartridgeStore, the kit pinned to that revision, and `tests/test_sso_with_cartridge_store.py` passing **unpatched** against it. Today it fails against the unpatched Store, which gives a `player-…` handle instead of the shared username |

## 3. PRG32 SDK and PRG32-QT: the buzzer retirement, the audio clock, the firmware engine (AUD-02, AUD-04)

| | |
| --- | --- |
| Who | the PRG32 and PRG32-QT maintainers |
| Ready | three tested patches and their pull requests ([upstream/README.md](upstream/README.md): riscv-prg32/PRG32#45, #46, riscv-prg32/PRG32-QT#1) |
| After the merge | move the pins (`static/wasm/BUILD.json`, CI's SDK and PRG32-QT revisions), then regenerate and check: `python3 tools/build_language_index.py`, `python3 tools/build_audio_fixtures.py`, `python3 tools/build_debug_fixtures.py`, `python3 tools/build_contract_fixtures.py`, `python3 tools/build_wasm.py`; `tests/test_upstream_sdk_patches.py` then tests the merged SDK itself |
| Closes it | the upstream conformance run green on the merged revisions, with the patches deleted from `docs/upstream/` |

## 4. A physical PRG32 console (DEP-01, DEP-04, EVAL-01, AUD-02)

| | |
| --- | --- |
| Who | someone with a PRG32 console flashed with the pinned firmware, on the same network as a kit |
| Ready | Deploy and Evaluate speak the console's web API, tested against `tests/fake_prg32.py`; the recording tools |
| Run | `python3 tools/deploy_evidence.py --console http://192.168.4.1 --slot cart7 --out docs/evidence/deploy/DATE-console` |
| | `python3 tools/evaluation_evidence.py --console http://192.168.4.1 --slot cart7 --out docs/evidence/evaluate/DATE-console` |
| | the stereo recording of [hardware_audio_check.md](hardware_audio_check.md) (integrity, eight voices, pan, ADSR, silence and reset, no buzzer output) |
| Closes it | those records, committed with the console's firmware revision in them. A stand-in device or an emulator never counts |

## 5. PRG32-iOS (DEP-03)

| | |
| --- | --- |
| Who | the PRG32-iOS maintainers |
| Today | PRG32-iOS has no documented import interface beyond its file importer, so the kit claims nothing (ADR-0020) |
| Closes it | a documented PRG32-iOS interface and a recorded handoff to a real device. Until then DEP-03 stays at 0: no guessed URL scheme |

## 6. Google Drive and OneDrive, for real (CLD-01, CLD-02)

| | |
| --- | --- |
| Who | someone with throwaway test accounts at both providers |
| Ready | `tests/test_cloud_live.py` (settings from the environment only; it touches only files it makes, and deletes them) |
| Run | see [live_testing.md](live_testing.md) for the variables, then `python3 -m pytest -q tests/test_cloud_live.py -rs` |
| Closes it | a recorded run against both providers. A skipped run is not a pass |

## 7. Builds that share the server's user id (SEC-01)

| | |
| --- | --- |
| Today | every build runs as the same server user outside its namespaces. Builds are kept apart by mounts and by a process limit that counts that user's processes host-wide ([build_sandbox.md](build_sandbox.md); CI proves it beside 300 processes of the same uid) |
| Who | the operator |
| Closes it | either per-build user ids (they need privileges the container drops on purpose: ADR-0010), or the formal isolation of the kit's user id: a host or VM where no other workload runs as that uid, written into the deployment's own records |

## Where the evidence goes

Each closed gate adds its record under `docs/evidence/` (or `docs/privacy/` for the controller's
decisions) and a line in the capability's note in `capabilities.json`. The auditor sets the
scores (`audit_score`), never the maintainers.
