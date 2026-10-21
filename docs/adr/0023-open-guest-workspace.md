# ADR-0023: The kit opens without an account (guest workspace)

**Status:** Accepted (2026-10-22). Amends ADR-0017 (guests) and ADR-0012 (what needs the server).

## Context

Until now every page asked for a sign-in, and a visitor without an account got a small
static page: a Blocks scratchpad in IndexedDB (ADR-0017). Teachers asked for the real kit to
be open by default, the way a student meets it in class: the IDE, Sprite Lab, AudioStudio and
the Player, with a sign-in needed only for what must be kept or shared on the server
(building a real cartridge, publishing, classes).

## Decision

1. **Open by default.** A new setting, **Sign-in required for every page**
   (`LOGIN_REQUIRED`, `PRG32_KIT_LOGIN_REQUIRED`, default **off**), together with the existing
   `PRG32_GUEST_MODE=local`, opens these pages to visitors without an account:
   `/`, `/ide/<id>`, `/projects/<id>`, `/sprites`, `/audio-studio`, `/audio-studio/<id>` and
   `/player` (`auth.GUEST_PAGES`). Turning the setting on, or `PRG32_GUEST_MODE=off`, closes
   them again: every page then asks for a sign-in, as before.
2. **Still no server storage for guests** (ADR-0017 rule 1 holds). A guest's projects, sprites
   and sounds live in IndexedDB (`guest_store.js`, database version 2). The pages are unchanged:
   `Kit.api` hands their calls to `guest_api.js`, which answers from IndexedDB in the server's
   shapes, including the same version checks (`expected_version`, 409).
3. **Stateless guest API.** What only the server can do, it does on what the browser sends
   and keeps nothing (`prg32_construction_kit/guest_api.py`): generate the validated IR, C and
   assembly (`routes.generate_sources`, the same code as for an account, so the output is
   identical), check and preview an AudioStudio sound, turn a sprite into C, and copy an
   example. It writes no rows and no files. It is limited per address
   (`security.LIMITS["guest_api"]`); that counter is a hashed key, as for sign-in attempts.
4. **Needs an account:** building a cartridge (`/package`) and the compiler check (`/check`),
   publishing, classes, artifacts, cloud copies, samples (their sound is a server file) and
   project history. The page shows **Sign in to keep going**; nothing is lost.
5. **Moving in.** After sign-in, the Projects page moves each guest game into the account with
   its sound and sprites; each leaves the browser only after the server has all of it.
6. **The static offline page stays** for when the server cannot be reached.

## Consequences

- AGENTS.md: "every page requires a signed-in user" now reads "unless the operator turned off
  Sign-in required"; the guest pages and APIs above are the only exceptions.
- The guest notice changes: the server now sees a guest's blocks or sound while it answers a
  request (and keeps none of it): notice `guest` 1.1, record of processing `guest_requests`.
- Generated C and assembly for guests are the teaching material they are for accounts:
  deterministic, validated, never compiled.
- Tests: `tests/test_guest_access.py` (pages, closed routes, nothing stored, same code,
  limits) and `tests/test_guest_ide_browser.py` (the workspace in a real browser, moving in).
