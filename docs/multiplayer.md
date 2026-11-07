# Multiplayer

PRG32 multiplayer is online only: each player has their own console (or PRG32-QT), and the consoles
share numbers through a [PRG32 Multiplayer Server](https://github.com/riscv-prg32/PRG32-Multiplayer-Server)
on the classroom network. There is no second player on one console any more: the firmware removed
the player 2 buttons.

## For students

A multiplayer game does three things:

1. **Join a room**, once, when the game starts. Only consoles in the same room see each other.
2. **Share** your numbers every frame: x, y, a "look" and "flags". They mean what your game decides.
3. **Read** the other players and draw them.

| Blocks | PRG32 Python | What it does |
| --- | --- | --- |
| *join multiplayer room* | `prg32.mp_join("class3b")` | Ask for a place. An empty room name means the game's title |
| *share my position x y look flags* | `prg32.mp_share(x, y, look, flags)` | Give the others your numbers |
| *share my buttons* | `prg32.mp_send_buttons()` | Let the others read your buttons |
| *leave multiplayer room* | `prg32.mp_leave()` | Leave the room |

Read the others in any number field, or with `prg32.` in front in Python:

| Value | Meaning |
| --- | --- |
| `peers()` | How many other players are in the room |
| `peer_x(i)`, `peer_y(i)`, `peer_look(i)`, `peer_flags(i)` | What player `i` shared (0 is the first) |
| `peer_input(i)` | The buttons player `i` shared |
| `peer_id(i)` | The ID of player `i` |
| `my_id()` | Your own ID: 0 until the server has let you in |

A small game in PRG32 Python:

```python
import prg32

x: int = 160


def init() -> None:
    prg32.mp_join("class3b")


def update() -> None:
    global x
    x = prg32.clamp(x + prg32.stick_x() // 32, 0, 312)
    prg32.mp_share(x, 100, 1)


def draw() -> None:
    prg32.clear(prg32.BLACK)
    prg32.rect(x, 100, 8, 8, prg32.YELLOW)
    if prg32.peers() > 0:
        prg32.rect(prg32.peer_x(0), prg32.peer_y(0), 8, 8, prg32.RED)
```

Things that are good to know:

- Joining takes a moment. Draw "waiting" while `my_id()` is 0.
- Players come and go, and an ID can change after a reconnection. Do not keep one for later.
- A room name has up to 47 letters, digits and `_ - . :`. Other characters become `-`, so
  *Star Catcher* is the room `Star-Catcher`.
- Change the room name, for example to `pong:v2`, when a new version shares its numbers differently.

## Testing on one computer

Open your game in **two windows** of the same browser (or two tabs), side by side, and press Run (or
Play in the Player) in both. Windows in the same room see each other: `peers()` is 1, `my_id()` is
a number, and each window is one player. The status line under the Player says how many others are
in the room. The quick Blocks preview joins the same rooms, so it can even play against the Player.

To give each window its own player:

- **Keyboard:** click a window's game screen; the keys go to that window only.
- **Two game controllers:** choose *Controller for this window* under the screen, a different one in
  each window. With *All controllers*, every controller moves every window.

The browser does not reach the PRG32 Multiplayer Server: only windows of this browser meet. To play
with consoles, download the PRG32 cartridge and run it on consoles, or on PRG32-QT with the server's
address in its settings. A window that is hidden (minimised, or a tab in the background) stops its
game, and the others see it leave after 3 seconds.

## For teachers

Run one server on a computer in the classroom network, and give each console its address
(`python3 -m prg32 multiplayer set-url ws://192.168.1.10:8081`):

```bash
git clone https://github.com/riscv-prg32/PRG32-Multiplayer-Server.git
```

Give each group its own room name so that groups do not meet by accident.

## What the kit generates

The generated C and assembly call the firmware directly, and you can read both:

- *join* calls `prg32_multiplayer_join` only the first time. Every firmware join forgets the other
  players, so a join that ran every frame would never see anyone.
- A game that uses multiplayer calls `prg32_multiplayer_tick` once per frame, at the end of update,
  even if it only watches: that call sends your numbers, and a console that stays silent for 15
  seconds is dropped by the server.
- The kit warns about a game that uses multiplayer but has no join step, because it would stay alone
  without any error.

In the browser the same calls reach `static/js/prg32_multiplayer.js`, which passes the numbers to the
other windows of the browser with a `BroadcastChannel` (ADR-0031): nothing is sent to the server or
stored.
