# ADR-0031: Multiplayer between windows of one browser

## Status

Accepted (amends 0030's "multiplayer stays offline in the browser").

## Context

A Blocks multiplayer game could only be tried on two consoles (or two PRG32-QT) and a PRG32
Multiplayer Server. In the browser the core had no `MultiplayerService`, so `join` failed, `my_id()`
stayed 0 and a student never saw a second player. PRG32-QT's core already asks a platform-neutral
`MultiplayerService` (`src/core/Multiplayer.h`) for ABI calls #32 to #40 and #139, so no core patch
is needed.

## Decision

- `wasm/prg32_core_api.cpp` gives the core a small `KitMultiplayer` service with the firmware's rules
  (room names `[A-Za-z0-9_.:-]{1,47}`, sharing only after a join, a join forgets the others, eleven
  button bits, at most 8 peers). The page is its transport: after each frame it reads the room and
  this player's state (`prg32_mp_room`, `prg32_mp_local_json`); before the next one it gives the
  core the players it hears (`prg32_mp_clear_peers`, `prg32_mp_put_peer`).
- `static/js/prg32_multiplayer.js` carries those numbers between the windows and tabs of the same
  browser with a `BroadcastChannel`: one message per frame, a leave message when a window leaves or
  closes, and a player not heard for 3 s is gone (as `PRG32_MULTIPLAYER_PEER_TIMEOUT_MS`). Each
  window has a random player ID.
- The quick Blocks preview (`simulator.js`) joins the same rooms, so the preview and the PRG32 core
  can even play each other.
- `prg32_controllers.js` lets a window use one controller of its own, so two controllers and two
  windows side by side are two players.

## Consequences

- Nothing crosses the network and nothing is stored: a `BroadcastChannel` reaches only pages of the
  same origin in the same browser profile. It works for guests and offline pages too.
- Players in the browser never meet consoles; that still needs the server. The generated C and
  assembly are unchanged, and a console behaves as before.
- With no page feeding it (the native harness) a game is alone in its room but does get an ID,
  like the firmware once it is admitted; the golden tests are unchanged.
- Hidden tabs slow down or stop their frames, so they drop out after 3 s, as a console that stops.
