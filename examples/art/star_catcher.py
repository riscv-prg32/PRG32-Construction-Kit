"""Star Catcher: catch the falling star with the rocket (PRG32 Python, with Sprite Lab art)."""
import prg32

# The art is made in Sprite Lab ("rocket", "star"), Backgrounds ("sky") and AudioStudio
# ("Coin", "Theme"). The game names it; the kit turns each name into code.
rocket_x: int = 152
ROCKET_Y: int = 160
star_x: int = 100
star_y: int = 0
score: int = 0


def new_star() -> None:
    """Send the star back to the top, at a new place."""
    global star_x, star_y
    star_y = 0
    star_x = prg32.random(8, 304)


def init() -> None:
    """Runs once: the sky goes into the playfield, the music starts."""
    global rocket_x, star_x, star_y, score
    rocket_x = 152
    star_x = 100
    star_y = 0
    score = 0
    prg32.background_load("sky")
    prg32.soundtrack_play("Theme")


def update() -> None:
    """Runs every frame: move the rocket, let the star fall, catch it."""
    global rocket_x, star_y, score
    if prg32.held(prg32.LEFT):
        rocket_x -= 3
    if prg32.held(prg32.RIGHT):
        rocket_x += 3
    rocket_x = prg32.clamp(rocket_x, 0, 304)
    star_y += 2
    if prg32.touching(rocket_x, ROCKET_Y, 16, 16, star_x, star_y, 8, 8):
        score += 1
        prg32.sound_effect("Coin")
        new_star()
    if star_y > 176:
        new_star()


def draw() -> None:
    """Runs every frame after update: the sky, the rocket, the star, the score."""
    prg32.background_draw("sky")
    prg32.sprite("rocket", rocket_x, ROCKET_Y)
    prg32.sprite("star", star_x, star_y)
    prg32.number(score, 8, 8, prg32.YELLOW, prg32.NAVY)
