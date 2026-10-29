"""Blocks -> RISC-V assembly: safe, deterministic, explained, and doing exactly what the C does."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from prg32_construction_kit.asm_generator import ASM_GLOSSARY, asm_string, asm_symbol, blocks_to_asm, ir_to_asm
from prg32_construction_kit.generator import blocks_to_ir, ir_to_c

from rv32_harness import HOST_CC, find_riscv_gcc, run_asm, run_c
from test_examples import EDGE_PROJECT, EXAMPLE_FILES, every_block_project, load_project

RISCV_GCC = find_riscv_gcc()
needs_riscv = pytest.mark.skipif(RISCV_GCC is None, reason="no RISC-V GCC (set PRG32_RISCV_GCC)")
HOST_IS_GCC = bool(HOST_CC and "gcc" in Path(HOST_CC).resolve().name.lower())
needs_both = pytest.mark.skipif(RISCV_GCC is None or not HOST_IS_GCC,
                                reason="needs a RISC-V GCC and host GCC with the PRG32 argument order")


def chain(*blocks: dict) -> dict | None:
    """Link blocks into one stack (each block's 'next' is the following one)."""
    for current, following in zip(blocks, blocks[1:]):
        current["next"] = {"block": following}
    return blocks[0] if blocks else None


def stmt(block_type: str, inner: list[dict] | None = None, **fields) -> dict:
    block = {"type": block_type, "fields": fields}
    if inner:
        block["inputs"] = {"DO": {"block": chain(*inner)}}
    return block


def program(start=(), update=(), draw=()) -> dict:
    tops = []
    for kind, blocks in (("prg32_on_start", start), ("prg32_update", update), ("prg32_draw", draw)):
        top = {"type": kind}
        if blocks:
            top["inputs"] = {"DO": {"block": chain(*blocks)}}
        tops.append(top)
    return {"blocks": {"languageVersion": 0, "blocks": tops}}


# Expressions and blocks where a careless translation would differ from C:
# division by 0 and by -1, the smallest int, shifts, short-circuit && and || around
# random(), positions outside a list, negative angles, narrow firmware parameters,
# variables called like registers, nested loops and every kit function.
STRESS_PROJECT = program(
    start=[
        stmt("prg32_list_create", LIST="cells", SIZE="5", VALUE="3"),
        stmt("prg32_set_state", VAR="a0", VALUE="-2147483647"),
        stmt("prg32_set_state", VAR="sp", VALUE="0x10"),
        stmt("prg32_set_state", VAR="zero", VALUE="-1"),
        stmt("prg32_set_state", VAR="angle", VALUE="-725"),
        stmt("prg32_mp_join"),
        stmt("prg32_audio_volume", VOLUME="300"),
    ],
    update=[
        stmt("prg32_change_state", VAR="angle", DELTA="37"),
        stmt("prg32_set_state", VAR="q", VALUE="(a0 - 1) / zero + (a0 - 1) % zero + 7 / (sp - 16) + 7 % (sp - 16)"),
        stmt("prg32_set_state", VAR="s", VALUE="(1 << angle) + (a0 >> 3) + (-a0 >> 31) + ~sp + !zero + !!angle"),
        stmt("prg32_set_state", VAR="r", VALUE="random(0, 1) && random(5, 9) || random(-3, 3) > 0"),
        stmt("prg32_set_state", VAR="t", VALUE="sin(angle) + cos(angle) * 2 - sin(-angle) / 3 + abs(a0 - 1) + sign(zero)"),
        stmt("prg32_set_state", VAR="u", VALUE="min(q, s) * max(r, t) + clamp(angle, -50, 50) + rgb(300, -4, 128)"),
        stmt("prg32_set_state", VAR="v", VALUE="cells[angle % 7] + cells[-1] + cells[5] + tile(1, angle & 255, 300)"),
        stmt("prg32_set_state", VAR="w", VALUE="peers() + peer_x(0) + peer_y(1) + peer_look(1) + peer_x(4) + frame()"),
        stmt("prg32_set_state", VAR="cmp", VALUE="(q < s) + (q > s) * 2 + (q <= s) * 4 + (q >= s) * 8 + (q == q) * 16 + (q != s) * 32"),
        stmt("prg32_list_set", LIST="cells", INDEX="angle % 6", VALUE="u ^ v | w & 255"),
        stmt("prg32_list_change", LIST="cells", INDEX="frame() % 7 - 1", DELTA="random(1, 3)"),
        stmt("prg32_random_state", VAR="dice", LOW="1", HIGH="6"),
        stmt("prg32_random_state", VAR="same", LOW="4", HIGH="2"),
        stmt("prg32_clamp_state", VAR="angle", LOW="-400", HIGH="random(390, 410)"),
        stmt("prg32_wrap_state", VAR="t", LOW="-10", HIGH="10"),
        stmt("prg32_repeat", [
            stmt("prg32_repeat", [stmt("prg32_change_state", VAR="sum", DELTA="i * j")], VAR="j", FROM="i", TO="3"),
            stmt("prg32_if_else", [stmt("prg32_change_state", VAR="sum", DELTA="1")], COND="i % 2"),
        ], VAR="i", FROM="-2", TO="frame() % 5"),
        stmt("prg32_if_button", [stmt("prg32_change_state", VAR="held", DELTA="1")], BUTTON="LEFT"),
        stmt("prg32_if_button_once", [stmt("prg32_change_state", VAR="presses", DELTA="1")], BUTTON="START"),
        stmt("prg32_if_button_once", [stmt("prg32_play_beep", FREQ="cells[0] * 40", MS="50")], BUTTON="P2_A"),
        stmt("prg32_if_touching", [stmt("prg32_audio_note", NOTE="60 + dice", CHANNEL="dice - 1", MS="100")],
             AX="angle % 40", AY="0", AW="20", AH="20", BX="10", BY="0", BW="20", BH="20"),
        stmt("prg32_mp_share", X="angle * 100", Y="-angle * 99", LOOK="a0"),
        stmt("prg32_score_submit", VALUE="q"),
        stmt("prg32_audio_stop", CHANNEL="257"),
    ],
    draw=[
        stmt("prg32_clear_screen", COLOR="NAVY"),
        stmt("prg32_draw_rect_rgb", X="1", Y="2", W="3", H="4", RGB="u"),
        stmt("prg32_draw_pixel_indexed", X="t", Y="u", INDEX="-1"),
        stmt("prg32_palette_set", INDEX="sp + 250", COLOR="PINK"),
        stmt("prg32_draw_number", VALUE="a0 - 1", X="0", Y="0", FG="WHITE", BG="BLACK"),
        stmt("prg32_draw_number", VALUE="q", X="0", Y="8", FG="WHITE", BG="BLACK"),
        stmt("prg32_band_text", TEXT="Q", VALUE="q"),
        stmt("prg32_band_text", TEXT="Café \"quoted\" \\ back"),
        stmt("prg32_draw_text", TEXT="*/ not a comment end", X="2", Y="2", FG="RED", BG="BLACK"),
        stmt("prg32_draw_line", X1="angle % 50", Y1="0", X2="0", Y2="angle % 30", COLOR="GREEN"),
        stmt("prg32_draw_circle", X="100", Y="100", R="angle % 9 - 1", COLOR="RED", FILL="FILLED"),
        stmt("prg32_draw_circle", X="50", Y="50", R="250", COLOR="RED", FILL="OUTLINE"),
        stmt("prg32_draw_frame", X="5", Y="5", W="angle % 4 - 1", H="3", COLOR="LIME"),
        stmt("prg32_draw_bitmap", X="0", Y="0", COLOR="WHITE", SCALE="angle % 11 - 1",
             ROW0="#.#.#.#.", ROW1=".#.#.#.#", ROW2="########", ROW3="........", ROW4="#......#",
             ROW5="##....##", ROW6="#.#..#.#", ROW7="..####.."),
        stmt("prg32_tile_define", ID="300", FG="WHITE", BG="BLACK", ROW0="########"),
        stmt("prg32_playfield_put", LAYER="1", TX="angle", TY="-3", ID="9"),
        stmt("prg32_playfield_scroll", LAYER="0", X="-angle", Y="angle * 3"),
        stmt("prg32_playfield_draw", LAYER="1", TRANSPARENT="TRANSPARENT"),
        stmt("prg32_comment", TEXT="*/ evil(); /* \\"),
    ],
)


def projects() -> dict[str, dict]:
    found = {path.stem: load_project(path) for path in EXAMPLE_FILES}
    found["every_block"] = {"title": "Every Block", "blocks_json": every_block_project()}
    found["edge_values"] = {"title": "Edge", "blocks_json": EDGE_PROJECT}
    found["stress"] = {"title": "Stress */ Test", "blocks_json": STRESS_PROJECT}
    # Sprite Lab sprites and a background (project_assets.py): the art functions make the same calls.
    from test_project_assets import ART_BLOCKS, CATALOG
    found["art"] = {"title": "Art Test", "blocks_json": ART_BLOCKS, "assets": CATALOG}
    return found


PROJECTS = projects()


@pytest.mark.parametrize("name", list(PROJECTS))
def test_assembly_is_deterministic_and_complete(name):
    project = PROJECTS[name]
    ir, source = blocks_to_asm(project["blocks_json"], project)
    assert blocks_to_asm(project["blocks_json"], project)[1] == source  # same JSON, same assembly
    prefix = ir["entry_prefix"]
    for phase in ("init", "update", "draw"):
        assert f"    .globl {prefix}_{phase}\n" in source
        assert f"\n{prefix}_{phase}:\n" in source
    assert "Unsupported" not in source


@pytest.mark.parametrize("name", list(PROJECTS))
def test_every_instruction_line_is_explained(name):
    """Read-by-line: every instruction has a comment, every block has a heading with its C line."""
    _, source = blocks_to_asm(PROJECTS[name]["blocks_json"], PROJECTS[name])
    for line in source.splitlines():
        stripped = line.strip()
        if not line.startswith("    ") or stripped.startswith(("/*", "*", ".")) or not stripped:
            continue
        mnemonic = stripped.split()[0]
        if mnemonic in ASM_GLOSSARY:
            assert " # " in line, line
    used = {line.split()[0] for line in source.splitlines() if line.startswith("    ") and line.split()
            and line.split()[0] in ASM_GLOSSARY}
    header = source.split("*/", 1)[0]
    for mnemonic in used:
        assert ASM_GLOSSARY[mnemonic] in header, mnemonic


def test_blocks_are_headed_by_their_sentence_and_c_line():
    blocks = program(update=[stmt("prg32_change_state", VAR="score", DELTA="2")])
    _, source = blocks_to_asm(blocks, {"title": "Heading"})
    assert 'Block "change score by 2": add 2 to score.' in source
    assert "C:  score += 2;" in source
    c_source = ir_to_c(blocks_to_ir(blocks, {"title": "Heading"}))
    assert 'Block "change score by 2": add 2 to score.' in c_source  # the same sentence in both files


def test_text_and_comments_cannot_escape_into_assembly():
    _, source = blocks_to_asm(STRESS_PROJECT, {"title": "Stress */ Test"})
    assert "*/ evil" not in source  # a comment block cannot end the comment early
    assert '.asciz "*/ not a comment end"' in source  # inside a string literal it is only text
    assert "* / not a comment end" in source  # in the explanations it is defused
    assert '.asciz "Caf? \\"quoted\\" \\\\ back"' in source  # quotes and backslashes are escaped
    assert asm_string("Caf\u00e9") == "Caf\\303\\251"  # a title keeps its UTF-8 bytes, as octal escapes
    for line in source.splitlines():
        assert not line.lstrip().startswith("#"), line  # the C preprocessor would read it as a directive


def test_register_names_are_renamed_only_in_the_assembly():
    ir, source = blocks_to_asm(STRESS_PROJECT, {"title": "Stress"})
    assert asm_symbol("a0") == "a0_var" and asm_symbol("score") == "score"
    assert "\na0_var:" in source and "\nsp_var:" in source and "\nzero_var:" in source
    assert "static int a0 = -2147483647;" in ir_to_c(ir)


def test_division_uses_the_riscv_instructions():
    _, source = blocks_to_asm(program(update=[stmt("prg32_set_state", VAR="q", VALUE="a / b + a % b")]), {"title": "D"})
    assert re.search(r"^\s+div\s+a0, t0, a0|^\s+div\s+a0, a0, t0", source, re.M)
    assert re.search(r"^\s+rem\s+a0", source, re.M)
    # The C line in the heading uses the C helpers; the assembly needs no helper at all.
    assert "call  prg32_kit_div" not in source and "prg32_kit_div:" not in source and "prg32_kit_mod:" not in source


def test_call_arguments_with_side_effects_follow_prg32_gcc_order():
    """Two random arguments must consume random values in the same order as generated C."""
    blocks = program(draw=[stmt("prg32_playfield_put", LAYER="0", TX="random(0, 63)",
                                TY="random(0, 31)", ID="1")])
    _, source = blocks_to_asm(blocks, {"title": "Argument Order"})
    block = source[source.index('Block "put tile'):]
    row = block.index("a0 = random(0, 31)")
    column = block.index("a0 = random(0, 63)")
    call = block.index("call  prg32_playfield_put")
    assert row < column < call


@needs_riscv
@pytest.mark.parametrize("name", list(PROJECTS))
def test_assembly_assembles_for_the_prg32_target(tmp_path, name):
    _, source = blocks_to_asm(PROJECTS[name]["blocks_json"], PROJECTS[name])
    path = tmp_path / "game.S"
    path.write_text(source)
    result = subprocess.run([RISCV_GCC, "-march=rv32imc_zicsr_zifencei", "-mabi=ilp32", "-x", "assembler-with-cpp",
                             "-c", str(path), "-o", str(tmp_path / "game.o")], capture_output=True, text=True)
    assert result.returncode == 0 and not result.stderr, result.stderr


@needs_both
@pytest.mark.parametrize("name", list(PROJECTS))
def test_assembly_makes_exactly_the_same_firmware_calls_as_the_c(tmp_path, name):
    """Run both translations through GCC for 40 frames: the call logs must match."""
    project = PROJECTS[name]
    ir = blocks_to_ir(project["blocks_json"], project)
    c_log = run_c(ir_to_c(ir), ir["entry_prefix"], 40, tmp_path)
    asm_log = run_asm(ir_to_asm(ir), ir["entry_prefix"], 40, tmp_path, RISCV_GCC)
    assert len(c_log) > 40
    assert asm_log == c_log


def test_asm_helpers_are_only_emitted_when_used():
    from prg32_construction_kit.sample_data import default_blocks
    _, source = blocks_to_asm(default_blocks(), {"title": "Hello Blocks"})
    assert "prg32_kit_draw_line" not in source and "prg32_kit_sine_table" not in source
    _, stress = blocks_to_asm(STRESS_PROJECT, {"title": "Stress"})
    for helper in ("prg32_kit_sin:", "prg32_kit_cos:", "prg32_kit_draw_circle:", "prg32_kit_band:", "prg32_kit_get:"):
        assert helper in stress


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_stress_project_reads_the_same_in_the_simulator():
    from test_examples import run_node
    ir = blocks_to_ir(STRESS_PROJECT, {"title": "Stress"})
    js = json.loads(run_node(f"const ir = window.PRG32Simulator.compileBlocks({json.dumps(STRESS_PROJECT)});"
                             "console.log(JSON.stringify({update: ir.update, draw: ir.draw}));"))
    assert js["update"] == ir["update"] and js["draw"] == ir["draw"]
    assert ir["warnings"] == []


def test_generated_files_name_the_same_entry_points():
    ir = blocks_to_ir(STRESS_PROJECT, {"title": "Stress"})
    c_names = set(re.findall(r"^void (\w+)\(void\) \{", ir_to_c(ir), re.M))
    asm_names = set(re.findall(r"^\s+\.globl (\w+)$", ir_to_asm(ir), re.M))
    assert c_names == asm_names == {f"stress_{phase}" for phase in ("init", "update", "draw")}
