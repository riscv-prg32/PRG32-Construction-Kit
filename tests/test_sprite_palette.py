"""Indexed-colour sprites: palettes, packing, the API, the archive and the C (sprite_palette.py).

The last test compiles the generated C with the real PRG32 toolchain into an Advanced C cartridge
that draws the sprite, runs it in PRG32-QT's headless runner and reads the drawn pixels back:
the palette, the packing and the transparent entry are what the PRG32 itself draws. It skips
when the toolchain or the runner is missing.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from prg32_construction_kit import sprite_palette as sp
from prg32_construction_kit.generator import sprite_to_c

ROOT = Path(__file__).resolve().parent.parent
PALETTE = {"mode": "indexed", "colors": ["#000000", "#ffd800", "#ff0000"], "transparent_index": 0,
           "indices": [[0, 1, 2, 1], [1, 1, 1, 1]]}


def test_bits_per_pixel_is_the_smallest_prg32_packing():
    assert [sp.bits_per_pixel(count) for count in (1, 2, 3, 4, 5, 16, 17, 256)] == [1, 1, 2, 2, 4, 4, 8, 8]
    with pytest.raises(sp.PaletteError):
        sp.bits_per_pixel(257)


@pytest.mark.parametrize("colors, indices, expected", [
    (2, [[1, 0, 1, 1, 0, 0, 0, 1], [1, 1, 1, 1, 1, 1, 1, 1]], b"\xb1\xff"),         # 1 bit: 10110001 11111111
    (3, [[0, 1, 2, 1], [1, 1, 1, 1]], b"\x19\x55"),                                    # 2 bits: 00 01 10 01 ...
    (16, [[15, 0, 1], [2, 3, 4]], b"\xf0\x12\x34"),                                    # 4 bits, across rows
    (16, [[7, 8, 9]], b"\x78\x90"),                                                    # odd count: last nibble padded
    (256, [[255, 1]], b"\xff\x01"),                                                    # 8 bits
])
def test_indices_are_packed_densely_most_significant_first(colors, indices, expected):
    palette = {"mode": "indexed", "colors": ["#000000"] * colors, "transparent_index": -1, "indices": indices}
    assert sp.packed(sp.checked(palette, len(indices[0]), len(indices))) == expected


@pytest.mark.parametrize("change", [
    {"mode": "rgb"}, {"colors": []}, {"colors": ["#00000"] * 3}, {"colors": ["#000000"] * 257},
    {"transparent_index": 3}, {"transparent_index": True}, {"indices": [[0, 1, 2, 1]]},
    {"indices": [[0, 1, 2, 3], [1, 1, 1, 1]]}, {"indices": [[0, 1, 2, -1], [1, 1, 1, 1]]},
])
def test_a_wrong_palette_is_refused_with_a_reason(change):
    with pytest.raises(sp.PaletteError) as refused:
        sp.checked({**PALETTE, **change}, 4, 2)
    assert refused.value.args[0].key.startswith("server.sprite.")


def test_the_pixels_are_made_from_the_palette_and_the_transparent_entry():
    assert sp.pixels_of(sp.checked(PALETTE, 4, 2)) == [["transparent", "#ffd800", "#ff0000", "#ffd800"], ["#ffd800"] * 4]
    assert sp.checked({}, 4, 2) == {} and sp.checked(None, 4, 2) == {}


def test_an_indexed_sprite_becomes_its_palette_indices_and_descriptor_in_c():
    source = sprite_to_c({"name": "Ship", "width": 4, "height": 2, "palette": PALETTE})
    assert "static const uint16_t ship_palette[3] = {\n    0x0000, 0xFEC0, 0xF800  /* #000000, #ffd800, #ff0000 */\n};" in source
    assert "static const uint8_t ship_indices[2] = {\n    0x19, 0x55\n};" in source
    assert "ship_indices, ship_palette, 4, 2, 1, 3, PRG32_SPRITE_BPP_2, 0" in source
    assert "entry 0 is transparent" in source and "(8 pixels in 2 bytes instead of 16)" in source
    direct = sprite_to_c({"name": "Ship", "width": 1, "height": 1, "pixels": [["#ff0000"]]})
    assert "static const uint16_t ship_pixels[1]" in direct and "palette" not in direct


def test_the_api_keeps_the_palette_and_makes_the_pixels(client):
    sprite = client.post("/api/sprites", json={"name": "ship", "width": 4, "height": 2, "pixels": [],
                                               "palette": PALETTE}).get_json()
    assert sprite["palette"]["colors"] == PALETTE["colors"] and sprite["pixels"][0][0] == "transparent"
    bad = client.put(f"/api/sprites/{sprite['id']}", json={"width": 4, "height": 2, "palette": {**PALETTE, "colors": ["red"]}})
    assert bad.status_code == 400 and bad.get_json()["message_key"].startswith("server.sprite.palette_colours")
    converted = client.post(f"/api/sprites/{sprite['id']}/convert", json={}).get_json()
    assert "prg32_indexed_sprite_t ship_sprite" in converted["c_source"]
    direct = client.post("/api/sprites", json={"name": "plain", "width": 1, "height": 1, "pixels": [["#ff0000"]]}).get_json()
    assert direct["palette"] == {}


def test_guests_convert_indexed_sprites_too(anon, app):
    app.config["LOGIN_REQUIRED"] = False
    answer = anon.post("/api/guest/sprites/convert", json={"sprite": {"name": "ship", "width": 4, "height": 2,
                                                                       "palette": PALETTE}},
                       headers={"X-PRG32-Kit": "1"})
    assert answer.status_code == 200 and "PRG32_SPRITE_BPP_2" in answer.get_json()["c_source"]


def test_the_archive_keeps_indexed_sprites(client):
    project = client.post("/api/projects", json={"title": "Palette Game", "blocks_json": {}}).get_json()
    client.post("/api/sprites", json={"project_id": project["id"], "name": "ship", "width": 4, "height": 2,
                                      "pixels": [], "palette": PALETTE})
    data = client.get(f"/api/projects/{project['id']}/archive").data
    imported = client.post("/api/projects/import", data={"file": (io.BytesIO(data), "game.prg32project.zip")},
                           content_type="multipart/form-data").get_json()
    sprite = client.get(f"/api/sprites?project_id={imported['id']}").get_json()["sprites"][0]
    assert sprite["palette"] == {**PALETTE, "colors": PALETTE["colors"]} and sprite["pixels"][0][1] == "#ffd800"


def headless_runner() -> Path | None:
    for candidate in (os.environ.get("PRG32QT_HEADLESS"), ROOT.parent / "PRG32-QT" / "build-core" / "prg32qt-headless",
                      ROOT.parent / "PRG32-QT" / "build-macos" / "prg32qt-headless"):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return shutil.which("prg32qt-headless") and Path(shutil.which("prg32qt-headless"))


def test_the_prg32_draws_the_generated_indexed_sprite(client, tmp_path):
    from prg32_construction_kit.build_check import builds_available

    runner = headless_runner()
    if not builds_available(client.application.config["PRG32_BUILD_COMMAND"]) or runner is None:
        pytest.skip("needs the PRG32 toolchain and prg32qt-headless")
    sprite_c = sprite_to_c({"name": "ship", "width": 4, "height": 2, "palette": PALETTE})
    body = sprite_c.split('#include "prg32.h"\n', 1)[1]
    source = ('#include "prg32.h"\n#include <stdint.h>\n' + body.replace("#include <stdint.h>\n", "") +
              "void palette_check_init(void) {}\nvoid palette_check_update(void) {}\n"
              "void palette_check_draw(void) {\n    prg32_gfx_clear(PRG32_COLOR_BLUE);\n"
              "    prg32_sprite_draw_indexed(10, 20, &ship_sprite, 0);\n}\n")
    project = client.post("/api/projects", json={"title": "Palette Check", "game_json": {
        "source_mode": "c", "source_c": source, "required_features": ["sprites"]}}).get_json()
    built = client.post(f"/api/projects/{project['id']}/package", json={"architectures": ["qemu"]}).get_json()
    assert built["cartridge_artifacts"], built.get("build", {}).get("log")
    cartridge = tmp_path / "check.prg32"
    cartridge.write_bytes(client.get(f"/api/artifacts/{built['cartridge_artifacts'][0]['id']}/download").data)
    ppm = tmp_path / "frame.ppm"
    subprocess.run([str(runner), str(cartridge), "10", "--dump-ppm", str(ppm)], check=True, capture_output=True, timeout=60)
    data = ppm.read_bytes()
    header_end = data.index(b"\n", data.index(b"\n", data.index(b"\n") + 1) + 1) + 1
    width = int(data.split(b"\n")[1].split()[0])

    def pixel(x, y):
        at = header_end + (y * width + x) * 3
        return tuple(data[at:at + 3])

    blue, yellow, red = pixel(0, 0), pixel(11, 20), pixel(12, 20)
    assert blue[2] > 200 and blue[0] < 40                     # the background
    assert pixel(10, 20) == blue                              # entry 0 is transparent: not drawn
    assert yellow[0] > 240 and yellow[1] > 200 and yellow[2] < 40 and red[0] > 240 and red[1] < 40
    assert all(pixel(x, 21) == yellow for x in range(10, 14)) and pixel(14, 21) == blue
