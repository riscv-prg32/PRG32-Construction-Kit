# ADR-0020: Delivery targets the kit claims, and how evidence is recorded

**Status:** Accepted (2026-10-20, priority 3 of the brief after audit `fea31c0`)

## Context

The capability table lists three delivery targets beyond the browser: the PRG32
console (DEP-01), PRG32-QT (DEP-02) and PRG32-iOS (DEP-03). The kit verifies the
browser Player automatically and PRG32-QT's runtime headlessly, but no console, no
end-user PRG32-QT import and no iOS device has been used. PRG32-iOS is a private
repository that imports cartridges with a SwiftUI file importer; it has no URL scheme
or API the kit could hand a cartridge to.

## Decision

1. **PRG32-iOS handoff is deferred.** The kit does not implement or claim an iOS
   handoff, and does not invent a URL scheme or API. `docs/delivery.md` and
   `docs/compatibility.md` say so. Revisit when PRG32-iOS publishes an import
   contract and a device is available.
2. **Console and PRG32-QT use the PRG32 web API**, the one the SDK's
   `python3 -m prg32 esp32c6 upload` uses: `POST /api/games?slot=`,
   `POST /api/games/select?slot=`, `GET /api/screenshot.bmp`. The kit adds no new
   protocol.
3. **Evidence is a record, not a claim.** `tools/delivery_check.py` writes JSON per
   run: cartridge SHA-256 and header, device runtime answer, slot, screenshot hash
   and whether anything is drawn, outcome, kit and SDK commits, notes. It talks only
   to the `--url` given and needs an explicit `--slot`, because an upload replaces
   that slot.
4. Developers do not run it against someone's own PRG32-QT by default: uploading
   changes that installation's cartridge slots.

## Consequences

- DEP-01 and DEP-03 stay unverified; DEP-03 is recorded as deferred. They move only
  when a record from a real device is added to `docs/implementation-status.md`.
- The end-user PRG32-QT import (file dialog) is described for teachers; its
  recorded run is still pending.
