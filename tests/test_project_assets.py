"""Project art in code (project_assets.py, docs/project_art.md).

A project's sprites (Sprite Lab), backgrounds (Backgrounds) and sounds (AudioStudio) are used
the same way in every kind of project:

- Blocks and PRG32 Python name them ("draw sprite rocket", prg32.sprite("rocket", x, y)); the IR
  carries the art, so the generated C and assembly are deterministic from the saved project;
- C and assembly write  #include "prg32_assets.h" / "prg32_assets.S"; the kit writes the art in
  place of that line, on that line, so every other line keeps its number;
- the include reads no file: every other include is still refused, by the server and the editor;
- the four Star Catcher examples build, and the PRG32 draws the same pixels for all four.
"""
from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest
from test_language_services import run_js
from test_sprite_palette import headless_runner

from prg32_construction_kit import project_assets as art
from prg32_construction_kit.asm_generator import ir_to_asm
from prg32_construction_kit.generator import blocks_to_ir, ir_to_c
from prg32_construction_kit.py_generator import ir_to_python
from prg32_construction_kit.python_project import PythonError, python_to_ir
from prg32_construction_kit.sample_data import ART_DIR, art_example_projects
from prg32_construction_kit.source_project import validate_asm_source, validate_c_source

ROOT = Path(__file__).resolve().parent.parent
SHIP = {"id": "1", "name": "Ship", "width": 4, "height": 2, "palette": {},
        "pixels": [["#ff0000", "transparent", "#00ff00", "#0000ff"], ["#ffffff"] * 4]}
GEM = {"id": "2", "name": "gem", "width": 4, "height": 2, "pixels": [],
       "palette": {"mode": "indexed", "colors": ["#000000", "#ffd800", "#ff0000"], "transparent_index": 0,
                   "indices": [[0, 1, 2, 1], [1, 1, 0, 0]]}}
LEVEL = {"id": "3", "kind": "background", "name": "level 1", "data": {
    "width": 3, "height": 2, "layers": [[[1, 0, 1], [1, 1, 1]], [[0, 0, 0], [0, 1, 0]]],
    "tiles": [{"id": 1, "name": "brick", "rows": [255, 129, 129, 129, 129, 129, 129, 255], "fg": "#c84c0c",
               "bg": "#000000", "flags": ["solid"]}]}}
AUDIO = {"effects": [{"name": "Jump", "voice": 0, "note": 72, "volume": 200, "duration_ms": 120}],
         "soundtracks": [{"name": "Theme"}]}
CATALOG = art.catalog([SHIP, GEM], [LEVEL], AUDIO, "Art Test")


def block(kind: str, **fields) -> dict:
    return {"type": kind, "fields": fields}


def program(start=(), draw=()) -> dict:
    def chain(blocks):
        blocks = [dict(item) for item in blocks]
        for current, following in zip(blocks, blocks[1:]):
            current["next"] = {"block": following}
        return blocks[0]
    tops = []
    for kind, body in (("prg32_on_start", start), ("prg32_update", ()), ("prg32_draw", draw)):
        tops.append({"type": kind, "inputs": {"DO": {"block": chain(body)}}} if body else {"type": kind})
    return {"blocks": {"languageVersion": 0, "blocks": tops}}


ART_BLOCKS = program(start=[block("prg32_background_load", BACKGROUND="level 1")],
                     draw=[block("prg32_background_draw", BACKGROUND="level 1"),
                           block("prg32_draw_project_sprite", SPRITE="Ship", X="10", Y="20"),
                           block("prg32_draw_project_sprite", SPRITE="gem", X="x + 1", Y="40")])


# --- the catalog --------------------------------------------------------------------------------

def test_every_piece_of_art_gets_its_own_c_name_in_a_fixed_order():
    assert [item["name"] for item in CATALOG["sprites"]] == ["ship", "gem"] or \
        [item["name"] for item in CATALOG["sprites"]] == ["gem", "ship"]
    assert [item["name"] for item in CATALOG["backgrounds"]] == ["level_1"]
    assert [item["name"] for item in CATALOG["effects"]] == ["sfx_jump"]
    assert [item["name"] for item in CATALOG["soundtracks"]] == ["TRACK_THEME"]
    twins = art.catalog([{**SHIP, "id": "a"}, {**SHIP, "id": "b"}], [{**LEVEL, "name": "Ship"}], None, "Art Test")
    names = [item["name"] for item in twins["sprites"] + twins["backgrounds"]]
    assert len(set(names)) == 3 and names[0] == "ship"
    # Never the game's own entry names, never a firmware name.
    clash = art.catalog([{**SHIP, "name": "Art Test"}, {**SHIP, "id": "9", "name": "prg32_gfx_clear"}], [], None, "Art Test")
    assert {item["name"] for item in clash["sprites"]} == {"my_art_test", "my_prg32_gfx_clear"}
    assert art.catalog(list(reversed([SHIP, GEM])), [LEVEL], AUDIO, "Art Test") == CATALOG


