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
    configure = run(["cmake", "-S", str(ROOT / "wasm"), "-B", str(build), f"-DPRG32QT_DIR={prg32qt}",
                     "-DCMAKE_BUILD_TYPE=Release"])
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
    for path in ("/static/wasm/prg32-core.js", "/static/wasm/prg32-core.wasm", "/static/js/prg32_runtime.js"):
        assert f"'{path}'" in worker


def test_player_page_needs_a_sign_in(client, anon):
    assert client.get("/player").status_code == 200
    assert anon.get("/player").status_code in (302, 401)
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
