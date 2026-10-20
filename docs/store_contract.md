# The Store contract

One file, `contracts/prg32-store-contract-1.json`, says what a PRG32 Store bundle
is, what the Cartridge Store accepts, and what its refusals mean (ADR-0018). The kit
and the Store are checked against it, so they cannot drift apart without a test
failing.

## What is in it

| Section | What it says |
|---|---|
| `bundle` | a zip with `manifest.json`, an icon, and one PRG32 cartridge (`.prg32`) per architecture |
| `manifest_schema` | the manifest as a JSON Schema: `abi`, `id`, `title`, `version`, `assets`, `architectures` |
| `architectures` | the two real targets (`esp32c6`, `qemu`) and the aliases the Store understands |
| `versioning` | the kit's rule (`0.1.<project version>`) and how the Store treats a repeated id/version |
| `publish` | `POST /api/publish/bundle`, the answer, and when a game becomes visible |
| `errors` | every refusal as a stable code, a message a student can read, and whether trying again can help |
| `tokens` | how Store tokens are made and revoked, and that they do not expire |
| `cartridge_artifact_metadata` | what the kit records about each PRG32 cartridge it builds |

`store_reference.checked_against` names the CartridgeStore commit the contract was
last checked against.

## For students

Before anything leaves the kit, your bundle is checked like the Store checks it. If
something is wrong you see why straight away (for example *"The game's id or version
uses characters the Store does not allow"*) and nothing is uploaded. If the Store
cannot be reached, the kit says that nothing was published and that you can try
again; trying again never publishes twice.

## For teachers

- A published game is a **pending submission**. It appears in the Store's catalogue
  only after an editor verifies it.
- Every saved change gives the game a new version (`0.1.7`, `0.1.8`, ...).
  Publishing an unchanged project again sends nothing new.
- A Store token works until you revoke it in the Store (**tokens do not expire**).
  Revoke the token of a publish profile you no longer use.

## How it is checked

| Check | Where |
|---|---|
| The fixture bundles are generated and reproducible | `tools/build_contract_fixtures.py --check` |
| The kit accepts and refuses each fixture with the contract's code | `tests/test_store_contract.py` |
| The Store's own bundle code accepts and refuses the same fixtures, and its messages map to the same codes; its id/version patterns, metadata ABI and architectures equal the contract's | `tests/test_store_contract.py` with a CartridgeStore checkout (CI job `store-contract`, which fails if the Store is missing) |
| Real publishes over HTTP to a throwaway Store: pending until verified, updates, repeated id/version, refused manifests, revoked token, the Store going away and coming back | `tests/test_store_live.py` (`PRG32_LIVE_STORE=local`; CI job `store-contract`) |

The live suite starts the CartridgeStore from the checkout next to the kit (or
`PRG32_CARTRIDGE_STORE_SOURCE`) on `127.0.0.1:5160` with a temporary data folder,
a random secret key and a test admin password. The kit's egress allow-list contains
only that address, so the suite cannot reach any other Store and never touches
production data.

```bash
PRG32_LIVE_STORE=local python3 -m pytest -q -rs tests/test_store_live.py
```

After changing the contract or the kit's manifest, regenerate the fixtures:

```bash
python3 tools/build_contract_fixtures.py
```

## Gaps in the Store today: what the kit does, and the proposal

1. **Repeated id/version.** The Store accepts a second pending submission with an id
   and version it already has; approving it replaces that version's files.
   - *The kit:* sends one bundle per id and version to a Store. The same files again
     get the first answer and nothing is uploaded; other files are refused with
     `version_already_published` until the student saves (a new version).
     (`versioning.kit_duplicate_rule`)
   - *Proposal for CartridgeStore:* refuse an upload whose id/version is already
     published or pending with another bundle digest (`409`, code
     `duplicate_version`), and accept the same digest again idempotently.
2. **Tokens without expiry.**
   - *The kit:* records when a publish profile's token was put in, shows the date it
     stops working (`token_expires_on`), and refuses it after
     `PRG32_STORE_TOKEN_MAX_DAYS` (default 180) with `token_too_old`. Rotation: make
     a new token in the Store, put it in the profile, revoke the old one in the Store.
     (`tokens.kit_rotation`)
   - *Proposal for CartridgeStore:* `POST /auth/tokens` accepts `expires_in_days`
     (default 180, at most 365); the token list shows `expires_at`; an expired token
     is refused with `401` and code `token_expired`.

Both proposed codes are already in the error catalogue (marked `"proposed": true`), so
a Store that adopts them is understood without a new contract version. Every change to
this file so far only added keys: `tests/test_store_lifecycle.py` checks that version 1
keeps all its keys and codes.

The live suite asserts the Store's current behaviour against the contract, so when
the Store changes, the suite fails and the contract is updated in the same change.
