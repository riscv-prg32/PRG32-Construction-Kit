"""The browser PRG32 core (static/wasm) runs cartridges exactly like PRG32-QT.

Golden tests compare, frame by frame, the WebAssembly build (under Node) with a
native build of the same C interface over the same PRG32-QT core, and that
native build with PRG32-QT's own prg32qt-headless. They need Node, CMake, a C++
compiler and a PRG32-QT checkout (PRG32QT_DIR, default ../PRG32-QT) and skip
cleanly without them. PRG32_WASM_MODULE points the tests at another build of
prg32-core.js (CI uses it to test a fresh build too).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from prg32_construction_kit.build_check import check_command
from prg32_construction_kit.sample_data import default_blocks

ROOT = Path(__file__).resolve().parent.parent
STATIC_WASM = ROOT / "static" / "wasm"
MODULE = Path(os.environ.get("PRG32_WASM_MODULE") or STATIC_WASM / "prg32-core.js")
PRG32QT = Path(os.environ.get("PRG32QT_DIR") or ROOT.parent / "PRG32-QT").resolve()
# The browser core's audio engine is the PRG32 firmware's (ADR-0021): the build needs the SDK too.
PRG32_SDK = Path(os.environ.get("PRG32_SOURCE") or ROOT.parent / "PRG32").resolve()
GOLDEN = ("Asteroids", "Bach", "PerformanceTest")


def run(command, **kwargs):
    return subprocess.run(command, capture_output=True, text=True, timeout=600, check=False, **kwargs)


@pytest.fixture(scope="session")
def node():
    found = shutil.which("node")
    if found is None:
        pytest.skip("Node.js is not installed")
    return found


@pytest.fixture(scope="session")
def prg32qt():
    if not (PRG32QT / "src" / "core" / "Runtime.cpp").is_file():
        pytest.skip(f"no PRG32-QT checkout at {PRG32QT} (set PRG32QT_DIR)")
    return PRG32QT


@pytest.fixture(scope="session")
def native_harness(tmp_path_factory, prg32qt):
    if shutil.which("cmake") is None or not (shutil.which("c++") or shutil.which("g++") or shutil.which("clang++")):
        pytest.skip("CMake or a C++ compiler is not installed")
    build = tmp_path_factory.mktemp("native-harness")
    if not (PRG32_SDK / "components" / "prg32_audio" / "audio_synth.c").is_file():
        pytest.skip(f"no PRG32 SDK checkout at {PRG32_SDK} (set PRG32_SOURCE)")
    configure = run(["cmake", "-S", str(ROOT / "wasm"), "-B", str(build), f"-DPRG32QT_DIR={prg32qt}",
                     f"-DPRG32_DIR={PRG32_SDK}", "-DCMAKE_BUILD_TYPE=Release"])
    assert configure.returncode == 0, configure.stderr
    built = run(["cmake", "--build", str(build), "--parallel"])
    assert built.returncode == 0, built.stdout + built.stderr
    return build / "prg32-core-harness"


def native_states(harness, cartridge, frames=600, every=100, ppm=None):
    result = run([str(harness), str(cartridge), str(frames), str(every), *([str(ppm)] if ppm else [])])
    assert result.returncode == 0, result.stderr
    return [json.loads(line) for line in result.stdout.splitlines()]


def wasm_states(node, cartridge, frames=600, every=100):
    result = run([node, str(ROOT / "tools" / "wasm_harness.mjs"), str(MODULE), str(cartridge), str(frames), str(every)])
    assert result.returncode == 0, result.stderr
    return [json.loads(line) for line in result.stdout.splitlines()]


def native_debug(harness, cartridge, *commands):
    result = run([str(harness), "--debug", str(cartridge), *commands])
    assert result.returncode == 0, result.stderr
    return [json.loads(line) for line in result.stdout.splitlines()]


def wasm_debug(node, cartridge, *commands):
    result = run([node, str(ROOT / "tools" / "wasm_harness.mjs"), str(MODULE), "--debug", str(cartridge), *commands])
    assert result.returncode == 0, result.stderr
    return [json.loads(line) for line in result.stdout.splitlines()]


# A debugger session touching every command: single steps, step over/out, breakpoints, frames.
DEBUG_SCRIPT = ("step:500", "stepi:50", "over:40", "out:3", "break:update", "break:draw+4", "continue:7",
                "frame:3", "unbreak:draw+4", "continue:2", "disasm:update:16", "out", "over:200",
                "slice:5000", "slice:5000", "slice:100", "state")


# --- the committed module ------------------------------------------------------------

def test_committed_module_matches_its_build_record():
    record = json.loads((STATIC_WASM / "BUILD.json").read_text())
    assert record["schema"] == "prg32-kit-wasm-build-1"
    assert record["abi"] == {"major": 1, "minor": 6, "hash": "0x260f6136"}
    assert len(record["core"]["revision"]) == 40 and record["core"]["license"] == "MIT"
    for name, expected in record["files"].items():
        data = (STATIC_WASM / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected["sha256"] and len(data) == expected["bytes"]


def test_service_worker_caches_the_runtime_for_offline_use():
    worker = (ROOT / "static" / "service-worker.js").read_text()
    for path in ("/static/wasm/prg32-core.js", "/static/wasm/prg32-core.wasm", "/static/js/prg32_runtime.js",
                 "/static/js/prg32_debugger.js"):
        assert f"'{path}'" in worker


def test_player_page_needs_a_sign_in(app, client, anon):
    assert client.get("/player").status_code == 200
    app.config["LOGIN_REQUIRED"] = True
    assert anon.get("/player").status_code in (302, 401)
    app.config["LOGIN_REQUIRED"] = False     # the guest workspace plays local .prg32 files
    assert anon.get("/player").status_code == 200
    assert client.get("/static/wasm/prg32-core.wasm").status_code == 200


def test_a_file_that_is_not_a_cartridge_is_refused(node, tmp_path):
    junk = tmp_path / "junk.prg32"
    junk.write_bytes(b"not a cartridge at all")
    result = run([node, str(ROOT / "tools" / "wasm_harness.mjs"), str(MODULE), str(junk), "1", "1"])
    assert result.returncode == 3 and result.stderr.startswith("load:")


# --- golden cartridges: WebAssembly == native == prg32qt-headless --------------------

@pytest.mark.parametrize("name", GOLDEN)
def test_wasm_runs_golden_cartridges_exactly_like_native(node, native_harness, prg32qt, name):
    cartridge = prg32qt / "tests" / "fixtures" / f"{name}.prg32"
    native = native_states(native_harness, cartridge)
    browser = wasm_states(node, cartridge)
    assert len(native) == 7
    # pc, x0..x31, retired instructions, virtual cycles, framebuffer hash, audio calls: all equal.
    assert browser == native
    assert native[-1]["retired"] > native[0]["retired"]


@pytest.mark.parametrize("name", ("Asteroids", "Bach"))
def test_native_harness_draws_exactly_like_prg32qt_headless(native_harness, prg32qt, tmp_path, name):
    build = tmp_path / "headless"
    if run(["cmake", "-S", str(prg32qt), "-B", str(build), "-DPRG32QT_BUILD_APP=OFF"]).returncode != 0:
        pytest.skip("PRG32-QT's headless runner does not configure here")
    if run(["cmake", "--build", str(build), "--target", "prg32qt-headless", "--parallel"]).returncode != 0:
        pytest.skip("PRG32-QT's headless runner does not build here")
    cartridge = prg32qt / "tests" / "fixtures" / f"{name}.prg32"
    # --verify-media presses the buttons in the same order as the harnesses.
    headless = run([str(build / "prg32qt-headless"), str(cartridge), "450", "--verify-media",
                    "--dump-ppm", str(tmp_path / "qt.ppm")])
    assert headless.returncode == 0, headless.stderr
    native_states(native_harness, cartridge, frames=450, every=450, ppm=tmp_path / "kit.ppm")
    assert (tmp_path / "kit.ppm").read_bytes() == (tmp_path / "qt.ppm").read_bytes()


# --- the debugger (G5): WebAssembly == native, step by step ----------------------------

@pytest.mark.parametrize("name", GOLDEN)
def test_debugger_steps_exactly_like_native(node, native_harness, prg32qt, name):
    cartridge = prg32qt / "tests" / "fixtures" / f"{name}.prg32"
    native = native_debug(native_harness, cartridge, *DEBUG_SCRIPT)
    assert len(native) == len(DEBUG_SCRIPT)
    # pc, x0..x31, phase, breakpoints, hit counts, retired instructions and cycles after every command.
    assert wasm_debug(node, cartridge, *DEBUG_SCRIPT) == native


@pytest.mark.parametrize("name", GOLDEN)
def test_single_steps_add_up(native_harness, prg32qt, name):
    cartridge = prg32qt / "tests" / "fixtures" / f"{name}.prg32"
    at_once = native_debug(native_harness, cartridge, "step:300")[-1]["state"]
    one_by_one = native_debug(native_harness, cartridge, *["step"] * 300)[-1]["state"]
    assert at_once == one_by_one
    start = native_debug(native_harness, cartridge, "state")[0]["state"]
    # One guest instruction per step; a step that runs a PRG32 ABI call retires no guest instruction.
    assert 250 < at_once["retired"] - start["retired"] <= 300
    assert at_once["phase"] in ("update", "draw")


@pytest.mark.parametrize("name", GOLDEN)
def test_breakpoint_stops_once_per_visit(native_harness, prg32qt, name):
    cartridge = prg32qt / "tests" / "fixtures" / f"{name}.prg32"
    lines = native_debug(native_harness, cartridge, "break:update", "continue", "continue:4", "break:0x10")
    first, five = lines[1], lines[2]
    update = first["state"]["entries"]["update"]
    assert first["result"] == 2 and first["state"]["pc"] == update and first["state"]["breakpoint_hits"] == 1
    # Resume ignores the current breakpoint once (PRG32-QT), so every continue runs exactly one frame.
    assert five["result"] == 2 and five["state"]["breakpoint_hits"] == 5 and five["state"]["last_breakpoint"] == update
    assert five["state"]["frames"] - first["state"]["frames"] == 4 and five["state"]["phase"] == "idle"
    assert five["state"]["breakpoints"] == [update]
    assert lines[3]["result"] == 0  # 0x10 is not guest memory


@pytest.mark.parametrize("name", GOLDEN)
def test_playback_slices_stop_at_every_visit(native_harness, prg32qt, name):
    """The browser plays in small slices; a breakpoint still stops every frame, and only Resume leaves it."""
    cartridge = prg32qt / "tests" / "fixtures" / f"{name}.prg32"
    lines = native_debug(native_harness, cartridge, "break:draw", "continue", "slice:1000000", "continue",
                         "slice:37", "stepi", *["slice:37"] * 400)
    hit, again, resumed, parked = lines[1]["state"], lines[2], lines[3]["state"], lines[4]
    assert again["result"] == 2 and again["state"]["last_steps"] == 0  # no resume: still on the breakpoint
    assert again["state"]["breakpoint_hits"] == 1  # ... and that is not a new hit
    assert resumed["breakpoint_hits"] == 2 and resumed["frames"] == hit["frames"] + 1
    assert parked["result"] == 2 and parked["state"]["last_steps"] == 0
    # A step moves off the breakpoint; small slices then run on until the next frame's visit.
    slices = lines[6:]
    first = next(index for index, line in enumerate(slices) if line["result"] == 2)
    assert first > 0 and all(line["result"] in (0, 1) for line in slices[:first])
    assert slices[first]["state"]["breakpoint_hits"] == 3 and slices[first]["state"]["pc"] == hit["entries"]["draw"]
    assert slices[first]["state"]["frames"] == resumed["frames"] + 1
    assert all(line["result"] == 2 and line["state"]["last_steps"] == 0 for line in slices[first + 1:])


@pytest.mark.parametrize("name", GOLDEN)
def test_debug_frames_match_normal_frames(native_harness, prg32qt, name):
    """Running instrumented (checking breakpoints) changes nothing the cartridge can see."""
    cartridge = prg32qt / "tests" / "fixtures" / f"{name}.prg32"
    debugged = native_debug(native_harness, cartridge, "frame:29", "state")[-1]["state"]
    normal = native_states(native_harness, cartridge, frames=29, every=29)[-1]
    # Music tracks advance only in whole frames (Runtime::frame), as in PRG32-QT's debug mode.
    debugged.pop("audio_calls"), normal.pop("audio_calls")
    assert debugged == normal


def test_step_over_and_step_out_follow_calls(native_harness, prg32qt):
    cartridge = prg32qt / "tests" / "fixtures" / "Asteroids.prg32"
    rows = native_debug(native_harness, cartridge, "disasm:update:12")[0]["disassembly"]
    assert rows[0]["address"] == native_debug(native_harness, cartridge, "break:0x10")[0]["state"]["entries"]["update"]
    call = next(row for row in rows if row["text"].startswith(("jal ", "jalr ra")))
    steps_to_call = rows.index(call)
    lines = native_debug(native_harness, cartridge, f"stepi:{steps_to_call}", "over", "out")
    at_call, over, out = (line["state"] for line in lines)
    assert at_call["pc"] == call["address"]
    assert over["pc"] == call["address"] + call["width"] and over["phase"] == "update"
    assert over["retired"] - at_call["retired"] > 1  # the whole called function ran
    assert out["phase"] == "draw" and out["pc"] == out["entries"]["draw"]  # update returned


def test_disassembly_uses_prg32_qt_names(native_harness, prg32qt):
    cartridge = prg32qt / "tests" / "fixtures" / "Asteroids.prg32"
    lines = native_debug(native_harness, cartridge, "disasm:update:8", "disasm:0x10:4")
    rows = lines[0]["disassembly"]
    assert len(rows) == 8 and all(row["width"] in (2, 4) and row["text"] for row in rows)
    assert all(rows[i + 1]["address"] == rows[i]["address"] + rows[i]["width"] for i in range(7))
    assert "sp" in rows[0]["text"]  # ABI register names, as in PRG32-QT's debugger
    assert lines[1]["disassembly"] == []


def test_debugger_javascript_parses(node):
    for path in ("static/js/prg32_runtime.js", "static/js/prg32_debugger.js", "static/js/player.js",
                 "tools/wasm_harness.mjs"):
        result = run([node, "--check", str(ROOT / path)])
        assert result.returncode == 0, path + result.stderr


def test_player_speaks_the_prg32_qt_debug_protocol(node, prg32qt):
    """PRG32CartridgePlayer.debug() with PRG32-QT's /api/debug commands, in Node with a stub canvas."""
    script = f"""
const store = {{}};
globalThis.window = globalThis;
window.addEventListener = () => {{}};
window.localStorage = {{ getItem: k => store[k] ?? null, setItem: (k, v) => {{ store[k] = String(v); }} }};
window.requestAnimationFrame = () => 0;
window.createPrg32Core = require({json.dumps(str(MODULE))});
require({json.dumps(str(ROOT / 'static' / 'js' / 'prg32_runtime.js'))});
const canvas = {{ getContext: () => ({{ createImageData: (w, h) => ({{ data: new Uint8ClampedArray(w * h * 4) }}),
                                       putImageData: () => {{}} }}) }};
const bytes = require('fs').readFileSync({json.dumps(str(prg32qt / 'tests' / 'fixtures' / 'Asteroids.prg32'))});
(async () => {{
  const out = {{}};
  const options = {{ base: {json.dumps(str(MODULE.parent) + '/')} }};
  let player = new PRG32CartridgePlayer(canvas, options);
  await player.load(bytes);
  out.disabled = player.debug({{ command: 'step' }});
  out.badSpeed = player.debug({{ command: 'speed', speed: 3 }});
  out.speed = player.debug({{ command: 'speed', speed: 0.01 }}).speed;
  out.enabled = player.debug({{ command: 'enable', enabled: true }}).enabled;
  const draw = player.debugState().entries.draw;
  out.badBreakpoint = player.debug({{ command: 'breakpoint', address: '0x10' }});
  out.breakpoints = player.debug({{ command: 'breakpoint', address: '0x' + draw.toString(16) }}).breakpoints;
  out.frame = player.debug({{ command: 'step_frame' }});
  out.step = player.debug({{ command: 'step' }});
  out.memory = player.debugState({{ address: draw, length: 16 }}).memory_hex;
  out.unknown = player.debug({{ command: 'explode' }});
  // A new player on the same cartridge remembers the breakpoint (same SHA-256).
  player = new PRG32CartridgePlayer(canvas, options);
  await player.load(bytes);
  out.remembered = player.debugState().breakpoints;
  console.log(JSON.stringify(out));
}})().catch(error => {{ console.error(error); process.exit(1); }});
"""
    result = run([node, "-e", script])
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["disabled"] == {"ok": False, "error": "debug mode is disabled"}
    assert out["badSpeed"]["ok"] is False and out["speed"] == 0.01 and out["enabled"] is True
    assert out["badBreakpoint"] == {"ok": False, "error": "invalid breakpoint address"}
    draw = out["breakpoints"][0]
    frame = out["frame"]
    # Qt's state fields, plus the kit's.
    for key in ("ok", "enabled", "running", "paused", "phase", "speed", "pc", "breakpoints", "registers",
                "memory_address", "memory_hex", "entries", "breakpoint_hits", "guest_ns", "wall_ms", "sha256"):
        assert key in frame
    assert frame["ok"] and frame["paused"] and frame["reason"] == "breakpoint" and frame["pc"] == draw
    assert frame["phase"] == "draw" and frame["breakpoint_hits"] == 1
    assert len(frame["registers"]) == 32 and len(frame["sha256"]) == 64
    assert out["step"]["phase"] == "draw" and out["step"]["pc"] != draw and out["step"]["reason"] == "step"
    assert len(out["memory"]) == 32
    assert out["unknown"]["ok"] is False
    assert out["remembered"] == [draw]