def test_a_damaged_sprite_or_background_is_left_out_and_named():
    broken = art.catalog([{**GEM, "palette": {"mode": "indexed", "colors": []}}],
                         [{**LEVEL, "data": {"width": 0}}], None, "x")
    assert broken["sprites"] == [] and broken["backgrounds"] == [] and broken["skipped"] == ["gem", "level 1"]


def test_the_see_through_colour_is_never_a_colour_the_sprite_paints():
    magenta = {**SHIP, "pixels": [["#ff00ff", "transparent", "#ff00ff", "#ff00ff"], ["#ffffff"] * 4]}
    header = art.c_header(art.catalog([magenta], [], None, "x"))
    assert "0xF81F" in header and "prg32_sprite_draw_frame(x, y, 4, 2, ship_pixels, 0, 0xF81E);" in header


def test_features_follow_the_art():
    assert art.features(CATALOG) == {"sprites", "tilemap", "platformer", "audio"}
    assert art.features(art.catalog([SHIP], [], None, "x")) == {"sprites"}


# --- C and assembly projects: the include line --------------------------------------------------

C_GAME = '''#include "prg32.h"
/* #include "prg32_assets.h" in a comment changes nothing */
#include "prg32_assets.h"
void art_test_init(void) { level_1_load(); }
void art_test_update(void) { }
void art_test_draw(void) { level_1_draw(); ship_draw(10, 20); gem_draw(30, 40); sfx_jump(); prg32_audio_play_track(TRACK_THEME); }
'''
ASM_GAME = (ART_DIR / "star_catcher.S").read_text()


def test_the_include_becomes_the_art_on_that_same_line():
    built = art.expand_c(C_GAME, CATALOG)
    before, after = C_GAME.splitlines(), built.splitlines()
    assert len(before) == len(after)
    changed = [number for number, (old, new) in enumerate(zip(before, after)) if old != new]
    assert changed == [2]                                   # only the include line, not the comment
    line = after[2]
    assert "void ship_draw(int x, int y)" in line and "void level_1_load(void)" in line and "TRACK_THEME = 0" in line
    assert "/*" not in line and "//" not in line and "#" not in line
    assert art.expand_c(C_GAME.replace('#include "prg32_assets.h"\n', ""), CATALOG) == \
        C_GAME.replace('#include "prg32_assets.h"\n', "")
    asm = art.expand_asm(ASM_GAME, art.catalog([], [], None, "x"))
    assert len(asm.splitlines()) == len(ASM_GAME.splitlines()) and "prg32_assets" not in asm.split("*/", 1)[1]


def test_the_assembly_include_keeps_the_section_and_has_no_comment():
    built = art.expand_asm(ASM_GAME, CATALOG)
    line = next(line for line in built.splitlines() if "ship_draw:" in line)
    assert line.startswith(".pushsection .rodata") and line.rstrip().endswith(".popsection")
    assert "#" not in line and "/*" not in line
    assert len(built.splitlines()) == len(ASM_GAME.splitlines())


def test_the_include_must_be_written_once_on_its_own_line_below_prg32_h():
    assert art.check_include(C_GAME, "c") and not art.check_include("#include \"prg32.h\"\n", "c")
    for wrong, why in ((C_GAME + '#include "prg32_assets.h"\n', "only once"),
                       (C_GAME.replace('#include "prg32_assets.h"', '#include "prg32_assets.h" /* art */'), "own"),
                       ('#include "prg32_assets.h"\n' + C_GAME.replace('#include "prg32_assets.h"\n', ""), "above")):
        with pytest.raises(art.AssetsError, match=why):
            art.check_include(wrong, "c")
    assert art.check_include(ASM_GAME, "asm")


def test_the_validators_accept_the_art_include_and_nothing_else():
    validate_c_source(C_GAME, "Art Test")
    validate_asm_source(ASM_GAME, "Star Catcher (Assembly)")
    for line in ('#include "game.S"', '#include "/etc/passwd"', '.include "prg32_assets.S"', '.incbin "prg32_assets.S"',
                 '#include "prg32_assets.S" // more', '#include "prg32_assets.h"', '#  include_next "prg32_assets.S"'):
        with pytest.raises(ValueError):
            validate_asm_source(ASM_GAME.replace('#include "prg32_assets.S"', line), "Star Catcher (Assembly)")
    with pytest.raises(ValueError):
        validate_c_source(C_GAME.replace("prg32_assets.h", "prg32_assets.S"), "Art Test")


