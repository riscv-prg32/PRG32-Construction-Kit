from __future__ import annotations

from prg32_construction_kit.generator import blocks_to_c, blocks_to_ir, check_expr, sprite_to_c
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
        "prg32_kit_random(0, 319)", "prg32_palette_set(1, PRG32_COLOR_RED)",
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


def _stmt(block_type, **fields):
    return {"blocks": {"blocks": [{"type": block_type, "fields": fields}]}}


def test_dropdown_values_cannot_inject_c():
    _, source = blocks_to_c(_stmt("prg32_clear_screen", COLOR="PRG32_COLOR_RED); system(\"x\"); (0"), {"title": "Inject"})
    assert "system" not in source
    assert "prg32_gfx_clear(PRG32_COLOR_BLACK);" in source
    blocks = {"blocks": {"blocks": [{"type": "prg32_if_button", "fields": {"BUTTON": "PRG32_BTN_A) { evil(); } if (1"}}]}}
    _, source = blocks_to_c(blocks, {"title": "Inject"})
    assert "evil" not in source
    assert "if (input & PRG32_BTN_A) {" in source


def test_comments_and_text_cannot_escape_into_c():
    _, source = blocks_to_c(_stmt("prg32_comment", TEXT="*/ evil(); /*"), {"title": "Comment"})
    assert "*/ evil" not in source
    _, source = blocks_to_c(_stmt("prg32_draw_text", TEXT='a"b\\c??/\r', X="1", Y="2"), {"title": "Text"})
    assert 'prg32_gfx_text8(1, 2, "a\\"b\\\\c?\\?/\\015",' in source
    _, source = blocks_to_c({"blocks": {"blocks": [{"type": "*/ evil(); /*"}]}}, {"title": "Type"})
    assert "*/ evil" not in source


def test_expressions_are_validated_with_warnings():
    ir, source = blocks_to_c(_stmt("prg32_draw_rect", X="exit(0)", Y="1.5", W="Player_X + 2", H="x--3"), {"title": "Expr"})
    assert "exit" not in source
    assert "prg32_gfx_rect(0, 0, player_x + 2, x - -3, PRG32_COLOR_WHITE);" in source
    assert len(ir["warnings"]) == 2
    for bad in ("1;", "{", "#define", "1 /* x", "a // b", "(1", "1)", "1+", "a b", "3x"):
        assert check_expr(bad) is None, bad
    for good in ("-3", "(a + 1) * 2", "a >= 0 && !b", "0x1F", "PRG32_SCREEN_W - 16"):
        assert check_expr(good) is not None, good


def test_reserved_names_become_safe_state_variables():
    _, source = blocks_to_c({"blocks": {"blocks": [
        {"type": "prg32_set_state", "fields": {"VAR": "input", "VALUE": "1"}},
        {"type": "prg32_change_state", "fields": {"VAR": "int", "DELTA": "input"}},
    ]}}, {"title": "Names"})
    assert "static int input_var = 1;" in source
    assert "int_var += input_var;" in source


def test_sprite_to_c_tolerates_bad_input():
    source = sprite_to_c({"name": "odd", "width": "abc", "height": 100000, "pixels": [["#zzzzzz", 7, None, "#fff"], "row"]})
    assert "ODD_WIDTH 16" in source
    assert "ODD_HEIGHT 128" in source
    assert "0xFFFF" in source


def _program(start=(), update=(), draw=()):
    def chain(blocks):
        blocks = [dict(b) for b in blocks]
        for current, following in zip(blocks, blocks[1:]):
            current["next"] = {"block": following}
        return {"block": blocks[0]} if blocks else None
    tops = []
    for kind, body in (("prg32_on_start", start), ("prg32_update", update), ("prg32_draw", draw)):
        block = {"type": kind}
        if body:
            block["inputs"] = {"DO": chain(body)}
        tops.append(block)
    return {"blocks": {"blocks": tops}}


def test_lists_become_bounds_checked_c_arrays():
    blocks = _program(
        start=[{"type": "prg32_list_create", "fields": {"LIST": "Bricks", "SIZE": "60", "VALUE": "1"}}],
        update=[{"type": "prg32_list_set", "fields": {"LIST": "bricks", "INDEX": "i", "VALUE": "bricks[i] - 1"}},
                {"type": "prg32_list_change", "fields": {"LIST": "bricks", "INDEX": "0", "DELTA": "2"}}],
    )
    ir, source = blocks_to_c(blocks, {"title": "Lists"})
    assert ir["lists"] == [{"name": "bricks", "size": 60}]
    assert "static int bricks[60];" in source
    assert "prg32_kit_fill(bricks, 60, 1);" in source
    assert "prg32_kit_set(bricks, 60, i, prg32_kit_get(bricks, 60, i) - 1);" in source
    assert "static int i = 0;" in source  # names used in expressions are declared


def test_kit_functions_and_constants_translate_to_visible_helpers():
    blocks = _program(update=[{"type": "prg32_set_state", "fields": {
        "VAR": "v", "VALUE": "abs(min(a, max(b, 3))) + sin(angle) * cos(angle) / 256 + rgb(1, 2, 3) + frame() + PRG32_GAME_W"}}])
    _, source = blocks_to_c(blocks, {"title": "Funcs"})
    assert ("v = prg32_kit_abs(prg32_kit_min(a, prg32_kit_max(b, 3))) + prg32_kit_sin(angle) * prg32_kit_cos(angle) / 256"
            " + prg32_kit_rgb(1, 2, 3) + prg32_kit_frame() + PRG32_GAME_W;") in source
    assert "static const int16_t prg32_kit_sine_table[91]" in source
    assert "prg32_kit_frame_count++;" in source
    for bad in ("exit(0)", "abs(1, 2)", "PRG32_SECRET", "bricks[1]", "a = 1", "x[1]]"):
        assert check_expr(bad) is None, bad


def test_repeat_is_capped_and_uses_a_hidden_counter():
    blocks = _program(update=[{"type": "prg32_repeat", "fields": {"VAR": "i", "FROM": "0", "TO": "n"},
                               "inputs": {"DO": {"block": {"type": "prg32_change_state", "fields": {"VAR": "i", "DELTA": "5"}}}}}])
    _, source = blocks_to_c(blocks, {"title": "Loop"})
    assert "for (prg32_kit_step0 = 0; prg32_kit_step0 <= prg32_kit_last0 && prg32_kit_count0 < 1024;" in source
    assert "i = prg32_kit_step0;" in source


def test_only_used_helpers_are_emitted():
    _, source = blocks_to_c(default_blocks(), {"title": "Hello Blocks"})
    assert "prg32_kit_" not in source


def test_multiplayer_projects_pass_the_builder_multiplayer_flag(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from prg32_construction_kit.packager import run_prg32_build
    seen = []
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run",
                        lambda command, **_: seen.append(command) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    run_prg32_build("prg32 build", tmp_path / "g.c", tmp_path / "g.prg32", "g", "g", "qemu", 64, ["multiplayer", "audio"])
    assert "--multiplayer" in seen[0]
    assert seen[0].count("--required-feature") == 2
