"""Brick Catch: catch the falling bricks with your paddle (a PRG32 Python example)."""
import prg32

# The paddle at the bottom of the screen.
paddle_x: int = 140
PADDLE_Y: int = 184
PADDLE_W: int = 40

# Five bricks fall at once: their x and y positions are kept in lists.
brick_x: list[int] = [20, 80, 140, 200, 260]
brick_y: list[int] = [0, -60, -20, -100, -40]
speed: int = 2

score: int = 0
lives: int = 3
playing: bool = True


def restart() -> None:
    """Put everything back where it starts."""
    global score, lives, playing, speed
    score = 0
    lives = 3
    speed = 2
    playing = True
    for i in range(5):
        brick_y[i] = -40 * i


def wrap_brick(i: int) -> None:
    """Send brick number i back to the top, at a new place."""
    brick_y[i] = -prg32.random(10, 80)
    brick_x[i] = prg32.random(0, 304)


def centre(x: int, width: int) -> int:
    return x + width // 2


def init() -> None:
    restart()
    prg32.volume(180)


def play() -> None:
    """One frame of the game: move the paddle and the bricks, count catches and misses."""
    global paddle_x, score, lives, playing, speed
    if prg32.held(prg32.LEFT):
        paddle_x -= 4
    if prg32.held(prg32.RIGHT):
        paddle_x += 4
    paddle_x = prg32.clamp(paddle_x, 0, prg32.SCREEN_W - PADDLE_W)
    for i in range(5):
        brick_y[i] += speed
        if prg32.touching(brick_x[i], brick_y[i], 16, 8, paddle_x, PADDLE_Y, PADDLE_W, 6):
            score += 1
            prg32.note(72, voice=1, ms=80)
            wrap_brick(i)
            if score % 10 == 0:
                speed += 1
        if brick_y[i] > prg32.SCREEN_H:
            lives -= 1
            prg32.note(40, voice=2, ms=200)
            wrap_brick(i)
    if lives <= 0:
        playing = False


def update() -> None:
    if playing:
        play()
    else:
        if prg32.pressed(prg32.START):
            restart()


def draw() -> None:
    prg32.clear(prg32.NAVY)
    for i in range(5):
        prg32.rect(brick_x[i], brick_y[i], 16, 8, prg32.ORANGE)
    prg32.rect(paddle_x, PADDLE_Y, PADDLE_W, 6, prg32.CYAN)
    prg32.pixel(centre(paddle_x, PADDLE_W), PADDLE_Y - 2, prg32.WHITE)
    prg32.text(4, 4, "SCORE")
    prg32.number(score, 52, 4, prg32.YELLOW)
    prg32.text(240, 4, "LIVES")
    prg32.number(lives, 288, 4, prg32.YELLOW)
    if not playing:
        prg32.text(116, 96, "GAME OVER", prg32.RED)
        prg32.text(92, 112, "PRESS START", prg32.WHITE)
