"""Check that cartridge builds work, and stay apart, before a class starts.

Used by ``tools/check_build.py`` (for teachers) and by the tests. The
classroom check signs in several students, opens several "browser windows"
for each one, and lets them all compile at the same moment. Then it checks
that every student got a real cartridge of *their own* game, and that nobody
can download a classmate's cartridge.
"""

from __future__ import annotations

import shlex
import shutil
import struct
import subprocess
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any

from .packager import SUPPORTED_ARCHITECTURES, slugify
from .sample_data import default_blocks, starter_project

CARTRIDGE_MAGIC = b"PRG2"
# PRG32 cartridge header: magic, 4 small numbers, 7 words, then a 32-byte name.
_NAME_OFFSET = struct.calcsize("<4sHHHHIIIIIII")


def cartridge_name(data: bytes) -> str | None:
    """The game name stored in a PRG32 cartridge header, or None if it is not a cartridge."""
    if len(data) < _NAME_OFFSET + 32 or not data.startswith(CARTRIDGE_MAGIC):
        return None
    return data[_NAME_OFFSET:_NAME_OFFSET + 32].split(b"\0", 1)[0].decode("ascii", "replace")


def check_command(build_command: str, tool_prefix: str = "riscv32-esp-elf-") -> list[tuple[bool, str]]:
    """Quick checks of the build command and the RISC-V compiler. Each line is (ok, message)."""
    lines: list[tuple[bool, str]] = []
    try:
        result = subprocess.run(shlex.split(build_command) + ["--help"], capture_output=True, text=True, timeout=60)
        ok = result.returncode == 0
        detail = "" if ok else (result.stderr or result.stdout).strip().splitlines()[-1:] or [""]
        lines.append((ok, f"build command runs: {build_command}" + ("" if ok else f" ({detail[0]})")))
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        lines.append((False, f"build command runs: {build_command} ({exc})"))
    gcc = shutil.which(tool_prefix + "gcc")
    lines.append((gcc is not None, f"RISC-V compiler on PATH: {gcc or tool_prefix + 'gcc not found'}"))
    return lines


def toolchain_present(build_command: str, tool_prefix: str = "riscv32-esp-elf-") -> bool:
    """A quick look (no program is run): is the compiler on PATH and can the build command start?

    Used after a build that made no cartridge, to tell "this server has no
    build tools" (a source-only bundle) from "the compiler refused the source"
    (a failed build).
    """
    import importlib.util
    import sys
    from pathlib import Path

    if shutil.which(tool_prefix + "gcc") is None:
        return False
    try:
        parts = shlex.split(build_command)
    except ValueError:
        return False
    if not parts or (shutil.which(parts[0]) is None and not Path(parts[0]).is_file()):
        return False
    # "<this python> -m prg32 ...": the module must be importable here too.
    if len(parts) > 2 and parts[1] == "-m" and Path(parts[0]).resolve() == Path(sys.executable).resolve():
        return importlib.util.find_spec(parts[2].split(".")[0]) is not None
    return True


@lru_cache(maxsize=4)
def builds_available(build_command: str, tool_prefix: str = "riscv32-esp-elf-") -> bool:
    """True when this server can compile PRG32 cartridges. Checked once per server process."""
    return all(ok for ok, _message in check_command(build_command, tool_prefix))