def test_audio_calls_reach_the_browser_host(node, prg32qt):
    script = f"""
const createPrg32Core = require({json.dumps(str(MODULE))});
const bytes = require('fs').readFileSync({json.dumps(str(prg32qt / 'tests' / 'fixtures' / 'Bach.prg32'))});
createPrg32Core().then(core => {{
  const p = core._malloc(bytes.length); core.HEAPU8.set(bytes, p);
  if (!core._prg32_load(p, bytes.length)) process.exit(3);
  const kinds = new Set(); let total = 0;
  for (let i = 0; i < 300; i++) {{
    core._prg32_frame(0);
    const n = core._prg32_audio_count(), at = core._prg32_audio_records() >> 2;
    for (let r = 0; r < n; r++) kinds.add(core.HEAP32[at + r * 12]);
    total += n; core._prg32_audio_clear();
  }}
  console.log(JSON.stringify({{total, kinds: [...kinds].sort((a, b) => a - b)}}));
}});
"""
    result = run([node, "-e", script])
    assert result.returncode == 0, result.stderr
    audio = json.loads(result.stdout)
    assert audio["total"] > 0 and all(1 <= kind <= 11 for kind in audio["kinds"])


# --- cartridges made by the kit -------------------------------------------------------

def test_kit_cartridges_run_the_same_in_the_browser_core(app, client, node, native_harness, tmp_path):
    """Blocks, Advanced C and handwritten assembly cartridges (needs the real PRG32 toolchain)."""
    if not all(ok for ok, _ in check_command(app.config["PRG32_BUILD_COMMAND"])):
        pytest.skip("PRG32 build toolchain is not installed")
    pong = json.loads((ROOT / "examples" / "games" / "pong.json").read_text())["project"]
    c_source = ('#include "prg32.h"\nvoid wasm_c_init(void) {}\nvoid wasm_c_update(void) {}\n'
                'void wasm_c_draw(void) { prg32_gfx_clear(0); prg32_gfx_rect(10, 10, 40, 20, 0xFFE0); }\n')
    asm = ("    .section .text\n    .globl wasm_asm_init\n    .globl wasm_asm_update\n    .globl wasm_asm_draw\n"
           "wasm_asm_init:\n    ret\nwasm_asm_update:\n    ret\nwasm_asm_draw:\n    ret\n")
    projects = [
        {"title": "Pong", "blocks_json": pong["blocks_json"]},
        {"title": "Wasm C", "game_json": {"source_mode": "c", "source_c": c_source}},
        {"title": "Wasm Asm", "game_json": {"source_mode": "asm", "source_asm": asm}},
        {"title": "Hello Asm", "blocks_json": default_blocks()},
    ]
    for index, payload in enumerate(projects):
        project = client.post("/api/projects", json=payload).get_json()
        body = {"architectures": ["qemu"], **({"source_language": "asm"} if index == 3 else {})}
        result = client.post(f"/api/projects/{project['id']}/package", json=body).get_json()
        assert result["build"]["status"] == "ready", result["build"]["log"]
        cartridge = tmp_path / f"{index}.prg32"
        cartridge.write_bytes(client.get(f"/api/artifacts/{result['cartridge_artifacts'][0]['id']}/download").data)
        native = native_states(native_harness, cartridge, frames=300, every=60)
        assert wasm_states(node, cartridge, frames=300, every=60) == native
        script = ("step:200", "over:20", "out", "break:update", "continue:3", "frame", "disasm:update:8")
        assert wasm_debug(node, cartridge, *script) == native_debug(native_harness, cartridge, *script)
        if payload["title"] in ("Pong", "Wasm C", "Hello Asm"):
            assert native[-1]["non_black"] > 0  # it really drew something