def test_the_editor_checks_agree_with_the_server():
    sources = {
        "ok-asm": ("asm", ASM_GAME, "Star Catcher (Assembly)"),
        "bad-asm": ("asm", ASM_GAME.replace('#include "prg32_assets.S"', '#include "prg32_assets.S" // x'),
                    "Star Catcher (Assembly)"),
        "ok-c": ("c", (ART_DIR / "star_catcher.c").read_text(), "Star Catcher (C)"),
    }
    answers = run_js([{"op": "diagnostics", "language": lang, "source": text, "title": title}
                      for lang, text, title in sources.values()])
    errors = {name: [p for p in answer if p["severity"] == "error"] for name, answer in zip(sources, answers)}
    assert errors["ok-asm"] == [] and errors["ok-c"] == []
    assert "asm-file-access" in [p["code"] for p in errors["bad-asm"]]   # as for any other include


# --- Blocks and PRG32 Python: the IR carries the art ---------------------------------------------

def test_blocks_name_the_art_and_the_ir_carries_only_what_they_use():
    ir = blocks_to_ir(ART_BLOCKS, {"title": "Art Test", "assets": CATALOG})
    assert ir["warnings"] == [] and set(ir["required_features"]) >= {"sprites", "tilemap", "platformer"}
    assert [stmt["op"] for stmt in ir["draw"]] == ["background_draw", "sprite_draw", "sprite_draw"]
    assert {item["name"] for item in ir["assets"]["sprites"]} == {"ship", "gem"}
    only_ship = blocks_to_ir(program(draw=[block("prg32_draw_project_sprite", SPRITE="Ship", X="1", Y="2")]),
                             {"title": "Art Test", "assets": CATALOG})
    assert [item["name"] for item in only_ship["assets"]["sprites"]] == ["ship"] and only_ship["assets"]["backgrounds"] == []
    assert "assets" not in blocks_to_ir(program(draw=[block("prg32_clear_screen", COLOR="BLACK")]), {"title": "x"})


def test_a_missing_sprite_is_a_warning_never_a_guess():
    ir = blocks_to_ir(program(draw=[block("prg32_draw_project_sprite", SPRITE="Nope", X="1", Y="2")]),
                      {"title": "Art Test", "assets": CATALOG})
    assert ir["warnings"] == ["The sprite 'Nope' is not in this project"] and "assets" not in ir
    assert ir["draw"][0]["op"] == "comment"


def test_c_and_assembly_make_the_same_art_calls():
    ir = blocks_to_ir(ART_BLOCKS, {"title": "Art Test", "assets": CATALOG})
    c, asm = ir_to_c(ir), ir_to_asm(ir)
    assert "void ship_draw(int x, int y)" in c and "ship_draw(10, 20);" in c and "gem_draw(x + 1, 40);" in c
    assert "ship_draw:" in asm and "call  ship_draw" in asm and "call  level_1_load" in asm
    for firmware in ("prg32_sprite_draw_frame", "prg32_sprite_draw_indexed", "prg32_tile_define",
                     "prg32_platform_tile_flags", "prg32_playfield_put", "prg32_playfield_draw"):
        assert firmware in c and firmware in asm
    assert "sfx_jump" not in c   # Blocks play sounds with their own blocks: no sound functions here
    assert ir_to_c(ir) == c and ir_to_asm(ir) == asm


def test_python_names_the_art_like_the_blocks():
    ir = blocks_to_ir(ART_BLOCKS, {"title": "Art Test", "assets": CATALOG})
    python = ir_to_python(ir)
    assert 'prg32.sprite("Ship", 10, 20)' in python and 'prg32.background_load("level 1")' in python
    again = python_to_ir(python, {"title": "Art Test", "assets": CATALOG})
    assert again["assets"] == ir["assets"]
    assert [s for s in again["draw"] if s["op"] != "comment"] == ir["draw"]
    with pytest.raises(PythonError, match="no sprite named 'Nope'"):
        python_to_ir(python.replace('"Ship"', '"Nope"'), {"title": "Art Test", "assets": CATALOG})