def classroom_check(app, students: int = 3, windows: int = 2, password: str = "check-build-password-1",
                    architectures: list[str] | None = None) -> dict[str, Any]:
    """Build at the same time as ``students`` users, each in ``windows`` browser windows.

    ``app`` must be a Construction Kit app with its own, throwaway data folder,
    and its test client must sign in as the admin by default (see tests/conftest.py
    and tools/check_build.py).
    """
    architectures = architectures or list(SUPPORTED_ARCHITECTURES)
    admin = app.test_client()
    names = [f"student{n + 1}" for n in range(students)]
    projects: dict[str, dict[str, Any]] = {}
    for name in names:
        response = admin.post("/api/users", json={"username": name, "email": f"{name}@school.test",
                                                  "password": password, "role": "user"})
        if response.status_code not in (201, 409):
            raise RuntimeError(f"could not create {name}: {response.get_json()}")
        client = app.test_client(login=(name, password))
        project = client.post("/api/projects", json={"title": f"Lab Check {name}",
                                                     "blocks_json": default_blocks()}).get_json()
        projects[name] = project

    jobs = [(name, window, arch) for name in names for window in range(windows) for arch in architectures]

    def build(job):
        name, window, arch = job
        client = app.test_client(login=(name, password))  # one browser window = one client
        project = projects[name]
        response = client.post(f"/api/projects/{project['id']}/package",
                               json={"architectures": [arch], "expected_blocks_json": project["blocks_json"]})
        body = response.get_json() or {}
        outcome = {"student": name, "window": window, "architecture": arch, "status_code": response.status_code,
                   "slug": slugify(project["title"]), "error": body.get("error"), "log": ""}
        if response.status_code != 200:
            return outcome
        outcome["build_id"] = body["build"]["id"]
        outcome["build_status"] = body["build"]["status"]
        outcome["log"] = body["result"].get("log", "")
        cartridges = body.get("cartridge_artifacts", [])
        if cartridges:
            outcome["artifact_id"] = cartridges[0]["id"]
            outcome["data"] = client.get(f"/api/artifacts/{cartridges[0]['id']}/download").data
        return outcome

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        results = list(pool.map(build, jobs))

    problems: list[str] = []
    for item in results:
        where = f"{item['student']} window {item['window'] + 1} ({item['architecture']})"
        if item["status_code"] != 200:
            problems.append(f"{where}: HTTP {item['status_code']} {item['error']}")
        elif item.get("build_status") != "ready" or "data" not in item:
            last = item["log"].strip().splitlines()[-1:] or ["no log"]
            problems.append(f"{where}: no cartridge was built ({last[0]})")
        else:
            found = cartridge_name(item["data"])
            if found is not None and found != item["slug"]:
                problems.append(f"{where}: got the cartridge of '{found}' instead of '{item['slug']}'")
            elif found is None and item["build_id"].encode() not in item["data"]:
                problems.append(f"{where}: the downloaded file is not a PRG32 cartridge")
    if len({item.get("build_id") for item in results if item.get("build_id")}) != len(
            [item for item in results if item.get("build_id")]):
        problems.append("two builds shared one build id")

    # A classmate must not be able to download somebody else's cartridge.
    built = [item for item in results if item.get("artifact_id")]
    if len(names) > 1 and built:
        owner = built[0]["student"]
        other = next(name for name in names if name != owner)
        peek = app.test_client(login=(other, password)).get(f"/api/artifacts/{built[0]['artifact_id']}/download")
        if peek.status_code != 404:
            problems.append(f"{other} could download {owner}'s cartridge")

    return {"builds": len(results), "cartridges": len(built), "problems": problems, "results": results}


# One small game per way of writing it (docs/install_cartridge_build.md): Blocks (built from its
# generated C, and from its generated RISC-V assembly), Advanced C and handwritten assembly.
MODE_C_SOURCE = """#include "prg32.h"

/* Advanced C build check: a box that moves one pixel every frame. */
static int x;

void mode_check_c_init(void) { x = 0; }
void mode_check_c_update(void) { x = (x + 1) % 300; }
void mode_check_c_draw(void) {
    prg32_gfx_clear(PRG32_COLOR_BLACK);
    prg32_gfx_rect(x, 100, 20, 20, PRG32_COLOR_YELLOW);
}
"""
MODE_ASM_SOURCE = """/* Handwritten assembly build check: count the frames, draw a green screen. */
    .option norelax
    .section .data
    .balign 4
frames: .word 0
    .section .text
    .globl mode_check_asm_init
    .globl mode_check_asm_update
    .globl mode_check_asm_draw
mode_check_asm_init:
    ret
mode_check_asm_update:
    la   t0, frames
    lw   t1, 0(t0)
    addi t1, t1, 1
    sw   t1, 0(t0)
    ret
mode_check_asm_draw:
    addi sp, sp, -16
    sw   ra, 12(sp)
    li   a0, 0x07E0              # clear the screen to green (RGB565)
    call prg32_gfx_clear
    lw   ra, 12(sp)
    addi sp, sp, 16
    ret
"""