def test_fresh_build_matches_the_committed_module(prg32qt, tmp_path):
    """Rebuilding from the recorded PRG32-QT revision gives the same bytes (needs Emscripten)."""
    if shutil.which("emcc") is None or shutil.which("ninja") is None:
        pytest.skip("Emscripten or Ninja is not installed")
    from prg32_construction_kit.provenance import git_revision

    record = json.loads((STATIC_WASM / "BUILD.json").read_text())
    if git_revision(prg32qt) != record["core"]["revision"]:
        pytest.skip("the PRG32-QT checkout is not at the recorded revision")
    emcc = run(["emcc", "--version"]).stdout.splitlines()[0].strip()
    if emcc != record["emscripten"]:
        pytest.skip(f"different Emscripten ({emcc}); bytes are only comparable with the same one")
    result = run(["python3", str(ROOT / "tools" / "build_wasm.py"), "--prg32qt", str(prg32qt),
                  "--build-dir", str(tmp_path / "build"), "--check"])
    assert result.returncode == 0, result.stdout + result.stderr


# --- the source debugger's fixtures (refinement phase 4, ADR-0015) --------------------------

DEBUG_FIXTURES = ROOT / "tests" / "fixtures" / "debug"


def line_address(name: str, line: int) -> int:
    """The first statement address of a source line in a committed debug map."""
    rows = json.loads((DEBUG_FIXTURES / f"{name}.map.json").read_text())["lines"]
    return next(row[0] for row in rows if row[1] == 0 and row[2] == line and row[3])