def test_the_simulator_reads_the_art_blocks_into_the_same_ir():
    from test_examples import run_node
    script = (f"window.PRG32Simulator.setArt({json.dumps(CATALOG)});"
              f"const ir = window.PRG32Simulator.compileBlocks({json.dumps(ART_BLOCKS)});"
              "console.log(JSON.stringify({init: ir.init, draw: ir.draw, assets: ir.assets}));")
    js = json.loads(run_node(script))
    ir = blocks_to_ir(ART_BLOCKS, {"title": "Art Test", "assets": CATALOG})
    assert js == {"init": ir["init"], "draw": ir["draw"], "assets": ir["assets"]}


def test_a_blocks_game_converted_to_code_keeps_following_the_art():
    from prg32_construction_kit.sample_data import blocks_as_code

    project = {"title": "Art Test", "blocks_json": ART_BLOCKS, "assets": CATALOG}
    c = blocks_as_code(project, "c")["source_c"]
    asm = blocks_as_code(project, "asm")["source_asm"]
    assert '#include "prg32_assets.h"' in c and "ship_pixels" not in c
    assert '#include "prg32_assets.S"' in asm and "ship_pixels" not in asm
    validate_c_source(c, "Art Test")
    validate_asm_source(asm, "Art Test")
    assert art.check_include(c, "c") and art.check_include(asm, "asm")


# --- through the API ----------------------------------------------------------------------------

def make_art_project(client, title: str, game_json: dict, blocks_json: dict | None = None) -> str:
    project = client.post("/api/projects", json={"title": title, "blocks_json": blocks_json or {},
                                                 "game_json": game_json}).get_json()
    for sprite in (SHIP, GEM):
        client.post("/api/sprites", json={**{k: v for k, v in sprite.items() if k != "id"}, "project_id": project["id"]})
    client.post("/api/assets", json={"project_id": project["id"], "kind": "background", "name": "level 1",
                                     "content_type": "application/json", "data": LEVEL["data"]})
    return project["id"]


def test_the_art_route_gives_the_files_and_the_line_for_each_language(client):
    project_id = make_art_project(client, "Art Test", {})
    answer = client.get(f"/api/projects/{project_id}/art").get_json()
    assert {item["title"] for item in answer["catalog"]["sprites"]} == {"Ship", "gem"}
    assert "void ship_draw(int x, int y)" in answer["c_header"] and "ship_draw:" in answer["asm_include"]
    ship = next(item for item in answer["usage"]["sprites"] if item["title"] == "Ship")
    assert ship["c"] == "ship_draw(10, 20);" and ship["python"] == 'prg32.sprite("Ship", 10, 20)'
    assert answer["files"] == {"c": "prg32_assets.h", "asm": "prg32_assets.S"}
    assert client.get("/api/projects/nope/art").status_code == 404


def test_a_c_project_builds_its_art_through_the_include(client):
    project_id = make_art_project(client, "Art Test", {"source_mode": "c", "source_c": C_GAME.replace("sfx_jump(); ", "")
                                                       .replace("prg32_audio_play_track(TRACK_THEME); ", "")})
    answer = client.post(f"/api/projects/{project_id}/convert", json={"source_language": "c"}).get_json()
    assert "void ship_draw(int x, int y)" in answer["c_source"]
    assert {"sprites", "tilemap", "platformer"} <= set(answer["game_ir"]["required_features"])
    assert answer["game_ir"]["source_c"] == client.get(f"/api/projects/{project_id}").get_json()["game_json"]["source_c"]
    wrong = client.put(f"/api/projects/{project_id}", json={"game_json": {"source_mode": "c", "source_c":
                       C_GAME.replace('#include "prg32_assets.h"', '#include "prg32_assets.h" /* x */')}}).get_json()
    refused = client.post(f"/api/projects/{project_id}/convert", json={}).get_json()
    assert wrong["id"] == project_id and "on a line of its own" in refused["error"]


def test_examples_bring_their_art_and_sound(client):
    listed = {item["slug"]: item for item in client.get("/api/examples").get_json()["examples"]}
    assert {listed[slug]["language"] for slug in ("star_catcher_blocks", "star_catcher_python", "star_catcher_c",
                                                  "star_catcher_asm")} == {"blocks", "python", "c", "asm"}
    for item in art_example_projects():
        project = client.post(f"/api/examples/{item['slug']}/import").get_json()
        sprites = client.get(f"/api/sprites?project_id={project['id']}").get_json()["sprites"]
        backgrounds = client.get(f"/api/assets?project_id={project['id']}&kind=background").get_json()["assets"]
        audio = client.get(f"/api/projects/{project['id']}/audio").get_json()
        assert {sprite["name"] for sprite in sprites} == {"rocket", "star"} and [b["name"] for b in backgrounds] == ["sky"]
        assert [effect["name"] for effect in audio["document"]["effects"]] == ["Coin"] and audio["version"] == 1
        converted = client.post(f"/api/projects/{project['id']}/convert", json={}).get_json()
        assert converted.get("game_ir", {}).get("warnings") == [], (item["slug"], converted.get("error"))


