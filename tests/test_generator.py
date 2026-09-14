from __future__ import annotations

from prg32_construction_kit.generator import blocks_to_c, blocks_to_ir, sprite_to_c
from prg32_construction_kit.sample_data import default_blocks, upstream_example_projects


def test_blocks_to_ir_has_lifecycle():
    ir = blocks_to_ir(default_blocks(), {"title": "Hello Blocks", "author": "Tester"})
    assert ir["entry_prefix"] == "hello_blocks"
    assert ir["init"]
    assert ir["update"]
    assert ir["draw"]
    assert any(item["name"] == "player_x" for item in ir["state"])


def test_blocks_to_c_contains_prg32_calls():
    ir, c_source = blocks_to_c(default_blocks(), {"title": "Hello Blocks"})
    assert "void hello_blocks_init" in c_source
    assert "prg32_input_read" in c_source
    assert "prg32_gfx_rect" in c_source
    assert ir["entry_prefix"] == "hello_blocks"
    assert "prg32_audio_beep" not in c_source


def test_beep_uses_current_audio_abi():
    blocks = {"blocks": {"blocks": [{"type": "prg32_play_beep", "fields": {"FREQ": "880", "MS": "80"}}]}}
    _, c_source = blocks_to_c(blocks, {"title": "Tone"})
    assert "prg32_audio_note(0, 0, prg32_kit_note_from_hz(880), 255, 80);" in c_source


def test_every_upstream_example_has_convertible_blocks():
    for project in upstream_example_projects():
        ir, c_source = blocks_to_c(project["blocks_json"], project)
        assert ir["warnings"] == []
        assert "prg32_gfx_rect" in c_source


def test_sprite_to_c_rgb565():
    sprite = {"name": "player", "width": 2, "height": 1, "pixels": [["#ffffff", "transparent"]]}
    c_source = sprite_to_c(sprite)
    assert "PLAYER_WIDTH 2" in c_source
    assert "0xFFFF" in c_source
    assert "0x0000" in c_source
