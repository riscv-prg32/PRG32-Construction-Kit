# ADR-0028: One Deploy tool for a PRG32 console, PRG32-QT and QEMU

**Status:** Accepted (2026-10-24, the brief after audit `7a700ba`). Builds on ADR-0020.

## Context

Students compile a PRG32 cartridge in the kit and then have to get it onto something that runs
it. Until now, that meant the SDK's command line (`python3 -m prg32 esp32c6 upload`) or
`tools/delivery_check.py`, both outside the kit. The audit asks for **Deploy** in the menu of an
open project. It must cover a physical PRG32, QEMU and canonical PRG32-QT behind one interface
that a learner can follow. It must still be truthful about each target: an emulator run is
never physical-device evidence.

## Decision

1. **The server deploys, to targets an administrator registered.** A browser page cannot reach
   a console's `http://192.168.4.1` from an `https://` kit under its strict CSP, and must not
   be allowed to make the server contact an address a student typed. So administrators register
   consoles and PRG32-QT computers by name and address (`/api/admin/deploy_targets`, http(s)
   addresses with no path or credentials). QEMU appears only when the operator sets
   `PRG32_QEMU_FIRMWARE` (environment only: it names programs the server runs).
2. **One adapter interface, three kinds.** `probe` (identity, ABI, limits, slots), `upload`,
   `launch`, `verify`, `screenshot`, `close` (`prg32_construction_kit/deploy.py`). Consoles
   and PRG32-QT share the PRG32 web API of ADR-0020. QEMU boots a fresh copy of the operator's
   firmware image in the deployment's own folder, with the cartridge staged in its slot. It is
   seen running from the serial console, and its screen is read through QEMU's GDB stub.
   `tools/build_qemu_firmware.py` makes that firmware folder from a named SDK revision, with a
   manifest: ABI, RAM, slots, flash SHA-256 and screen symbols.
3. **Nothing is replaced that nobody named or saw.** A deployment needs a named slot and a
   confirmation. It also carries what the student saw when they looked: the target's
   fingerprint (address, identity, ABI, limits) and the slot's content. Both are asked for again
   right before sending, and a difference is refused (`target_changed`, `slot_changed`).
4. **The cartridge is the one the kit built and the student sees.** It must be a kit build
   (`not_built_here`), its file must still have the SHA-256 recorded at build time
   (`hash_mismatch`), and it must be built from the project's current version (`stale_build`;
   builds now record `project_version`). Its architecture must be one the target runs
   (`wrong_architecture`). The target must accept its ABI by the SDK's own rules: major,
   hash or a compatible older hash, features (`unsupported_abi`). It must also have room in
   size and RAM (`target_full`).
5. **The steps run in the background and are recorded as they happen.** Each deployment row
   holds its status, progress, a translated log and its result. A broken connection is retried
   twice with the whole cartridge. Cancel stops before the next step. One deployment per target
   runs at a time (`target_busy`). A deployment left running by a stopped server is reported
   as `interrupted`. Every failure says what it left on the target. Only cartridges and slot
   names leave the kit, never a person's name.
6. **Evidence is labelled by what it is.** Every answer and record carries `evidence` and
   `physical_device`, and only a console is a physical device. `tools/deploy_evidence.py`
   drives a real target through these same API routes and keeps `record.json` and the
   screenshot under `docs/evidence/deploy/`.

## Consequences

- DEP-04 has records for QEMU and PRG32-QT (2026-10-24). No console was available, so the
  console adapter is tested only against `tests/fake_prg32.py`, and DEP-01 stays unverified.
- Moving Artifacts and Classes into the account menu keeps the menu bar to one row with Deploy
  in it.
- Deployments are personal data: they are in the record of processing, the export and the
  erasure (`deploy.delete_deployments_of`).