def test_the_art_examples_are_up_to_date():
    before = {name: (ART_DIR / name).read_text() for name in ("star_catcher.art.json", "star_catcher.blocks.json")}
    subprocess.run(["python3", str(ROOT / "tools" / "build_art_examples.py")], check=True, capture_output=True)
    assert {name: (ART_DIR / name).read_text() for name in before} == before


def test_guests_use_their_art_without_storing_it(anon, app):
    app.config["LOGIN_REQUIRED"] = False
    kit = {"X-PRG32-Kit": "1"}
    body = {"title": "Art Test", "sprites": [SHIP, GEM], "backgrounds": [{"name": "level 1", "data": LEVEL["data"]}]}
    answer = anon.post("/api/guest/art", json=body, headers=kit)
    assert answer.status_code == 200 and "level_1_load" in answer.get_json()["c_header"]
    converted = anon.post("/api/guest/convert", json={**body, "project": {"title": "Art Test", "blocks_json": ART_BLOCKS}},
                          headers=kit)
    assert "void ship_draw(int x, int y)" in converted.get_json()["c_source"]
    example = anon.get("/api/guest/examples/star_catcher_c", headers=kit).get_json()
    assert {sprite["name"] for sprite in example["sprites"]} == {"rocket", "star"} and example["audio_studio"]["effects"]
    too_many = anon.post("/api/guest/art", json={"sprites": [SHIP] * 65}, headers=kit)
    assert too_many.status_code == 400


# --- the PRG32 draws it -------------------------------------------------------------------------

def test_the_prg32_draws_the_same_star_catcher_in_every_language(client, tmp_path):
    from prg32_construction_kit.build_check import builds_available

    runner = headless_runner()
    if not builds_available(client.application.config["PRG32_BUILD_COMMAND"]) or runner is None:
        pytest.skip("needs the PRG32 toolchain and prg32qt-headless")
    frames = {}
    for item in art_example_projects():
        project = client.post(f"/api/examples/{item['slug']}/import").get_json()
        built = client.post(f"/api/projects/{project['id']}/package", json={"architectures": ["qemu"]}).get_json()
        assert built["cartridge_artifacts"], built.get("build", {}).get("log")
        cartridge = tmp_path / f"{item['slug']}.prg32"
        cartridge.write_bytes(client.get(f"/api/artifacts/{built['cartridge_artifacts'][0]['id']}/download").data)
        ppm = tmp_path / f"{item['slug']}.ppm"
        subprocess.run([str(runner), str(cartridge), "10", "--dump-ppm", str(ppm)], check=True, capture_output=True,
                       timeout=60)
        frames[item["language"]] = ppm.read_bytes()
    data = frames["c"]
    header_end = data.index(b"\n", data.index(b"\n", data.index(b"\n") + 1) + 1) + 1
    width, height = (int(value) for value in data.split(b"\n")[1].split())
    top = (height - 200) // 2 if height > 200 else 0

    def pixel(x, y):
        at = header_end + ((y + top) * width + x) * 3
        return tuple(data[at:at + 3])

    assert pixel(159, 160)[0] > 200 and pixel(159, 160)[2] > 200        # the rocket's white tip
    sky = pixel(152, 161)                                                 # a see-through rocket pixel shows the sky
    assert sky[2] > 60 and sky[0] < 40
    assert pixel(100, 176)[1] > 150                                       # the grass tile
    assert pixel(100, 23)[0] > 200 and pixel(100, 23)[1] > 180            # the star (palette entry 1, yellow)
    assert frames["blocks"] == frames["python"] == frames["c"] == frames["asm"]


def test_archive_of_an_art_example_keeps_the_art(client):
    project = client.post("/api/examples/star_catcher_python/import").get_json()
    archive = client.get(f"/api/projects/{project['id']}/archive").data
    imported = client.post("/api/projects/import", data={"file": (io.BytesIO(archive), "star.prg32project.zip")},
                           content_type="multipart/form-data").get_json()
    assert client.post(f"/api/projects/{imported['id']}/convert", json={}).get_json()["game_ir"]["warnings"] == []
