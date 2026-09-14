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


def test_current_main_scalar_features_generate_public_api_calls():
    blocks = {"blocks": {"blocks": [
        {"type": "prg32_random_state", "fields": {"VAR": "target_x", "LOW": "0", "HIGH": "319"}},
        {"type": "prg32_palette_set", "fields": {"INDEX": "1", "COLOR": "RED"}},
        {"type": "prg32_clear_indexed", "fields": {"INDEX": "0"}},
        {"type": "prg32_draw_rect_indexed", "fields": {"X": "2", "Y": "3", "W": "4", "H": "5", "INDEX": "1"}},
        {"type": "prg32_draw_pixel_indexed", "fields": {"X": "6", "Y": "7", "INDEX": "1"}},
        {"type": "prg32_draw_pixel", "fields": {"X": "8", "Y": "9", "COLOR": "BLUE"}},
        {"type": "prg32_audio_note", "fields": {"NOTE": "60", "CHANNEL": "1", "MS": "250"}},
    ]}}
    _, source = blocks_to_c(blocks, {"title": "API Check"})
    for call in (
        "prg32_random_number(0, 319)", "prg32_palette_set(1, PRG32_COLOR_RED)",
        "prg32_gfx_clear_indexed(0)", "prg32_gfx_rect_indexed(2, 3, 4, 5, 1)",
        "prg32_gfx_pixel_indexed(6, 7, 1)", "prg32_gfx_pixel(8, 9, PRG32_COLOR_BLUE)",
        "prg32_audio_note(1, 0, 60, 255, 250)",
    ):
        assert call in source


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
