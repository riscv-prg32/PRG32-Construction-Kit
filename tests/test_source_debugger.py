"""Source and block debugging (refinement phase 4, ADR-0015).

The coordinate chain  Blockly block -> IR path -> source lines -> guest addresses  is made of
saved, deterministic maps; these tests prove each link and the debugger built on them:

- source maps never change the generated C or assembly, and name every block;
- debug maps come from DWARF, keep no server paths, and degrade safely to "unavailable";
- debug builds give byte-identical cartridges (with the real toolchain);
- the browser's source debugger (static/js/source_debug.js), driving the real WebAssembly
  core on committed fixtures: source/block breakpoints, active block, call stack, locals,
  globals, watches, conditional breakpoints, CSRs and compressed-instruction steps;
- GET /api/artifacts/<id>/debug serves the maps only to the cartridge's owner.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from debug_seed import FIXTURES, pong_project, seed_pong
from test_auth import make_student, student_client
from test_examples import EXAMPLE_FILES, load_project

from prg32_construction_kit import debug_build, debug_info
from prg32_construction_kit.asm_generator import ir_to_asm
from prg32_construction_kit.generator import blocks_to_c
from prg32_construction_kit.source_maps import build_source_map, strip_markers

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")


def drive(fixture: str, *commands: str, source_map: bool = False) -> list[dict]:
    """Run tools/source_debug_check.mjs on a committed fixture cartridge."""
    result = subprocess.run(
        ["node", str(ROOT / "tools" / "source_debug_check.mjs"), str(FIXTURES / f"{fixture}.prg32"),
         str(FIXTURES / f"{fixture}.map.json"), str(FIXTURES / f"{fixture}.source_map.json") if source_map else "-",
         *commands], capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# --- source maps -------------------------------------------------------------------------------

@pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda path: path.stem)
@pytest.mark.parametrize("language", ["c", "asm"])
def test_source_maps_leave_the_generated_code_unchanged(path, language):
    project = load_project(path)
    game_ir, source, source_map = build_source_map(project["blocks_json"], project, language)
    expected = blocks_to_c(project["blocks_json"], project)[1] if language == "c" else ir_to_asm(game_ir)
    assert source == expected
    assert "\x00" not in source
    assert build_source_map(project["blocks_json"], project, language)[2] == source_map  # deterministic
    lines = source.split("\n")
    block_ids = {block["id"] for block in _all_blocks(project["blocks_json"])}
    for entry in source_map["entries"]:
        first, last = entry["lines"]
        assert 1 <= first <= last <= len(lines)
        assert entry["block"] in block_ids and entry["ir"].split("[")[0] in ("init", "update", "draw")


def _all_blocks(blocks_json):
    stack = list((blocks_json.get("blocks") or {}).get("blocks", []))
    while stack:
        block = stack.pop()
        yield block
        for value in (block.get("inputs") or {}).values():
            if isinstance(value, dict) and isinstance(value.get("block"), dict):
                stack.append(value["block"])
        if isinstance((block.get("next") or {}).get("block"), dict):
            stack.append(block["next"]["block"])


def test_every_statement_block_is_mapped_with_nested_paths():
    project = pong_project()
    _, _, source_map = build_source_map(project["blocks_json"], project, "c")
    paths = {entry["ir"] for entry in source_map["entries"]}
    assert "update[1].then[0].then[0]" in paths  # a block inside an "if" inside an "if"
    nested = next(entry for entry in source_map["entries"] if entry["ir"] == "update[1].then[0].then[0]")
    outer = next(entry for entry in source_map["entries"] if entry["ir"] == "update[1]")
    assert outer["lines"][0] < nested["lines"][0] <= nested["lines"][1] < outer["lines"][1]


def test_markers_must_balance():
    with pytest.raises(ValueError):
        strip_markers("\x00prg32-map-begin a\ncode")


def test_committed_block_map_matches_the_generator():
    project = pong_project()
    assert build_source_map(project["blocks_json"], project, "c")[2] == json.loads(
        (FIXTURES / "pong.source_map.json").read_text())


# --- debug maps --------------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["compressed", "locals", "pong"])
def test_committed_debug_maps_name_no_server_folder(name):
    text = (FIXTURES / f"{name}.map.json").read_text()
    debug_map = json.loads(text)
    assert debug_map["status"] == "ok" and debug_map["link_base"] == 0x40800000
    assert all("/" not in name and "\\" not in name for name in debug_map["files"])
    for word in ("/Users/", "/home/", "/tmp/", "/var/", "/srv/", ".espressif"):
        assert word not in text


def test_damaged_or_missing_debug_information_is_unavailable(tmp_path):
    junk = tmp_path / "junk.elf"
    junk.write_bytes(b"\x7fELF" + os.urandom(200))
    assert debug_info.build_debug_map(junk)["status"] == "unavailable"
    assert debug_info.build_debug_map(tmp_path / "missing.elf")["status"] == "unavailable"
    big = tmp_path / "big.elf"
    big.write_bytes(b"\x7fELF" + b"\0" * (debug_info.MAX_ELF_BYTES + 1))
    assert "4 MiB" in debug_info.build_debug_map(big)["reason"]
    assert debug_info.matches_cartridge(junk, FIXTURES / "pong.prg32") is False


def test_cartridge_code_is_read_from_the_header():
    code = debug_info.cartridge_code((FIXTURES / "locals.prg32").read_bytes())
    assert code and len(code) == int.from_bytes((FIXTURES / "locals.prg32").read_bytes()[16:20], "little")
    with pytest.raises(debug_info.DebugInfoError):
        debug_info.cartridge_code(b"not a cartridge at all")


def test_only_the_prg32_builder_gets_debug_wrappers(tmp_path):
    assert debug_build.is_prg32_builder("python3 -m prg32 cartridge build")
    assert debug_build.is_prg32_builder("/usr/local/bin/prg32 cartridge build")
    assert not debug_build.is_prg32_builder("my-own-builder --fast")
    assert debug_build.prepare(tmp_path, "riscv32-esp-elf-", "my-own-builder") is None


def test_fixtures_are_what_the_toolchain_makes():
    from prg32_construction_kit.build_check import toolchain_present
    from prg32_construction_kit.config import Config

    if not toolchain_present(Config.PRG32_BUILD_COMMAND):
        pytest.skip("the PRG32 toolchain is not installed")
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import build_debug_fixtures

    recorded = json.loads((FIXTURES / "BUILD.json").read_text())
    if build_debug_fixtures.inputs() != recorded:
        pytest.skip(f"the fixtures were built with {recorded}; this machine has {build_debug_fixtures.inputs()}")
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "build_debug_fixtures.py"), "--check"],
                            capture_output=True, text=True, timeout=600, check=False, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


# --- the browser's source debugger on the real core ----------------------------------------------

@needs_node
def test_source_breakpoint_call_stack_and_variables():
    placed, stop = drive("locals", "line:20", "continue")
    assert placed["placed"]["line"] == 20
    assert stop["result"] == 2 and stop["line"] == {"file": "game.c", "line": 20}
    assert [(frame["function"], frame["line"]) for frame in stop["stack"][:3]] == [
        ("paint_cell", 20), ("paint_row", 27), ("dbg_draw", 51)]
    cell = dict((item["name"], item["text"]) for item in stop["variables"][0])
    assert cell["column"] == "0" and cell["left"] == "0" and cell["top"] == "10"
    assert "optimised out" in cell["row"]  # said, not guessed
    assert dict((item["name"], item["text"]) for item in stop["variables"][1])["total"] == "0"
    globals_ = dict((item["name"], item["text"]) for item in stop["globals"])
    assert globals_["score"] == "4" and globals_["heights"].startswith("int[4]")


@needs_node
def test_a_line_without_code_moves_the_breakpoint_to_the_next_line():
    assert drive("locals", "line:19")[0]["placed"]["line"] == 20


@needs_node
def test_watches_read_members_elements_and_registers():
    answers = drive("locals", "line:20", "continue", "watch:player.x", "watch:heights[2]", "watch:heights[column]",
                    "watch:score", "watch:sp", "watch:nothing_here", "watch:heights[9]")
    values = {answer["command"]: answer for answer in answers[2:]}
    assert values["watch:player.x"]["value"] == 150
    assert values["watch:heights[2]"]["value"] == 30
    assert values["watch:heights[column]"]["value"] == 10
    assert values["watch:score"]["value"] == 4
    assert values["watch:sp"]["value"] > 0x40800000
    assert values["watch:nothing_here"]["error"] and values["watch:heights[9]"]["error"]


@needs_node
def test_conditional_breakpoints_run_on_while_false():
    answers = drive("locals", "if:27:row == 2", "continue", "watch:row")
    assert answers[1]["skipped"] == 8  # rows 0 and 1, four columns each
    assert answers[2]["value"] == 2


@needs_node
def test_block_breakpoint_finds_the_active_block():
    answers = drive("pong", "block:pong-34", "continue", source_map=True)
    assert answers[0]["placed"]["block"] == "pong-34"
    stop = answers[1]
    assert stop["result"] == 2 and stop["block"]["block"] == "pong-34" and stop["block"]["op"] == "clamp"
    assert stop["stack"][0]["function"] == "pong_update"
    assert {"player_y", "ball_x", "player_score"} <= {item["name"] for item in stop["globals"]}


@needs_node
def test_compressed_instructions_step_by_their_own_width():
    answers = drive("compressed", "line:30", "continue", "stepi:12")
    # c.addi16sp, c.swsp, la (auipc+addi), c.lw, c.addi, c.sw, c.mv, c.jal (+8), c.add, c.jr (-8), c.lwsp
    assert answers[2]["widths"] == [2, 2, 4, 4, 2, 2, 2, 2, 8, 2, -8, 2]
    assert answers[1]["globals"] == [{"name": "counter", "text": "0 (0x00000000)"}]
    assert answers[2]["globals"] == [{"name": "counter", "text": "1 (0x00000001)"}]
    # handwritten assembly has no call-frame rules: the caller comes from ra, and says so
    assert answers[2]["stack"][-1]["guessed"] is True


@needs_node
def test_csr_counters_follow_the_core():
    stop = drive("locals", "line:20", "continue")[1]
    csr = dict(stop["csr"])
    assert csr["instret"] == stop["retired"] and csr["cycle"] >= csr["instret"] and csr["time"] > 0


# --- the API ----------------------------------------------------------------------------------

def test_debug_route_serves_maps_source_and_blocks(app, client):
    seeded = seed_pong(client, app.config["BUILD_ROOT"])
    answer = client.get(f"/api/artifacts/{seeded['cartridge']}/debug").get_json()
    assert answer["debug_map"]["status"] == "ok" and answer["source"]["file"] == "game.c"
    assert answer["source_map"]["entries"] and answer["blocks_json"]
    assert "path" not in answer["cartridge"]


def test_debug_route_falls_back_without_maps(app, client):
    seeded = seed_pong(client, app.config["BUILD_ROOT"], with_maps=False)
    answer = client.get(f"/api/artifacts/{seeded['cartridge']}/debug").get_json()
    assert answer["debug_map"]["status"] == "unavailable" and answer["source_map"] is None


def test_a_block_map_for_another_source_is_not_used(app, client):
    seeded = seed_pong(client, app.config["BUILD_ROOT"])
    build = client.get(f"/api/builds/{seeded['build']}").get_json()
    client.put(f"/api/artifacts/{build['c_artifact_id']}", json={"text_content": "/* edited */"})
    answer = client.get(f"/api/artifacts/{seeded['cartridge']}/debug").get_json()
    assert answer["source_map"] is None and answer["blocks_json"] is None


def test_debug_route_is_only_for_the_owner(app, client):
    seeded = seed_pong(client, app.config["BUILD_ROOT"])
    make_student(client, "debugger_peer")
    peer = student_client(app, "debugger_peer")
    assert peer.get(f"/api/artifacts/{seeded['cartridge']}/debug").status_code == 404
    other = client.post("/api/artifacts", json={"kind": "note", "name": "x"}).get_json()
    assert client.get(f"/api/artifacts/{other['id']}/debug").status_code == 404


def test_packaging_reports_debug_status_but_never_the_maps(app, client, monkeypatch):
    from test_source_languages import fake_builder

    app.config["PRG32_BUILD_COMMAND"] = "classroom-builder --cartridge"  # some other builder
    commands = []
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder(commands))
    project = pong_project()
    created = client.post("/api/projects", json={"title": "Pong", "blocks_json": project["blocks_json"]}).get_json()
    result = client.post(f"/api/projects/{created['id']}/package", json={"architectures": ["qemu"]}).get_json()
    assert "debug_maps" not in result["result"]
    assert "--tool-prefix" not in commands[0]  # not the PRG32 builder: no debug wrappers


def test_real_debug_build_gives_the_same_cartridge(app, client):
    """With the real toolchain: debug information on or off, the cartridge is byte for byte the same."""
    from prg32_construction_kit.build_check import toolchain_present

    if not toolchain_present(app.config["PRG32_BUILD_COMMAND"]):
        pytest.skip("the PRG32 toolchain is not installed")
    project = pong_project()
    created = client.post("/api/projects", json={"title": "Pong", "blocks_json": project["blocks_json"]}).get_json()
    shas = []
    for enabled in (True, False):
        app.config["PRG32_DEBUG_INFO"] = enabled
        result = client.post(f"/api/projects/{created['id']}/package", json={"architectures": ["qemu"]}).get_json()
        assert result["build"]["status"] == "ready", result["build"]["log"]
        assert result["result"]["debug_info"] == ({"qemu": "ok"} if enabled else {})
        cartridge = result["cartridge_artifacts"][0]
        shas.append(cartridge["metadata"]["sha256"])
        if enabled:
            answer = client.get(f"/api/artifacts/{cartridge['id']}/debug").get_json()
            assert answer["debug_map"]["status"] == "ok" and len(answer["source_map"]["entries"]) > 50
    assert shas[0] == shas[1]
