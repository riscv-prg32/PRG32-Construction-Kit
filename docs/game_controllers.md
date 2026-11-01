# Game controllers and the analog stick

## For students

**Plug in a game controller** (USB or Bluetooth) on the computer running the browser, open the IDE
or the Player, and **press any button on it**: browsers show a controller to a page only after that.
The name of the controller appears under the screen. It works at once, with no setup.

| Controller | PRG32 |
| --- | --- |
| Left stick | The analog stick, and the directions |
| Cross | LEFT, RIGHT, UP, DOWN |
| Bottom, right, left, top button | A, B, C, D |
| Shoulder buttons and triggers | L, R |
| Back/View, Start/Menu | SELECT |

Without a controller, drag the **on-screen stick** next to the game. The keyboard also has the new
buttons: <kbd>C</kbd> is C, <kbd>V</kbd> is D, <kbd>Q</kbd> is L and <kbd>E</kbd> is R.

**Read the stick in your game.** The stick says *how far*, the buttons only *which way*:

| Value | Meaning |
| --- | --- |
| `stick_x()` | -127 (left) to 127 (right), 0 at rest |
| `stick_y()` | -127 (up) to 127 (down), 0 at rest |
| `has_stick()` | 1 with a real stick, 0 with buttons only |

In Blocks, type them in any number field; the **Input** category has two ready-made blocks,
*change player_x by stick_x() / 32*. In PRG32 Python write `prg32.stick_x()`. In C and assembly,
call `prg32_input_axis_x()` and `prg32_input_axis_y()`.

```python
x = prg32.clamp(x + prg32.stick_x() // 32, 0, 312)
```

A game that uses the stick also works without one: the direction buttons then give -127, 0 or 127.
Pushing a stick also presses the direction buttons, so a game written for buttons needs no change.

## For teachers

- Nothing needs installing, and nothing about a controller is sent to the server or stored.
- Browsers offer controllers only on `https://` pages and on `localhost`. On a plain `http://` school
  server, controllers do not appear; the on-screen stick and the keyboard still work.
- Every controller drives the same player. A PRG32 console has one player: a second player needs a
  second console ([multiplayer](multiplayer.md)).
- A controller that the browser does not recognise as "standard" uses its first six buttons as
  A, B, C, D, L, R and its next four as SELECT. The kit has no screen for changing this.

## Consoles

On a console, the stick is the hardware's: profile `breadboard2` has an analog stick and buttons C,
D, L and R; `breadboard1` has neither, so `has_stick()` is 0 and those four buttons are never pressed.
Offer a way to play with A and B if your game should run on every console.

## How it matches the console

`static/js/prg32_controllers.js` follows the firmware's rules: a deadzone of 12, then a rescale to
reach ±127, and a direction that turns on at a tilt of 40 and off below 24. The browser core answers
ABI calls 140 to 143 from it (ADR-0030). A physical stick also has calibration, which a controller
does not need. `prg32_input_axes_raw` gives 2048 + 16 × axis in the browser, a stand-in for the
12-bit reading of a real stick.
