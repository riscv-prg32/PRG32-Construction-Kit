"""Backgrounds: tiles and playfield maps, checked, saved, archived and turned into C (backgrounds.py).

The last test compiles the generated C with the real PRG32 toolchain, loads the background and
draws its playfield in PRG32-QT's headless runner, then reads the pixels back: the tile bits,
colours and map positions are what the PRG32 itself draws. It skips without the toolchain or
the runner.
"""

from __future__ import annotations

import io
import subprocess

import pytest

from prg32_construction_kit import backgrounds as bg
from test_sprite_palette import headless_runner

BRICK = {"id": 1, "name": "brick", "rows": [255, 129, 129, 255, 255, 24, 24, 255], "fg": "#ff0000", "bg": "#000000",
         "flags": ["solid"]}
HALF = {"id": 2, "name": "half", "rows": [240] * 8, "fg": "#ffff00", "bg": "#0000ff", "flags": []}


def level(width=3, height=2):
    return {"width": width, "height": height, "tiles": [BRICK, HALF],
            "layers": [[[1, 0, 2], [2, 2, 1]][:height] if height == 2 else [[1] * width] * height]}


def test_a_background_is_checked_like_the_prg32_reads_it():
    checked = bg.checked(level())
    assert checked["tiles"][0]["flags"] == ["solid"] and checked["layers"][0][0] == [1, 0, 2]
    for change in ({"width": 65}, {"height": 0}, {"tiles": [{**BRICK, "id": 0}]}, {"tiles": [BRICK, {**BRICK}]},
                   {"tiles": [{**BRICK, "rows": [1] * 7}]}, {"tiles": [{**BRICK, "fg": "red"}]},
                   {"tiles": [{**BRICK, "flags": ["bouncy"]}]}, {"layers": []}, {"layers": [[[1, 0, 2]]]},
                   {"layers": [[[1, 0, 9], [2, 2, 1]]]}):
        with pytest.raises(bg.BackgroundError) as refused:
            bg.checked({**level(), **change})
        assert refused.value.args[0].key.startswith("server.background."), change


def test_the_c_defines_the_tiles_and_fills_the_playfield():
    source = bg.to_c("Level 1", level())
    assert "static const uint8_t level_1_tile_ids[2] = { 1, 2 };" in source
    assert "{ 0xFF, 0x81, 0x81, 0xFF, 0xFF, 0x18, 0x18, 0xFF },  /* 1: brick */" in source
    assert "{ 0xF800, 0x0000 },  /* #ff0000 on #000000 */" in source
    assert "static const uint8_t level_1_tile_flags[2] = { 1, 0 };" in source and "platformer feature" in source
    assert "static const uint8_t level_1_layer0[2][3] = {\n    { 1, 0, 2 },\n    { 2, 2, 1 }\n};" in source
    assert "prg32_tile_define(level_1_tile_ids[i], level_1_tiles[i]" in source
    assert "prg32_playfield_put(0, (uint8_t)x, (uint8_t)y, level_1_layer0[y][x]);" in source
    plain = bg.to_c("plain", {**level(), "tiles": [{**BRICK, "flags": []}, HALF]})
    assert "tile_flags" not in plain and "prg32_platform_tile_flags" not in plain


def test_backgrounds_are_assets_saved_checked_converted_and_archived(client):
    project = client.post("/api/projects", json={"title": "Tiles", "blocks_json": {}}).get_json()
    asset = client.post("/api/assets", json={"project_id": project["id"], "kind": "background", "name": "level",
                                             "content_type": "application/json", "data": level()}).get_json()
    assert asset["data"]["tiles"][1]["name"] == "half"
    bad = client.put(f"/api/assets/{asset['id']}", json={"kind": "background", "data": {**level(), "width": 99},
                                                         "expected_version": asset.get("version", 0)})
    assert bad.status_code == 400 and bad.get_json()["message_key"].startswith("server.background.the_map")
    converted = client.post(f"/api/assets/{asset['id']}/convert", json={}).get_json()
    assert "void level_load(void)" in converted["c_source"] and converted["artifact"]["kind"] == "background_c_source"
    data = client.get(f"/api/projects/{project['id']}/archive").data
    imported = client.post("/api/projects/import", data={"file": (io.BytesIO(data), "tiles.prg32project.zip")},
                           content_type="multipart/form-data").get_json()
    copies = client.get(f"/api/assets?project_id={imported['id']}&kind=background").get_json()["assets"]
    assert len(copies) == 1 and copies[0]["data"] == asset["data"]


def test_guests_convert_backgrounds_too(anon, app):
    app.config["LOGIN_REQUIRED"] = False
    answer = anon.post("/api/guest/backgrounds/convert", json={"background": {"name": "level", "data": level()}},
                       headers={"X-PRG32-Kit": "1"})
    assert answer.status_code == 200 and "void level_load(void)" in answer.get_json()["c_source"]
    refused = anon.post("/api/guest/backgrounds/convert", json={"background": {"name": "level", "data": {"width": 0}}},
                        headers={"X-PRG32-Kit": "1"})
    assert refused.status_code == 400


def test_the_prg32_draws_the_generated_background(client, tmp_path):
    from prg32_construction_kit.build_check import builds_available

    runner = headless_runner()
    if not builds_available(client.application.config["PRG32_BUILD_COMMAND"]) or runner is None:
        pytest.skip("needs the PRG32 toolchain and prg32qt-headless")
    background = bg.to_c("level", {**level(), "tiles": [{**BRICK, "flags": []}, HALF]})
    body = background.split('#include "prg32.h"\n', 1)[1]
    source = ('#include "prg32.h"\n#include <stdint.h>\n' + body +
              "void tile_check_init(void) { level_load(); }\nvoid tile_check_update(void) {}\n"
              "void tile_check_draw(void) {\n    prg32_gfx_clear(PRG32_COLOR_BLACK);\n    prg32_playfield_draw(0, 0);\n}\n")
    project = client.post("/api/projects", json={"title": "Tile Check", "game_json": {
        "source_mode": "c", "source_c": source, "required_features": ["tilemap"]}}).get_json()
    built = client.post(f"/api/projects/{project['id']}/package", json={"architectures": ["qemu"]}).get_json()
    assert built["cartridge_artifacts"], built.get("build", {}).get("log")
    cartridge = tmp_path / "check.prg32"
    cartridge.write_bytes(client.get(f"/api/artifacts/{built['cartridge_artifacts'][0]['id']}/download").data)
    ppm = tmp_path / "frame.ppm"
    subprocess.run([str(runner), str(cartridge), "10", "--dump-ppm", str(ppm)], check=True, capture_output=True, timeout=60)
    data = ppm.read_bytes()
    header_end = data.index(b"\n", data.index(b"\n", data.index(b"\n") + 1) + 1) + 1
    width, height = (int(value) for value in data.split(b"\n")[1].split())
    top = (height - 200) // 2 if height > 200 else 0          # the 320x200 game area inside the screen

    def pixel(x, y):
        at = header_end + ((y + top) * width + x) * 3
        return tuple(data[at:at + 3])

    red, black = pixel(0, 0), pixel(1, 1)                     # brick at (0, 0): row 0 all on, row 1 only its edges
    assert red[0] > 200 and red[1] < 60 and black == (0, 0, 0) and pixel(7, 1)[0] > 200
    yellow, blue = pixel(16, 0), pixel(20, 0)                 # "half" at map (2, 0): left 4 pixels on, right 4 off
    assert yellow[0] > 200 and yellow[1] > 200 and blue[2] > 200 and blue[0] < 60
    assert pixel(8, 0) == (0, 0, 0)                           # map (1, 0) is empty
