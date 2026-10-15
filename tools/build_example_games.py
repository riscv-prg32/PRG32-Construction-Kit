#!/usr/bin/env python3
"""Write the five classic-inspired example games as Blocks JSON.

The games live in ``examples/games/*.json`` and are ordinary Construction Kit
projects: open them in the editor, change blocks, play them in the simulator,
generate C and build PRG32 cartridges. This script only exists so the JSON
can be regenerated deterministically after a change to a game:

    python3 tools/build_example_games.py

Each game is written with a tiny helper vocabulary that mirrors the blocks a
student drags (``set_``, ``if_``, ``repeat``, ``rect`` ...).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "examples" / "games"


class Workspace:
    """Collects blocks and gives every block a stable, readable id."""

    def __init__(self, slug: str):
        self.slug = slug
        self.count = 0

    def block(self, block_type: str, fields: dict | None = None, inputs: dict | None = None) -> dict:
        self.count += 1
        block: dict = {"type": block_type, "id": f"{self.slug}-{self.count}"}
        if fields:
            block["fields"] = {key: str(value) for key, value in fields.items()}
        if inputs:
            linked = {name: chain(body) for name, body in inputs.items()}
            block["inputs"] = {name: {"block": first} for name, first in linked.items() if first}
        return block


WS: Workspace = Workspace("game")


_USED: set[str] = set()


def chain(blocks) -> dict | None:
    """Link a list of statement blocks with 'next' and return the first one."""
    flat = [b for b in _flatten(blocks) if b]
    for block in flat:
        if block["id"] in _USED:
            raise ValueError(f"block {block['id']} is used twice; build a fresh block instead")
        _USED.add(block["id"])
    for current, following in zip(flat, flat[1:]):
        current["next"] = {"block": following}
    return flat[0] if flat else None


def _flatten(items):
    for item in items:
        if isinstance(item, (list, tuple)):
            yield from _flatten(item)
        else:
            yield item


# ---- one helper per block -------------------------------------------------
def comment(text): return WS.block("prg32_comment", {"TEXT": text})
def set_(var, value): return WS.block("prg32_set_state", {"VAR": var, "VALUE": value})
def change(var, delta): return WS.block("prg32_change_state", {"VAR": var, "DELTA": delta})
def keep(var, low, high): return WS.block("prg32_clamp_state", {"VAR": var, "LOW": low, "HIGH": high})
def wrap(var, low, high): return WS.block("prg32_wrap_state", {"VAR": var, "LOW": low, "HIGH": high})
def rand(var, low, high): return WS.block("prg32_random_state", {"VAR": var, "LOW": low, "HIGH": high})
def make_list(name, size, value=0): return WS.block("prg32_list_create", {"LIST": name, "SIZE": size, "VALUE": value})
def set_item(name, index, value): return WS.block("prg32_list_set", {"LIST": name, "INDEX": index, "VALUE": value})
def change_item(name, index, delta): return WS.block("prg32_list_change", {"LIST": name, "INDEX": index, "DELTA": delta})
def if_(cond, *body): return WS.block("prg32_if", {"COND": cond}, {"DO": body})
def if_else(cond, body, otherwise): return WS.block("prg32_if_else", {"COND": cond}, {"DO": body, "ELSE": otherwise})
def repeat(var, first, last, *body): return WS.block("prg32_repeat", {"VAR": var, "FROM": first, "TO": last}, {"DO": body})
def held(button, *body): return WS.block("prg32_if_button", {"BUTTON": button}, {"DO": body})
def pressed(button, *body): return WS.block("prg32_if_button_once", {"BUTTON": button}, {"DO": body})


def touching(a, b, *body):
    fields = dict(zip(("AX", "AY", "AW", "AH"), a)) | dict(zip(("BX", "BY", "BW", "BH"), b))
    return WS.block("prg32_if_touching", fields, {"DO": body})


def clear(color): return WS.block("prg32_clear_screen", {"COLOR": color})
def rect(x, y, w, h, color): return WS.block("prg32_draw_rect", {"X": x, "Y": y, "W": w, "H": h, "COLOR": color})
def outline(x, y, w, h, color): return WS.block("prg32_draw_frame", {"X": x, "Y": y, "W": w, "H": h, "COLOR": color})
def rect_rgb(x, y, w, h, rgb): return WS.block("prg32_draw_rect_rgb", {"X": x, "Y": y, "W": w, "H": h, "RGB": rgb})
def line(x1, y1, x2, y2, color): return WS.block("prg32_draw_line", {"X1": x1, "Y1": y1, "X2": x2, "Y2": y2, "COLOR": color})
def circle(x, y, r, color, filled=False): return WS.block("prg32_draw_circle", {"X": x, "Y": y, "R": r, "COLOR": color, "FILL": "FILLED" if filled else "OUTLINE"})
def text(value, x, y, fg="WHITE", bg="BLACK"): return WS.block("prg32_draw_text", {"TEXT": value, "X": x, "Y": y, "FG": fg, "BG": bg})
def number(value, x, y, fg="WHITE", bg="BLACK"): return WS.block("prg32_draw_number", {"VALUE": value, "X": x, "Y": y, "FG": fg, "BG": bg})


def _rows(rows):
    return {f"ROW{index}": row for index, row in enumerate(rows)}


def picture(rows, x, y, color, scale=2): return WS.block("prg32_draw_bitmap", {"X": x, "Y": y, "COLOR": color, "SCALE": scale, **_rows(rows)})
def sprite8(rows, x, y, fg, bg): return WS.block("prg32_draw_sprite8", {"X": x, "Y": y, "FG": fg, "BG": bg, **_rows(rows)})
def tile_define(tile_id, rows, fg, bg): return WS.block("prg32_tile_define", {"ID": tile_id, "FG": fg, "BG": bg, **_rows(rows)})
def fill_playfield(layer, tile_id): return WS.block("prg32_playfield_clear", {"LAYER": layer, "ID": tile_id})
def put_tile(tile_id, layer, tx, ty): return WS.block("prg32_playfield_put", {"ID": tile_id, "LAYER": layer, "TX": tx, "TY": ty})
def draw_playfield(layer, transparent=False): return WS.block("prg32_playfield_draw", {"LAYER": layer, "TRANSPARENT": "TRANSPARENT" if transparent else "OPAQUE"})
def beep(freq, ms): return WS.block("prg32_play_beep", {"FREQ": freq, "MS": ms})
def note(midi, channel, ms): return WS.block("prg32_audio_note", {"NOTE": midi, "CHANNEL": channel, "MS": ms})
def band(label, value=""): return WS.block("prg32_band_text", {"TEXT": label, "VALUE": value})
def save_score(value): return WS.block("prg32_score_submit", {"VALUE": value})
def splash(title, subtitle, ms): return WS.block("prg32_splash", {"TITLE": title, "SUBTITLE": subtitle, "MS": ms, "BG": "NAVY", "FG": "WHITE", "ACCENT": "YELLOW"})
def scroll_playfield(layer, x, y): return WS.block("prg32_playfield_scroll", {"LAYER": layer, "X": x, "Y": y})
def camera(x, y): return WS.block("prg32_playfield_camera", {"X": x, "Y": y})
def palette(index, color): return WS.block("prg32_palette_set", {"INDEX": index, "COLOR": color})
def rect_indexed(x, y, w, h, index): return WS.block("prg32_draw_rect_indexed", {"X": x, "Y": y, "W": w, "H": h, "INDEX": index})
def pixel_indexed(x, y, index): return WS.block("prg32_draw_pixel_indexed", {"X": x, "Y": y, "INDEX": index})
def clear_indexed(index): return WS.block("prg32_clear_indexed", {"INDEX": index})
def pixel(x, y, color): return WS.block("prg32_draw_pixel", {"X": x, "Y": y, "COLOR": color})
def stop_sound(channel): return WS.block("prg32_audio_stop", {"CHANNEL": channel})
def volume(value): return WS.block("prg32_audio_volume", {"VOLUME": value})
def mp_join(): return WS.block("prg32_mp_join")
def mp_share(x, y, look): return WS.block("prg32_mp_share", {"X": x, "Y": y, "LOOK": look})


def program(start, update, draw) -> dict:
    return {"blocks": {"languageVersion": 0, "blocks": [
        WS.block("prg32_on_start", inputs={"DO": start}) | {"x": 20, "y": 20},
        WS.block("prg32_update", inputs={"DO": update}) | {"x": 520, "y": 20},
        WS.block("prg32_draw", inputs={"DO": draw}) | {"x": 1120, "y": 20},
    ]}}


# ---------------------------------------------------------------------------
# Pong: the player (left paddle) against the computer (right paddle)
# ---------------------------------------------------------------------------
def pong() -> dict:
    def serve_ball(): return [
        comment("Serve: the ball starts in the middle with a random slope."),
        set_("ball_x", 157), set_("ball_y", 105), set_("ball_dy", "random(-2, 2)"),
        set_("serve_timer", 40), set_("mode", 0),
    ]
    paddle_bounce = lambda paddle_y, direction: [  # noqa: E731
        set_("ball_dx", f"{direction}min(abs(ball_dx) + 1, 7)"),
        comment("Where the ball hits the paddle decides the new angle."),
        set_("ball_dy", f"(ball_y + 3 - ({paddle_y} + 18)) / 4"),
        set_("rally", "rally + 1"),
        comment("The computer guesses where to stand; a bigger guess error makes it miss."),
        set_("cpu_error", "random(-24, 24)"),
        beep(660, 40),
    ]
    start = [
        comment("Pong: you are the left paddle, the computer plays the right paddle."),
        set_("player_y", 82), set_("cpu_y", 82), set_("player_score", 0), set_("cpu_score", 0),
        set_("ball_dx", -3), set_("rally", 0), set_("winner", 0), set_("cpu_error", 0),
        *serve_ball(),
    ]
    update = [
        comment("Mode 0 = waiting to serve, 1 = playing, 2 = game over."),
        if_("mode == 2",
            pressed("START", set_("player_score", 0), set_("cpu_score", 0), set_("winner", 0), set_("ball_dx", -3), *serve_ball())),
        comment("The player moves the left paddle with UP and DOWN."),
        held("UP", change("player_y", -4)),
        held("DOWN", change("player_y", 4)),
        keep("player_y", 20, 160),
        comment("The computer follows the ball only while it is coming towards it."),
        if_else("ball_dx > 0 && ball_x > 100",
                [set_("cpu_target", "ball_y + 3 - 18 + cpu_error")],
                [set_("cpu_target", 82)]),
        if_("cpu_y < cpu_target - 3", change("cpu_y", 3)),
        if_("cpu_y > cpu_target + 3", change("cpu_y", -3)),
        keep("cpu_y", 20, 160),
        comment("While waiting, count down to the serve."),
        if_("mode == 0", change("serve_timer", -1), if_("serve_timer <= 0", set_("mode", 1))),
        comment("Playing: move the ball, bounce it, and check for points."),
        if_("mode == 1",
            comment("Move the ball one step: new position = old position + velocity."),
            change("ball_x", "ball_dx"),
            change("ball_y", "ball_dy"),
            comment("Bounce on the top and bottom walls."),
            if_("ball_y < 20", set_("ball_y", 20), set_("ball_dy", "abs(ball_dy)"), beep(440, 20)),
            if_("ball_y > 192", set_("ball_y", 192), set_("ball_dy", "-abs(ball_dy)"), beep(440, 20)),
            comment("Paddle hits: only the paddle the ball is moving towards can hit it."),
            if_("ball_dx < 0", touching(("ball_x", "ball_y", 6, 6), (10, "player_y", 6, 36), *paddle_bounce("player_y", ""))),
            if_("ball_dx > 0", touching(("ball_x", "ball_y", 6, 6), (304, "cpu_y", 6, 36), *paddle_bounce("cpu_y", "-"))),
            comment("A point is scored when the ball leaves the court."),
            if_("ball_x < -6", change("cpu_score", 1), set_("ball_dx", -3), note(48, 1, 300), *serve_ball()),
            if_("ball_x > 320", change("player_score", 1), set_("ball_dx", 3), note(72, 1, 300), *serve_ball()),
            comment("The first player to reach 7 points wins."),
            if_("player_score == 7", set_("winner", 1), set_("mode", 2)),
            if_("cpu_score == 7", set_("winner", 2), set_("mode", 2))),
        comment("Show the player's score in the PRG32 status band."),
        band("YOU", "player_score"),
    ]
    draw = [
        comment("Painter's algorithm: clear, draw the court, then the moving objects on top."),
        clear("BLACK"),
        rect(0, 16, 320, 2, "GRAY"),
        rect(0, 198, 320, 2, "GRAY"),
        comment("The net: a dashed line made of 12 short rectangles."),
        repeat("dash", 0, 11, rect(159, "21 + dash * 15", 2, 8, "DARK_GRAY")),
        comment("Scores, labels, paddles and ball."),
        number("player_score", 120, 4, "WHITE"),
        number("cpu_score", 192, 4, "WHITE"),
        text("YOU", 8, 4, "CYAN"), text("CPU", 288, 4, "ORANGE"),
        rect(10, "player_y", 6, 36, "CYAN"),
        rect(304, "cpu_y", 6, 36, "ORANGE"),
        if_("mode != 2", rect("ball_x", "ball_y", 6, 6, "WHITE")),
        comment("Messages for the current mode."),
        if_("mode == 0", text("READY", 140, 120, "YELLOW")),
        if_("mode == 2",
            if_else("winner == 1", [text("YOU WIN!", 128, 90, "LIME")], [text("CPU WINS", 128, 90, "RED")]),
            text("PRESS START", 116, 110, "WHITE")),
    ]
    return program(start, update, draw)


# ---------------------------------------------------------------------------
# Breakout: 60 bricks in 6 coloured rows
# ---------------------------------------------------------------------------
def breakout() -> dict:
    def new_wall(): return [make_list("bricks", 60, 1), set_("bricks_left", 60)]
    def stick_ball(): return [set_("mode", 0), set_("ball_dx", 2), set_("ball_dy", -3)]
    start = [
        comment("Breakout: break every brick with the ball. A or START launches it."),
        comment("The wall: one list item per brick, 1 = still standing."),
        *new_wall(),
        comment("One colour per row, made with rgb(red, green, blue)."),
        make_list("row_color", 6, 0),
        set_item("row_color", 0, "rgb(255, 64, 64)"),
        set_item("row_color", 1, "rgb(255, 150, 40)"),
        set_item("row_color", 2, "rgb(255, 230, 40)"),
        set_item("row_color", 3, "rgb(80, 220, 80)"),
        set_item("row_color", 4, "rgb(60, 200, 255)"),
        set_item("row_color", 5, "rgb(150, 110, 255)"),
        set_("paddle_x", 140), set_("score", 0), set_("lives", 3),
        *stick_ball(),
    ]
    update = [
        comment("Mode 0 = ball on paddle, 1 = playing, 2 = game over, 3 = wall cleared."),
        comment("The player moves the paddle with LEFT and RIGHT."),
        held("LEFT", change("paddle_x", -5)),
        held("RIGHT", change("paddle_x", 5)),
        keep("paddle_x", 0, 280),
        comment("While the ball waits, it rides on the paddle; A or START launches it."),
        if_("mode == 0",
            set_("ball_x", "paddle_x + 18"), set_("ball_y", 180),
            pressed("A", set_("mode", 1)), pressed("START", set_("mode", 1))),
        comment("After a game over or a cleared wall, START plays again."),
        if_("mode >= 2",
            pressed("START",
                    if_else("mode == 2", [set_("score", 0), set_("lives", 3)], [change("lives", 1)]),
                    *new_wall(), *stick_ball())),
        comment("Playing: move the ball, then check bricks, paddle and lives."),
        if_("mode == 1",
            comment("Move the ball one step and bounce on the three walls."),
            change("ball_x", "ball_dx"),
            change("ball_y", "ball_dy"),
            if_("ball_x < 0", set_("ball_x", 0), set_("ball_dx", "abs(ball_dx)"), beep(300, 15)),
            if_("ball_x > 315", set_("ball_x", 315), set_("ball_dx", "-abs(ball_dx)"), beep(300, 15)),
            if_("ball_y < 18", set_("ball_y", 18), set_("ball_dy", "abs(ball_dy)"), beep(300, 15)),
            comment("Which brick is under the centre of the ball?"),
            set_("col", "(ball_x + 2 - 5) / 31"),
            set_("row", "(ball_y + 2 - 30) / 12"),
            if_("ball_x + 2 >= 5 && ball_y + 2 >= 30 && col < 10 && row < 6",
                if_("bricks[row * 10 + col] == 1",
                    set_item("bricks", "row * 10 + col", 0),
                    change("bricks_left", -1),
                    change("score", "(6 - row) * 10"),
                    set_("ball_dy", "-ball_dy"),
                    note("84 - row * 3", 1, 60))),
            comment("Paddle hit: the further from the centre, the steeper the bounce."),
            if_("ball_dy > 0",
                touching(("ball_x", "ball_y", 5, 5), ("paddle_x", 186, 40, 6),
                         set_("ball_dy", "-3 - (bricks_left < 30)"),
                         set_("ball_dx", "clamp((ball_x + 2 - (paddle_x + 20)) / 4, -4, 4)"),
                         if_("ball_dx == 0", set_("ball_dx", 1)),
                         beep(520, 25))),
            comment("Missing the ball costs a life."),
            if_("ball_y > 200",
                change("lives", -1), note(40, 1, 400),
                if_else("lives > 0", [*stick_ball()], [set_("mode", 2)])),
            comment("No bricks left: the wall is cleared."),
            if_("bricks_left == 0", set_("mode", 3), note(88, 1, 500))),
        comment("Show the score in the PRG32 status band."),
        band("SCORE", "score"),
    ]
    draw = [
        comment("Painter's algorithm: background, score line, bricks, paddle, ball, messages."),
        clear("BLACK"),
        text("SCORE", 4, 4, "GRAY"), number("score", 52, 4),
        text("LIVES", 248, 4, "GRAY"), number("lives", 296, 4),
        rect(0, 16, 320, 1, "DARK_GRAY"),
        comment("Brick i is drawn at column i % 10 and row i / 10, in its row colour."),
        repeat("i", 0, 59,
               if_("bricks[i] == 1",
                   rect_rgb("5 + (i % 10) * 31", "30 + (i / 10) * 12", 29, 10, "row_color[i / 10]"))),
        comment("Paddle, ball and messages."),
        rect("paddle_x", 186, 40, 6, "WHITE"),
        rect("paddle_x + 2", 187, 36, 1, "GRAY"),
        if_("mode < 2", rect("ball_x", "ball_y", 5, 5, "YELLOW")),
        if_("mode == 0", text("PRESS A", 132, 150, "CYAN")),
        if_("mode == 2", text("GAME OVER", 124, 120, "RED"), text("PRESS START", 116, 136)),
        if_("mode == 3", text("WALL CLEARED!", 108, 120, "LIME"), text("PRESS START", 116, 136)),
    ]
    return program(start, update, draw)


# ---------------------------------------------------------------------------
# Space Invaders: 5 x 8 marching invaders, shields, and a laser cannon
# ---------------------------------------------------------------------------
SQUID = [["...##...", "..####..", ".######.", "##.##.##", "########", "..#..#..", ".#.##.#.", "#.#..#.#"],
         ["...##...", "..####..", ".######.", "##.##.##", "########", ".#.##.#.", "#......#", ".#....#."]]
CRAB = [["..#..#..", "...##...", "..####..", ".##..##.", "########", "#.####.#", "#.#..#.#", "...##..."],
        ["..#..#..", "#..##..#", "#.####.#", "###..###", "########", ".######.", "..#..#..", ".#....#."]]
OCTOPUS = [["..####..", ".######.", "##.##.##", "########", ".##..##.", "##.##.##", "#......#", ".#....#."],
           ["..####..", ".######.", "##.##.##", "########", "..#..#..", ".#.##.#.", "#.#..#.#", "........"]]
CANNON = ["...##...", "...##...", ".######.", "########", "########", "########", "........", "........"]


def space_invaders() -> dict:
    def new_wave(): return [
        make_list("alive", 40, 1), set_("aliens_left", 40),
        set_("fleet_x", 24), set_("fleet_y", "28 + wave * 8"), set_("fleet_dir", 1),
        set_("march", 0), set_("march_timer", 0),
        make_list("shot_on", 3, 0),
    ]
    def restart(): return [
        set_("score", 0), set_("lives", 3), set_("wave", 0), set_("cannon_x", 152), set_("laser_on", 0),
        make_list("shield", 24, 3), *new_wave(), set_("mode", 1),
    ]
    start = [
        comment("Space Invaders: 40 invaders march down; A fires the laser cannon."),
        make_list("shot_x", 3, 0), make_list("shot_y", 3, 0),
        *restart(), set_("mode", 0),
    ]
    alien_hit = [
        comment("Which invader is the laser inside? Each one sits in a 24 x 18 cell."),
        set_("col", "(laser_x - fleet_x) / 24"),
        set_("row", "(laser_y - fleet_y) / 18"),
        if_("laser_x >= fleet_x && laser_y >= fleet_y && col < 8 && row < 5 && (laser_x - fleet_x) % 24 < 16 && (laser_y - fleet_y) % 18 < 16",
            if_("alive[row * 8 + col] == 1",
                set_item("alive", "row * 8 + col", 0),
                change("aliens_left", -1),
                change("score", "(5 - row) * 10"),
                set_("laser_on", 0),
                note(96, 2, 60))),
    ]
    shield_hit = lambda x, y, stop: [  # noqa: E731
        comment("Shields: 4 shields x 6 blocks, each block 8 x 6 pixels with 3 hit points."),
        set_("sx", f"({x} - 40) % 72"),
        set_("cell", f"(({x} - 40) / 72) * 6 + (({y} - 150) / 6) * 3 + sx / 8"),
        if_(f"{x} >= 40 && {x} < 292 && sx < 24 && {y} >= 150 && {y} < 162",
            if_("shield[cell] > 0", change_item("shield", "cell", -1), stop)),
    ]
    update = [
        comment("Mode 0 = title, 1 = playing, 2 = game over."),
        if_("mode != 1", pressed("START", *restart())),
        comment("Playing: cannon, laser, fleet, bombs, then the end-of-wave checks."),
        if_("mode == 1",
            comment("The cannon: LEFT and RIGHT move it, A fires one laser at a time."),
            held("LEFT", change("cannon_x", -3)),
            held("RIGHT", change("cannon_x", 3)),
            keep("cannon_x", 4, 300),
            if_("laser_on == 0",
                pressed("A", set_("laser_on", 1), set_("laser_x", "cannon_x + 7"), set_("laser_y", 172), beep(1200, 30))),
            comment("The laser flies up; it can hit an invader or a shield."),
            if_("laser_on == 1",
                change("laser_y", -6),
                if_("laser_y < 18", set_("laser_on", 0)),
                *alien_hit,
                *shield_hit("laser_x", "laser_y", set_("laser_on", 0))),
            comment("The fleet marches faster when fewer invaders are left."),
            change("march_timer", 1),
            if_("march_timer >= 2 + aliens_left / 3",
                set_("march_timer", 0),
                change("march", 1),
                note("36 + (march % 4)", 0, 80),
                set_("min_col", 8), set_("max_col", -1),
                repeat("i", 0, 39, if_("alive[i] == 1",
                                       set_("min_col", "min(min_col, i % 8)"),
                                       set_("max_col", "max(max_col, i % 8)"))),
                if_else("(fleet_dir > 0 && fleet_x + max_col * 24 + 16 >= 314) || (fleet_dir < 0 && fleet_x + min_col * 24 <= 4)",
                        [set_("fleet_dir", "-fleet_dir"), change("fleet_y", 8)],
                        [change("fleet_x", "fleet_dir * 4")])),
            comment("Invader bombs: up to 3 at a time, dropped by the lowest invader of a random column."),
            if_("random(0, 31) == 0",
                set_("col", "random(0, 7)"), set_("drop_row", -1),
                repeat("r", 0, 4, if_("alive[r * 8 + col] == 1", set_("drop_row", "r"))),
                if_("drop_row >= 0",
                    repeat("s", 0, 2, if_("shot_on[s] == 0 && drop_row >= 0",
                                          set_item("shot_on", "s", 1),
                                          set_item("shot_x", "s", "fleet_x + col * 24 + 7"),
                                          set_item("shot_y", "s", "fleet_y + drop_row * 18 + 16"),
                                          set_("drop_row", -1))))),
            comment("Bombs fall; they can hit a shield or the cannon."),
            repeat("s", 0, 2, if_("shot_on[s] == 1",
                                  change_item("shot_y", "s", 3),
                                  if_("shot_y[s] > 196", set_item("shot_on", "s", 0)),
                                  *shield_hit("shot_x[s]", "shot_y[s]", set_item("shot_on", "s", 0)),
                                  if_("shot_on[s] == 1 && mode == 1",
                                      touching(("shot_x[s]", "shot_y[s]", 2, 6), ("cannon_x", 176, 16, 12),
                                               set_item("shot_on", "s", 0), change("lives", -1), note(30, 1, 500),
                                               set_("cannon_x", 152),
                                               if_("lives <= 0", set_("mode", 2), save_score("score")))))),
            comment("If the invaders reach the ground, the game is over."),
            if_("fleet_y + 5 * 18 >= 176",
                comment("Find the lowest row that still has an invader."),
                set_("lowest", -1),
                repeat("i", 0, 39, if_("alive[i] == 1", set_("lowest", "max(lowest, i / 8)"))),
                if_("fleet_y + lowest * 18 + 16 >= 176", set_("mode", 2), set_("lives", 0), save_score("score"))),
            comment("All invaders gone: a new, lower wave starts."),
            if_("aliens_left == 0", change("wave", 1), if_("wave > 5", set_("wave", 5)), *new_wave())),
        comment("Show the score in the PRG32 status band."),
        band("SCORE", "score"),
    ]
    alien_pose = lambda rows, color: if_else(  # noqa: E731
        "march % 2 == 0",
        [picture(rows[0], "ax", "ay", color)],
        [picture(rows[1], "ax", "ay", color)])
    draw = [
        clear("BLACK"),
        text("SCORE", 4, 4, "GRAY"), number("score", 52, 4),
        text("LIVES", 248, 4, "GRAY"), number("lives", 296, 4),
        comment("Invader i sits at column i % 8 and row i / 8; two poses make it march."),
        repeat("i", 0, 39, if_("alive[i] == 1",
                               set_("ax", "fleet_x + (i % 8) * 24"),
                               set_("ay", "fleet_y + (i / 8) * 18"),
                               if_else("i < 8", [alien_pose(SQUID, "MAGENTA")],
                                       [if_else("i < 24", [alien_pose(CRAB, "CYAN")], [alien_pose(OCTOPUS, "YELLOW")])]))),
        comment("Shield blocks get darker as they lose hit points."),
        repeat("i", 0, 23, if_("shield[i] > 0",
                               rect_rgb("40 + (i / 6) * 72 + (i % 3) * 8", "150 + ((i % 6) / 3) * 6", 8, 6,
                                        "rgb(0, 80 + shield[i] * 55, 0)"))),
        comment("Cannon, laser, bombs and ground."),
        if_("mode == 1", picture(CANNON, "cannon_x", 176, "LIME")),
        if_("laser_on == 1", rect("laser_x", "laser_y", 2, 6, "WHITE")),
        repeat("s", 0, 2, if_("shot_on[s] == 1", rect("shot_x[s]", "shot_y[s]", 2, 6, "ORANGE"))),
        rect(0, 192, 320, 1, "GREEN"),
        if_("mode == 0", text("SPACE INVADERS", 104, 100, "LIME"), text("PRESS START", 116, 116)),
        if_("mode == 2", text("GAME OVER", 124, 100, "RED"), text("PRESS START", 116, 116)),
    ]
    return program(start, update, draw)


# ---------------------------------------------------------------------------
# Asteroids: fixed-point physics, wrap-around space, splitting rocks
# ---------------------------------------------------------------------------
def asteroids() -> dict:
    def spawn_ship(): return [set_("ship_x", 160 * 16), set_("ship_y", 100 * 16), set_("ship_vx", 0), set_("ship_vy", 0),
                  set_("angle", 0), set_("safe_timer", 60)]
    def new_wave(): return [
        make_list("rock_size", 12, 0),
        repeat("i", 0, "min(2 + wave, 7)",
               set_item("rock_size", "i", 3),
               comment("Big rocks start near the left or right edge with a random drift."),
               set_item("rock_x", "i", "(random(0, 1) * 260 + random(0, 40)) * 16"),
               set_item("rock_y", "i", "random(20, 180) * 16"),
               set_item("rock_vx", "i", "random(-12, 12)"),
               set_item("rock_vy", "i", "random(-12, 12)"),
               if_("rock_vx[i] == 0", set_item("rock_vx", "i", 7))),
    ]
    def restart(): return [set_("score", 0), set_("lives", 3), set_("wave", 1), make_list("shot_life", 4, 0),
               *spawn_ship(), *new_wave(), set_("mode", 1)]
    start = [
        comment("Asteroids: positions are in 1/16 pixel steps so the ship can drift smoothly."),
        make_list("rock_x", 12, 0), make_list("rock_y", 12, 0), make_list("rock_vx", 12, 0), make_list("rock_vy", 12, 0),
        make_list("shot_x", 4, 0), make_list("shot_y", 4, 0), make_list("shot_vx", 4, 0), make_list("shot_vy", 4, 0),
        comment("Restart: score, lives, a new ship and the first wave; then show the title."),
        *restart(), set_("mode", 0),
    ]
    split_rock = [
        comment("Split: smaller rocks give more points, then the rock becomes one size smaller."),
        set_("score", "score + 20 * (4 - rock_size[r]) * (4 - rock_size[r])"),
        change_item("rock_size", "r", -1),
        note("50 + rock_size[r] * 6", 1, 120),
        if_("rock_size[r] > 0",
            comment("Find a free slot for the second half of the rock."),
            set_("free", -1),
            repeat("j", 0, 11, if_("free < 0 && rock_size[j] == 0", set_("free", "j"))),
            if_("free >= 0",
                set_item("rock_size", "free", "rock_size[r]"),
                set_item("rock_x", "free", "rock_x[r]"),
                set_item("rock_y", "free", "rock_y[r]"),
                set_item("rock_vx", "free", "-rock_vy[r] - 4"),
                set_item("rock_vy", "free", "rock_vx[r] + 4"),
                set_item("rock_vx", "r", "rock_vy[r] + 4"),
                set_item("rock_vy", "r", "-rock_vx[free] - 4"))),
    ]
    update = [
        comment("Mode 0 = title, 1 = playing, 2 = game over."),
        if_("mode != 1", pressed("START", *restart())),
        comment("Playing: ship, bullets, rocks and collisions."),
        if_("mode == 1",
            comment("Rotate with LEFT and RIGHT: the angle is in degrees, 0 points up."),
            held("LEFT", change("angle", -8)),
            held("RIGHT", change("angle", 8)),
            wrap("angle", 0, 359),
            comment("Thrust: sin and cos give the direction, 256 means 1.0."),
            held("UP", change("ship_vx", "sin(angle) / 48"), change("ship_vy", "-cos(angle) / 48")),
            comment("Speed limit and friction, then move and wrap around the screen."),
            keep("ship_vx", -64, 64), keep("ship_vy", -64, 64),
            change("ship_vx", "-ship_vx / 40"), change("ship_vy", "-ship_vy / 40"),
            change("ship_x", "ship_vx"), change("ship_y", "ship_vy"),
            wrap("ship_x", 0, 320 * 16 - 1), wrap("ship_y", 0, 200 * 16 - 1),
            if_("safe_timer > 0", change("safe_timer", -1)),
            comment("Fire: find a free bullet slot (up to 4 bullets)."),
            pressed("A",
                    set_("free", -1),
                    repeat("j", 0, 3, if_("free < 0 && shot_life[j] == 0", set_("free", "j"))),
                    if_("free >= 0",
                        set_item("shot_life", "free", 36),
                        set_item("shot_x", "free", "ship_x + sin(angle) * 8 * 16 / 256"),
                        set_item("shot_y", "free", "ship_y - cos(angle) * 8 * 16 / 256"),
                        set_item("shot_vx", "free", "ship_vx + sin(angle) * 3 / 8"),
                        set_item("shot_vy", "free", "ship_vy - cos(angle) * 3 / 8"),
                        beep(1400, 20))),
            comment("Bullets fly for 36 frames and wrap around the screen."),
            repeat("s", 0, 3, if_("shot_life[s] > 0",
                                  change_item("shot_life", "s", -1),
                                  change_item("shot_x", "s", "shot_vx[s]"),
                                  change_item("shot_y", "s", "shot_vy[s]"),
                                  if_("shot_x[s] < 0", change_item("shot_x", "s", 320 * 16)),
                                  if_("shot_x[s] >= 320 * 16", change_item("shot_x", "s", -320 * 16)),
                                  if_("shot_y[s] < 0", change_item("shot_y", "s", 200 * 16)),
                                  if_("shot_y[s] >= 200 * 16", change_item("shot_y", "s", -200 * 16)))),
            comment("Rocks drift and wrap; count how many are left."),
            set_("rocks_left", 0),
            repeat("r", 0, 11, if_("rock_size[r] > 0",
                                   change("rocks_left", 1),
                                   change_item("rock_x", "r", "rock_vx[r]"),
                                   change_item("rock_y", "r", "rock_vy[r]"),
                                   if_("rock_x[r] < 0", change_item("rock_x", "r", 320 * 16)),
                                   if_("rock_x[r] >= 320 * 16", change_item("rock_x", "r", -320 * 16)),
                                   if_("rock_y[r] < 0", change_item("rock_y", "r", 200 * 16)),
                                   if_("rock_y[r] >= 200 * 16", change_item("rock_y", "r", -200 * 16)),
                                   set_("radius", "rock_size[r] * rock_size[r] + 4"),
                                   comment("Bullet hits: compare squared distances, no square root needed."),
                                   repeat("s", 0, 3, if_("shot_life[s] > 0 && rock_size[r] > 0",
                                                         set_("dx", "(shot_x[s] - rock_x[r]) / 16"),
                                                         set_("dy", "(shot_y[s] - rock_y[r]) / 16"),
                                                         if_("dx * dx + dy * dy <= radius * radius",
                                                             set_item("shot_life", "s", 0), *split_rock))),
                                   comment("Ship collision: the ship counts as a circle of radius 4."),
                                   if_("mode == 1 && safe_timer == 0 && rock_size[r] > 0",
                                       set_("dx", "(ship_x - rock_x[r]) / 16"),
                                       set_("dy", "(ship_y - rock_y[r]) / 16"),
                                       if_("dx * dx + dy * dy <= (radius + 4) * (radius + 4)",
                                           change("lives", -1), note(30, 1, 600),
                                           if_else("lives > 0", [*spawn_ship()], [set_("mode", 2), save_score("score")]))))),
            comment("All rocks destroyed: a bigger wave starts."),
            if_("rocks_left == 0", change("wave", 1), *new_wave(), set_("safe_timer", 60))),
        comment("Show the score in the PRG32 status band."),
        band("SCORE", "score"),
    ]
    ship_x, ship_y = "ship_x / 16", "ship_y / 16"
    nose = (f"{ship_x} + sin(angle) * 9 / 256", f"{ship_y} - cos(angle) * 9 / 256")
    left = (f"{ship_x} + sin(angle + 140) * 7 / 256", f"{ship_y} - cos(angle + 140) * 7 / 256")
    right = (f"{ship_x} + sin(angle + 220) * 7 / 256", f"{ship_y} - cos(angle + 220) * 7 / 256")
    tail = (f"{ship_x} - sin(angle) * 9 / 256", f"{ship_y} + cos(angle) * 9 / 256")
    draw = [
        comment("Rocks are two circles; bullets are 2 x 2 squares (positions divided by 16)."),
        clear("BLACK"),
        repeat("r", 0, 11, if_("rock_size[r] > 0",
                               circle("rock_x[r] / 16", "rock_y[r] / 16", "rock_size[r] * rock_size[r] + 4", "WHITE"),
                               circle("rock_x[r] / 16", "rock_y[r] / 16", "rock_size[r] * rock_size[r] + 2", "GRAY"))),
        repeat("s", 0, 3, if_("shot_life[s] > 0", rect("shot_x[s] / 16", "shot_y[s] / 16", 2, 2, "YELLOW"))),
        comment("The ship is a triangle of three lines, rotated with sin and cos; it blinks while safe."),
        if_("mode == 1 && (safe_timer == 0 || frame() % 8 < 5)",
            line(*nose, *left, "CYAN"), line(*nose, *right, "CYAN"), line(*left, *right, "CYAN"),
            held("UP", if_("frame() % 4 < 2", line(*left, *tail, "ORANGE"), line(*right, *tail, "ORANGE")))),
        comment("Score, ships left and messages."),
        text("SCORE", 4, 4, "GRAY"), number("score", 52, 4),
        text("SHIPS", 248, 4, "GRAY"), number("lives", 296, 4),
        if_("mode == 0", text("ASTEROIDS", 124, 90, "CYAN"), text("PRESS START", 116, 106)),
        if_("mode == 2", text("GAME OVER", 124, 90, "RED"), text("PRESS START", 116, 106)),
    ]
    return program(start, update, draw)


# ---------------------------------------------------------------------------
# Snake: a PRG32 tile playfield is the game board
# ---------------------------------------------------------------------------
def snake() -> dict:
    def place_food(): return [
        comment("Try random cells until an empty one is found."),
        set_("placed", 0),
        repeat("attempt", 1, 200, if_("placed == 0",
                                  set_("food_x", "random(1, 38)"), set_("food_y", "random(3, 23)"),
                                  if_("tile(0, food_x, food_y) == 0",
                                      put_tile(4, 0, "food_x", "food_y"), set_("placed", 1)))),
    ]
    def restart(): return [
        comment("New board: clear the playfield, then put wall tiles (1) all around it."),
        fill_playfield(0, 0),
        repeat("i", 0, 39, put_tile(1, 0, "i", 2), put_tile(1, 0, "i", 24)),
        repeat("i", 2, 24, put_tile(1, 0, 0, "i"), put_tile(1, 0, 39, "i")),
        comment("The body is a ring buffer: head is the newest cell, length cells back is the tail."),
        set_("head", 3), set_("length", 4),
        repeat("i", 0, 3, set_item("body_x", "i", "17 + i"), set_item("body_y", "i", 13), put_tile(2, 0, "17 + i", 13)),
        put_tile(3, 0, 20, 13),
        set_("dir_x", 1), set_("dir_y", 0), set_("next_x", 1), set_("next_y", 0),
        set_("score", 0), set_("move_timer", 0), set_("speed", 6),
        *place_food(),
    ]
    start = [
        comment("Snake: eat the apples, avoid the walls and your own tail."),
        comment("Tile 0 is the empty floor. Defining it keeps every PRG32 runtime drawing it the same way."),
        tile_define(0, ["........"] * 8, "BLACK", "BLACK"),
        comment("Tiles 1-4: wall, body, head and apple, each an 8 x 8 picture with two colours."),
        tile_define(1, ["#######.", "#######.", "#######.", "........", "###.####", "###.####", "###.####", "........"], "BROWN", "DARK_GRAY"),
        tile_define(2, [".######.", "########", "##.##.##", "########", "########", "#.##.##.", "########", ".######."], "GREEN", "BLACK"),
        tile_define(3, [".######.", "########", "#.####.#", "########", "########", "##....##", "########", ".######."], "LIME", "BLACK"),
        tile_define(4, ["....#...", "...#....", ".##.##..", "#######.", "#######.", "#######.", ".#####..", "..#.#..."], "RED", "BLACK"),
        make_list("body_x", 512, 0), make_list("body_y", 512, 0),
        *restart(),
        set_("mode", 0),
    ]
    update = [
        comment("Mode 0 = title, 1 = playing, 2 = game over."),
        if_("mode != 1", pressed("START", *restart(), set_("mode", 1))),
        comment("Playing: steer, then move one cell at a time."),
        if_("mode == 1",
            comment("Turning is allowed only sideways: the snake cannot reverse into itself."),
            held("LEFT", if_("dir_x == 0", set_("next_x", -1), set_("next_y", 0))),
            held("RIGHT", if_("dir_x == 0", set_("next_x", 1), set_("next_y", 0))),
            held("UP", if_("dir_y == 0", set_("next_x", 0), set_("next_y", -1))),
            held("DOWN", if_("dir_y == 0", set_("next_x", 0), set_("next_y", 1))),
            comment("The snake moves one cell every 'speed' frames."),
            change("move_timer", 1),
            if_("move_timer >= speed",
                set_("move_timer", 0),
                set_("dir_x", "next_x"), set_("dir_y", "next_y"),
                comment("Look at the tile in front of the head: a wall or the body ends the game."),
                set_("new_x", "body_x[head] + dir_x"),
                set_("new_y", "body_y[head] + dir_y"),
                set_("what", "tile(0, new_x, new_y)"),
                if_else("what == 1 || what == 2",
                        [set_("mode", 2), note(36, 1, 600), save_score("score")],
                        [
                            comment("Move: the old head becomes body, the new head is stored and drawn."),
                            put_tile(2, 0, "body_x[head]", "body_y[head]"),
                            set_("head", "(head + 1) % 512"),
                            set_item("body_x", "head", "new_x"),
                            set_item("body_y", "head", "new_y"),
                            put_tile(3, 0, "new_x", "new_y"),
                            comment("An apple makes the snake longer; otherwise the tail cell is erased."),
                            if_else("what == 4",
                                    [change("length", 1), change("score", 10), note("60 + length % 12", 1, 80),
                                     set_("speed", "max(2, 6 - score / 60)"), *place_food()],
                                    [set_("tail", "(head - length + 512) % 512"),
                                     put_tile(0, 0, "body_x[tail]", "body_y[tail]")]),
                        ]))),
        comment("Show the score in the PRG32 status band."),
        band("SCORE", "score"),
    ]
    draw = [
        comment("One block draws the whole board: 40 x 25 tiles of playfield layer 0."),
        draw_playfield(0),
        comment("Text is drawn on top of the tiles."),
        text("SNAKE", 4, 4, "LIME"),
        text("SCORE", 216, 4, "GRAY"), number("score", 264, 4),
        if_("mode == 0", text("PRESS START", 116, 90, "YELLOW", "DARK_GRAY")),
        if_("mode == 2", text("GAME OVER", 124, 80, "RED", "DARK_GRAY"), text("PRESS START", 116, 96, "WHITE", "DARK_GRAY")),
    ]
    return program(start, update, draw)


# ---------------------------------------------------------------------------
# Feature Tour: one screen that uses every family of blocks
# ---------------------------------------------------------------------------
def feature_tour() -> dict:
    star = ["...#....", "...#....", ".#####..", "..###...", ".##.##..", "........", "........", "........"]
    start = [
        comment("Feature Tour: every family of Construction Kit blocks on one screen."),
        splash("FEATURE TOUR", "PRG32 BLOCKS", 1200),
        volume(200),
        mp_join(),
        comment("Tiles and a scrolling playfield (layer 0) for the starry background."),
        tile_define(0, ["........"] * 8, "BLACK", "NAVY"),
        tile_define(1, star, "YELLOW", "NAVY"),
        fill_playfield(0, 0),
        repeat("i", 0, 40, put_tile(1, 0, "random(0, 63)", "random(0, 31)")),
        comment("Palette entries 16..19 make an indexed colour ramp."),
        palette(16, "RED"), palette(17, "ORANGE"), palette(18, "YELLOW"), palette(19, "LIME"),
        make_list("trail_x", 16, 160), make_list("trail_y", 16, 100),
        set_("hero_x", 152), set_("hero_y", 120), set_("p2_x", 40), set_("angle", 0), set_("beeps", 0),
    ]
    update = [
        held("LEFT", change("hero_x", -3)), held("RIGHT", change("hero_x", 3)),
        held("UP", change("hero_y", -3)), held("DOWN", change("hero_y", 3)),
        wrap("hero_x", 0, 304), keep("hero_y", 40, 176),
        held("P2_LEFT", change("p2_x", -3)), held("P2_RIGHT", change("p2_x", 3)), keep("p2_x", 0, 304),
        pressed("A", change("beeps", 1), note("60 + beeps % 12", 1, 120)),
        pressed("B", stop_sound(1)),
        change("angle", 4), wrap("angle", 0, 359),
        set_item("trail_x", "frame() % 16", "hero_x + 8"),
        set_item("trail_y", "frame() % 16", "hero_y + 8"),
        scroll_playfield(0, "frame() / 2", 0),
        camera(0, 0),
        mp_share("hero_x", "hero_y", 1),
        band("BEEPS", "beeps"),
        touching(("hero_x", "hero_y", 16, 16), ("p2_x", 176, 16, 8), set_("hero_y", 150)),
    ]
    draw = [
        draw_playfield(0),
        text("FEATURE TOUR", 4, 4, "WHITE", "NAVY"),
        text("PEERS", 232, 4, "GRAY", "NAVY"), number("peers()", 280, 4, "WHITE", "NAVY"),
        repeat("i", 0, 3, rect_indexed("8 + i * 12", 20, 10, 10, "16 + i")),
        pixel_indexed(60, 25, 18),
        pixel(64, 25, "WHITE"),
        outline(70, 18, 60, 14, "CYAN"),
        rect_rgb(72, 20, "(frame() * 2) % 56", 10, "rgb(frame() % 256, 128, 255 - frame() % 256)"),
        circle(270, 60, 14, "LIME", True),
        circle(270, 60, 18, "WHITE"),
        line(270, 60, "270 + cos(angle) * 18 / 256", "60 + sin(angle) * 18 / 256", "RED"),
        repeat("i", 0, 15, rect("trail_x[i] - 1", "trail_y[i] - 1", 2, 2, "ORANGE")),
        picture(star, "hero_x", "hero_y", "YELLOW", 2),
        sprite8(star, "p2_x", 176, "MAGENTA", "BLACK"),
        text("A: NOTE  B: STOP  P2: J/L", 64, 188, "GRAY", "NAVY"),
    ]
    return program(start, update, draw)


GAMES = [
    ("pong", "Pong", "Classic-inspired Pong: you play the left paddle with UP/DOWN, the computer plays the right paddle. First to 7 wins.",
     ["classic", "pong", "paddle", "computer-player"], pong),
    ("breakout", "Breakout", "Classic-inspired Breakout: move the paddle with LEFT/RIGHT, launch with A, clear 60 bricks in six coloured rows.",
     ["classic", "breakout", "lists", "collision"], breakout),
    ("space_invaders", "Space Invaders", "Classic-inspired Space Invaders: 40 marching invaders, shields and bombs. LEFT/RIGHT to move, A to fire.",
     ["classic", "space-invaders", "pictures", "lists"], space_invaders),
    ("asteroids", "Asteroids", "Classic-inspired Asteroids: rotate with LEFT/RIGHT, thrust with UP, fire with A. Rocks split in two.",
     ["classic", "asteroids", "fixed-point", "trigonometry"], asteroids),
    ("snake", "Snake", "Classic-inspired Snake on a PRG32 tile playfield: eat apples, grow, avoid walls and your tail.",
     ["classic", "snake", "tiles", "playfield"], snake),
]


EXTRAS = [
    ("feature_tour", "Feature Tour", "One screen that uses every family of blocks: tiles, scrolling playfield, sprites, palette, lines, circles, lists, sound, status band, multiplayer and player 2.",
     ["tour", "all-blocks", "reference"], feature_tour),
]


def build() -> list[Path]:
    global WS
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for slug, title, description, tags, make in GAMES + EXTRAS:
        WS = Workspace(slug)
        project = {
            "abi": "prg32-construction-kit-project-1.0",
            "project": {
                "title": title,
                "description": description,
                "author": "PRG32 Kit",
                "tags": tags,
                "blocks_json": make(),
            },
        }
        path = (OUT_DIR if (slug, title, description, tags, make) in GAMES else ROOT / "examples") / f"{slug}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(project, indent=1) + "\n", encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for written_path in build():
        print(written_path.relative_to(ROOT))
