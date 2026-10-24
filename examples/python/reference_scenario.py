"""Scenario L: the PRG32 Python reference game (tools/python_reference.py).

It uses every kind of thing a PRG32 Python game does, so one cartridge shows them all working:
whole-number arithmetic with the cartridge rules, if/elif/else and for, helper functions,
drawing, buttons, and the eight voices with stereo sound from AudioStudio.
"""
import prg32

x: int = 150
y: int = 100
score: int = 0
level: int = 0
wrapped: int = 0
tick: int = 0
playing: bool = True
grid: list[int] = [0] * 16


def double(v: int) -> int:
    return v * 2


def bump(points: int) -> None:
    global score
    score += points


def init() -> None:
    """Runs once: fill the grid, check the cartridge's number rules, start the sound."""
    global wrapped, level
    for i in range(16):
        grid[i] = i * 3 - 7
    wrapped = 2147483647
    wrapped += 1
    level = -7 // 2 + -7 % 2 + double(3)
    for v in range(8):
        prg32.note(60 + v * 4, v, 400)
    prg32.soundtrack_play("theme")


def update() -> None:
    """Runs every frame: buttons, movement, the grid."""
    global x, y, tick, playing
    tick += 1
    if prg32.held(prg32.LEFT):
        x -= 2
    if prg32.held(prg32.RIGHT):
        x += 2
    if prg32.pressed(prg32.A):
        bump(10)
        prg32.sound_effect("zap")
    if prg32.pressed(prg32.B):
        playing = not playing
    x = prg32.clamp(x, 0, 304)
    if tick % 60 == 0:
        y = 100 + prg32.sin(tick) * 20 // 256
    elif tick % 30 == 0:
        y = 100
    else:
        pass
    for i in range(16):
        if grid[i] < 0:
            grid[i] += 1
        elif grid[i] > 20:
            grid[i] = 0


def draw() -> None:
    """Runs every frame after update: the screen."""
    prg32.clear(prg32.NAVY)
    for i in range(16):
        prg32.rect(i * 20, 180 - grid[i], 18, 4, prg32.CYAN)
    prg32.rect(x, y, 16, 16, prg32.YELLOW)
    prg32.circle(160, 60, 12, prg32.MAGENTA, filled=True)
    prg32.line(0, 0, x, y, prg32.WHITE)
    prg32.bitmap(["...XX...", "..XXXX..", ".XXXXXX.", "XXXXXXXX", "XXXXXXXX", ".XXXXXX.", "..XXXX..", "...XX..."],
                 280, 20, prg32.LIME, 2)
    prg32.text(8, 8, "SCORE", prg32.WHITE, prg32.NAVY)
    prg32.number(score, 56, 8, prg32.YELLOW, prg32.NAVY)
    prg32.number(wrapped, 8, 20, prg32.GRAY, prg32.NAVY)
    prg32.number(level, 8, 32, prg32.GRAY, prg32.NAVY)
    if not playing:
        prg32.text(120, 96, "PAUSED", prg32.RED, prg32.BLACK)
