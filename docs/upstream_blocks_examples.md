# Upstream PRG32 examples in Blocks

The dashboard **Examples** button contains editable Blocks adaptations of all
ten game examples and all twelve feature demos in the
[PRG32 examples](https://github.com/riscv-prg32/PRG32/tree/main/examples).

Each adaptation keeps one central idea visible: a player marker, a playfield,
directional input, and—in the audio lessons—an A-button beep. This makes the
projects small enough to read and change in a lesson, while preserving the
names and themes students will meet in the upstream C and assembly examples.

These are not source-for-source translations. Advanced upstream features such
as tile maps, hardware sprites, streamed samples, Wi-Fi setup, and the
raycaster need APIs that the introductory Blocks language does not yet expose.
Open an adaptation, make a change, run it in the simulator, then use **Convert
to C** to see the deterministic C generated from its saved Blocks JSON.
