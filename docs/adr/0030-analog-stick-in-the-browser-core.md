# ADR-0030: The analog stick in the browser core

## Status

Accepted.

## Context

ABI 1.8 adds `prg32_input_axis_x/y`, `prg32_input_axes_raw` and `prg32_input_has_analog`. PRG32-QT's
core answers them from the digital directions because its hosts have no stick. The browser does have
one: a game controller through the Gamepad API, or the on-screen stick.

## Decision

`wasm/CMakeLists.txt` patches the kit's copy of the core, as it does for the audio hooks: a new
`prg32_set_stick(present, x, y)` feeds those four calls, with the firmware's rule that a resting
stick still lets the direction buttons steer. A changed anchor line stops the build.
`static/js/prg32_controllers.js` turns controllers into a button mask and axes with the firmware's
deadzone and direction thresholds, once per frame. All controllers drive the one player.

## Consequences

- PRG32-QT's own results are unchanged while a cartridge reads no axis; the golden tests still compare.
- The kit's harnesses sweep the stick with the same script, so the native and WebAssembly builds are
  compared on these calls too.
- Multiplayer stays offline in the browser: the core has no transport there. (Amended by ADR-0031:
  windows of one browser now play together.)