def runs(cartridge: bytes, frames: int = 30) -> bool | None:
    """Does the cartridge load and run ``frames`` frames in the browser core (static/wasm)? None without Node.js."""
    import tempfile
    from pathlib import Path

    capture = Path(__file__).resolve().parent.parent / "tools" / "audio_capture.mjs"
    if shutil.which("node") is None or not capture.is_file():
        return None
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "check.prg32"
        path.write_bytes(cartridge)
        result = subprocess.run(["node", str(capture), str(path), str(frames)], capture_output=True, timeout=120)
    return result.returncode == 0


def source_modes_check(app, architectures: list[str] | None = None, keep: Any = None) -> dict[str, Any]:
    """Build a real cartridge from each way of writing a game, for each target, as the admin.

    Returns ``{"results": [...], "problems": [...]}``; each result has the mode, the target,
    the build id and the cartridge's size and SHA-256 (for the evidence record)."""
    import hashlib

    architectures = architectures or list(SUPPORTED_ARCHITECTURES)
    client = app.test_client()
    blocks = client.post("/api/projects", json={"title": "Mode Check Blocks", "blocks_json": default_blocks()}).get_json()
    c_game = {"source_mode": "c", "source_c": MODE_C_SOURCE, "required_features": []}
    asm_game = {"source_mode": "asm", "source_asm": MODE_ASM_SOURCE, "required_features": []}
    c_project = client.post("/api/projects", json={"title": "Mode Check C", "game_json": c_game}).get_json()
    asm_project = client.post("/api/projects", json={"title": "Mode Check Asm", "game_json": asm_game}).get_json()
    python_game = starter_project("python", "Mode Check Python")["game_json"]
    python_project = client.post("/api/projects", json={"title": "Mode Check Python", "game_json": python_game}).get_json()
    modes = [("blocks (generated C)", blocks, "c"), ("blocks (generated assembly)", blocks, "asm"),
             ("advanced C", c_project, "c"), ("handwritten assembly", asm_project, "asm"),
             ("python (generated C)", python_project, "c"), ("python (generated assembly)", python_project, "asm")]
    results, problems = [], []
    for mode, project, language in modes:
        for arch in architectures:
            response = client.post(f"/api/projects/{project['id']}/package",
                                   json={"architectures": [arch], "source_language": language})
            body = response.get_json() or {}
            where = f"{mode} ({arch})"
            cartridges = body.get("cartridge_artifacts") or []
            if response.status_code != 200 or not cartridges:
                log = ((body.get("result") or {}).get("log") or body.get("error") or "").strip().splitlines()[-3:]
                problems.append(f"{where}: no cartridge was built ({' / '.join(log) or response.status_code})")
                continue
            data = client.get(f"/api/artifacts/{cartridges[0]['id']}/download").data
            if data[:4] != b"PRG2":
                problems.append(f"{where}: the downloaded file is not a PRG32 cartridge")
                continue
            if keep is not None:      # a folder: keep the cartridge (e.g. to deliver it to a console)
                name = mode.replace(" (", "-").replace(")", "").replace(" ", "-")
                (keep / f"{name}-{arch}.prg32").write_bytes(data)
            results.append({"mode": mode, "architecture": arch, "source_language": language,
                            "build_id": body["build"]["id"], "bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(), "runs_in_browser_core": runs(data)})
            if results[-1]["runs_in_browser_core"] is False:
                problems.append(f"{where}: the cartridge does not run in the browser core")
    return {"results": results, "problems": problems}
