# PRG32 examples in Blocks

The dashboard **Examples** button lists two kinds of Blocks projects.

## Complete games

Five classic-inspired games built only from blocks, each with a step-by-step
tutorial and slide deck in [tutorials/games/](tutorials/games/README.md):

| Game | File |
| --- | --- |
| Pong (you against the computer) | `examples/games/pong.json` |
| Breakout | `examples/games/breakout.json` |
| Space Invaders | `examples/games/space_invaders.json` |
| Asteroids | `examples/games/asteroids.json` |
| Snake | `examples/games/snake.json` |

They are full games: title screen, scoring, lives or win conditions, sound and
restart. Each one compiles to a PRG32 cartridge for the board and for QEMU and
was run on the QEMU firmware and on PRG32-QT (`runtime_check.md`).

`examples/feature_tour.json` is a one-screen reference that uses every family
of blocks (tiles, scrolling, sprites, palette, lines, circles, lists, sound,
status band, multiplayer, player 2).

## Sketches of the other upstream examples

For the remaining game examples and feature demos in the
[PRG32 examples](https://github.com/riscv-prg32/PRG32/tree/main/examples)
(Pacman, Tetris, Platformer, Raycaster, Wing Commander, Frogger, scrolling,
sprites, audio demos, ...), the dashboard offers short **sketches**: a
playfield, a player marker, directional input and, in the audio lessons, an
A-button beep. They keep the upstream names and themes and are a starting
point for students' own versions.

Sketches are not source-for-source translations. Platformer physics,
streamed samples, tracker music and Wi-Fi setup need APIs that are only
available in **Advanced C** (see `prg32_feature_coverage.md`). Open a sketch,
make a change, run it in the simulator, then use **Generate C** to see the
deterministic C generated from its saved Blocks JSON.