@pytest.mark.parametrize("name, line", [("locals", 20), ("locals", 27), ("pong", 333), ("compressed", 31)])
def test_source_breakpoints_stop_alike_in_browser_and_native(node, native_harness, name, line):
    """Fixed checkpoints: a source-line breakpoint, more hits, single steps (16- and 32-bit), a frame."""
    cartridge = DEBUG_FIXTURES / f"{name}.prg32"
    address = line_address(name, line)
    script = (f"break:{address}", "continue", "stepi:9", "continue:3", f"unbreak:{address}", "frame:2", "state")
    native = native_debug(native_harness, cartridge, *script)
    assert native[1]["result"] == 2 and native[1]["state"]["pc"] == address
    assert "csr" in native[1]["state"]  # the counter CSRs are part of the compared state
    assert wasm_debug(node, cartridge, *script) == native


def test_compressed_fixture_steps_one_instruction_at_a_time(node, native_harness):
    cartridge = DEBUG_FIXTURES / "compressed.prg32"
    script = ["break:update", "continue", *["stepi"] * 14]
    native = native_debug(native_harness, cartridge, *script)
    assert wasm_debug(node, cartridge, *script) == native
    rows = native_debug(native_harness, cartridge, "disasm:update:16")[0]["disassembly"]
    widths = {row["address"]: row["width"] for row in rows}
    pcs = [line["state"]["pc"] for line in native[1:]]
    straight = [(a, b) for a, b in zip(pcs, pcs[1:]) if b - a in (2, 4)]
    assert {widths[a] for a, _ in straight if a in widths} == {2, 4}  # both sizes were stepped
    assert all(b - a == widths[a] for a, b in straight if a in widths)


@pytest.mark.parametrize("name, line", [("pong", 333), ("locals", 20)])
def test_source_breakpoints_do_not_change_the_game(native_harness, name, line):
    """Stopping, stepping and resuming at source breakpoints leaves the guest exactly where a plain run is."""
    cartridge = DEBUG_FIXTURES / f"{name}.prg32"
    address = line_address(name, line)
    debugged = native_debug(native_harness, cartridge, f"break:{address}", "continue:6", "stepi:20",
                            f"unbreak:{address}", "frame:12", "state")[-1]["state"]
    normal = native_states(native_harness, cartridge, frames=debugged["frames"], every=debugged["frames"])[-1]
    debugged.pop("audio_calls"), normal.pop("audio_calls")
    assert debugged == normal
