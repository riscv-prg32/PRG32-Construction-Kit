#!/usr/bin/env python3
"""Check the example projects on real PRG32 runtimes and capture screenshots.

For each example this tool runs the whole Construction Kit pipeline outside the
web app:

    Blocks JSON -> game IR -> C -> .prg32 (qemu and esp32c6)

and then, when the runtimes are available:

* PRG32-QT: runs the qemu cartridge in the headless runner with scripted
  button presses and dumps the final frame;
* QEMU: stages the cartridge in a copy of the PRG32 QEMU flash image, boots the
  firmware, types keys on the console UART, and reads the 320x240 framebuffer
  through QEMU's GDB stub (the Espressif QEMU build has no screendump);
* the Construction Kit browser simulator (Node.js) with the same buttons.

Requirements (all optional except the PRG32 checkout):

    --prg32 PATH       PRG32 checkout (python3 -m prg32 must work from it)
    --qt-runner PATH   prg32qt-headless from a PRG32-QT build
    --qemu             also run QEMU; needs `python3 -m prg32 qemu build` done
                       in the PRG32 checkout with the cicd profile (boots the
                       staged cartridge) and Espressif's qemu-system-riscv32
                       and riscv32-esp-elf-gdb on PATH. QEMU opens an SDL window.

Example:

    python3 tools/runtime_check.py --prg32 ../PRG32 \\
        --qt-runner ../PRG32-QT/build-core/prg32qt-headless --qemu --out /tmp/prg32-check
"""

from __future__ import annotations

import argparse
import json
import os
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Load only the generator (pure standard library), not the Flask app, so this
# tool also runs inside the ESP-IDF Python environment.
_package = types.ModuleType("prg32_construction_kit")
_package.__path__ = [str(ROOT / "prg32_construction_kit")]
sys.modules.setdefault("prg32_construction_kit", _package)

from prg32_construction_kit.generator import blocks_to_c  # noqa: E402

BITS = {"LEFT": 1, "RIGHT": 2, "UP": 4, "DOWN": 8, "A": 16, "B": 32, "START": 64}
QEMU_KEYS = {"LEFT": "a", "RIGHT": "d", "UP": "w", "DOWN": "s", "A": "z", "B": "x", "START": " "}

# Button scripts: frame ranges at 30 frames per second. The same script drives
# PRG32-QT, the simulator, and (converted to seconds) QEMU.
SCRIPTS = {
    "pong": (260, ["20-60:UP", "100-150:DOWN"]),
    "breakout": (300, ["10:A", "40-70:LEFT", "120-150:RIGHT"]),
    "space_invaders": (300, ["5:START", "20-60:LEFT", "70:A", "120:A", "150-170:RIGHT", "180:A"]),
    "asteroids": (240, ["5:START", "20-40:LEFT", "50-70:UP", "80:A", "100:A", "130:A"]),
    "snake": (200, ["5:START", "60-62:UP", "110-112:LEFT"]),
    "feature_tour": (120, ["30-50:RIGHT", "60:A"]),
}


def example_files() -> dict[str, Path]:
    files = {path.stem: path for path in sorted((ROOT / "examples" / "games").glob("*.json"))}
    files["feature_tour"] = ROOT / "examples" / "feature_tour.json"
    return files


def parse_script(script: list[str]) -> dict[int, int]:
    masks: dict[int, int] = {}
    for item in script:
        span, _, buttons = item.partition(":")
        first, _, last = span.partition("-")
        for frame in range(int(first), int(last or first) + 1):
            for name in buttons.split("+"):
                masks[frame] = masks.get(frame, 0) | BITS[name]
    return masks


def save_image(ppm: Path, png: Path, scale: int = 2) -> Path:
    """Convert a PPM frame to a PNG scaled with nearest-neighbour pixels (needs Pillow)."""
    try:
        from PIL import Image
    except ImportError:
        return ppm
    image = Image.open(ppm)
    image = image.resize((image.width * scale, image.height * scale), Image.NEAREST)
    image.save(png, optimize=True)
    return png


def build_cartridges(name: str, path: Path, prg32: Path, out: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", data)
    ir, source = blocks_to_c(project["blocks_json"], project)
    c_file = out / f"{name}.c"
    c_file.write_text(source, encoding="utf-8")
    result = {"warnings": ir["warnings"], "features": ir["required_features"], "c_lines": len(source.splitlines())}
    for arch in ("qemu", "esp32c6"):
        command = [sys.executable, "-m", "prg32", "cartridge", "build", str(c_file), "--portable",
                   "--architecture", arch, "--cart-ram-kib", "64", "--entry-prefix", ir["entry_prefix"],
                   "--name", name, "--out", str(out / f"{name}-{arch}.prg32")]
        for feature in ir["required_features"]:
            command += ["--required-feature", feature]
        if "multiplayer" in ir["required_features"]:
            command.append("--multiplayer")
        proc = subprocess.run(command, cwd=prg32, capture_output=True, text=True)
        size = next((line.split("code=")[1].split()[0] for line in proc.stdout.splitlines() if "code=" in line), "?")
        result[arch] = {"ok": proc.returncode == 0, "code_bytes": size,
                        "log": "" if proc.returncode == 0 else (proc.stdout + proc.stderr)[-2000:]}
    return result


def run_qt(runner: Path, cart: Path, frames: int, script: list[str], ppm: Path) -> dict:
    args = [str(runner), str(cart), str(frames), "--unlimited"]
    for frame, mask in sorted(parse_script(script).items()):
        args += ["--input", f"{frame}:{mask}"]
    args += ["--dump-ppm", str(ppm)]
    proc = subprocess.run(args, capture_output=True, text=True)
    return {"ok": proc.returncode == 0, "output": (proc.stdout + proc.stderr).strip()}


def run_simulator(path: Path, frames: int, script: list[str], ppm: Path) -> dict:
    proc = subprocess.run(["node", str(ROOT / "tools" / "simulate.js"), str(path), str(frames), str(ppm), *script],
                          capture_output=True, text=True)
    return {"ok": proc.returncode == 0, "state": json.loads(proc.stdout)["state"] if proc.returncode == 0 else proc.stderr}


def run_qemu(prg32: Path, cart: Path, frames: int, script: list[str], ppm: Path, boot_seconds: float = 8.0) -> dict:
    """Boot PRG32 firmware in QEMU with the cartridge staged in slot cart0."""
    work = Path(tempfile.mkdtemp(prefix="qd", dir="/tmp"))  # short path: QEMU sockets and pipes
    try:
        flash = work / "flash.bin"
        shutil.copy(prg32 / "build-qemu" / "qemu_flash.bin", flash)
        subprocess.check_call([sys.executable, "-m", "prg32", "qemu", "upload", str(cart), "--flash", str(flash)],
                              cwd=prg32, stdout=subprocess.DEVNULL)
        for fifo in ("c.in", "c.out", "a.in", "a.out"):
            os.mkfifo(work / fifo)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        gdb_port = sock.getsockname()[1]
        sock.close()
        qemu = subprocess.Popen([
            "qemu-system-riscv32", "-M", "esp32c3", "-m", "4M",
            "-drive", f"file={flash},if=mtd,format=raw",
            "-drive", f"file={prg32 / 'build-qemu' / 'qemu_efuse.bin'},if=none,format=raw,id=efuse",
            "-global", "driver=nvram.esp32c3.efuse,property=drive,value=efuse",
            "-global", "driver=timer.esp32c3.timg,property=wdt_disable,value=true",
            "-nic", "user,model=open_eth", "-display", "sdl",
            "-serial", "pipe:c", "-serial", "pipe:a", "-gdb", f"tcp:127.0.0.1:{gdb_port}",
        ], cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        console_in = os.open(work / "c.in", os.O_WRONLY)
        console_out = os.open(work / "c.out", os.O_RDONLY | os.O_NONBLOCK)
        audio_in = os.open(work / "a.in", os.O_WRONLY)
        audio_out = os.open(work / "a.out", os.O_RDONLY | os.O_NONBLOCK)
        os.write(audio_in, b"K" * 10)  # audio flow-control credits (see PRG32 docs/usage/qemu.md)
        log = bytearray()
        pending = [0]

        def pump(seconds: float) -> None:
            end = time.time() + seconds
            while time.time() < end:
                ready, _, _ = select.select([console_out, audio_out], [], [], 0.02)
                if console_out in ready:
                    log.extend(os.read(console_out, 65536))
                if audio_out in ready:
                    pending[0] += len(os.read(audio_out, 65536))
                    while pending[0] >= 882:  # one credit per 20 ms PCM chunk
                        pending[0] -= 882
                        os.write(audio_in, b"K")

        # Convert the frame script to key presses at 30 frames per second.
        events = sorted((frame, name) for item in script for frame, name in _expand(item))
        start = time.time()
        pump(boot_seconds)
        for frame, name in events:
            pump(max(0.0, boot_seconds + frame / 30 - (time.time() - start)))
            os.write(console_in, QEMU_KEYS[name].encode())
        pump(max(0.0, boot_seconds + frames / 30 - (time.time() - start)))
        ok = _gdb_framebuffer(prg32, gdb_port, ppm, pump)
        qemu.terminate()
        qemu.wait()
        text = log.decode("utf-8", "replace")
        loaded = [line for line in text.splitlines() if "loaded cartridge" in line]
        return {"ok": ok and bool(loaded), "loaded": loaded[-1] if loaded else "cartridge not loaded"}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _expand(item: str):
    span, _, buttons = item.partition(":")
    first, _, last = span.partition("-")
    # QEMU's UART key mapper holds a key briefly; repeat it every 3 frames while held.
    for frame in range(int(first), int(last or first) + 1, 3):
        for name in buttons.split("+"):
            yield frame, name


def _gdb_framebuffer(prg32: Path, port: int, ppm: Path, pump) -> bool:
    """Stop at the next prg32_gfx_present and copy the firmware framebuffer g_fb."""
    elf = prg32 / "build-qemu" / "PRG32.elf"
    symbols = {}
    nm = subprocess.run(["riscv32-esp-elf-nm", str(elf)], capture_output=True, text=True).stdout
    for line in nm.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] in ("g_fb", "prg32_gfx_present"):
            symbols[parts[2]] = int(parts[0], 16)
    raw = ppm.with_suffix(".rgb565")
    base = symbols["g_fb"]
    commands = ["set pagination off", "set confirm off", f"target remote 127.0.0.1:{port}",
                f"hbreak *0x{symbols['prg32_gfx_present']:x}", "continue", "delete",
                f"dump binary memory {raw} 0x{base:x} 0x{base + 320 * 240 * 2:x}", "detach"]
    gdb = shutil.which("riscv32-esp-elf-gdb-no-python") or "riscv32-esp-elf-gdb"
    args = [gdb, "-nx", "-batch"]
    for command in commands:
        args += ["-ex", command]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while proc.poll() is None:
        pump(0.05)
    if not raw.exists():
        return False
    data = raw.read_bytes()
    raw.unlink()
    with ppm.open("wb") as out:
        out.write(b"P6\n320 240\n255\n")
        for i in range(0, len(data), 2):
            pixel = data[i] | (data[i + 1] << 8)
            out.write(bytes((((pixel >> 11) & 31) * 255 // 31, ((pixel >> 5) & 63) * 255 // 63, (pixel & 31) * 255 // 31)))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prg32", type=Path, required=True)
    parser.add_argument("--qt-runner", type=Path)
    parser.add_argument("--qemu", action="store_true")
    parser.add_argument("--out", type=Path, default=Path(tempfile.gettempdir()) / "prg32-runtime-check")
    parser.add_argument("--figures", type=Path, help="also write scaled PNG screenshots here (needs Pillow)")
    parser.add_argument("examples", nargs="*", help="example names (default: all)")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    report = {}
    failures = 0
    for name, path in example_files().items():
        if args.examples and name not in args.examples:
            continue
        frames, script = SCRIPTS[name]
        entry = build_cartridges(name, path, args.prg32.resolve(), args.out)
        if shutil.which("node"):
            ppm = args.out / f"{name}-simulator.ppm"
            entry["simulator"] = run_simulator(path, frames, script, ppm)
            if args.figures:
                save_image(ppm, args.figures / f"{name}-simulator.png")
        if args.qt_runner and entry["qemu"]["ok"]:
            ppm = args.out / f"{name}-prg32qt.ppm"
            entry["prg32qt"] = run_qt(args.qt_runner, args.out / f"{name}-qemu.prg32", frames, script, ppm)
            if args.figures and entry["prg32qt"]["ok"]:
                save_image(ppm, args.figures / f"{name}-prg32qt.png")
        if args.qemu and entry["qemu"]["ok"]:
            ppm = args.out / f"{name}-qemu.ppm"
            entry["qemu_run"] = run_qemu(args.prg32.resolve(), args.out / f"{name}-qemu.prg32", frames, script, ppm)
            if args.figures and entry["qemu_run"]["ok"]:
                save_image(ppm, args.figures / f"{name}-qemu.png")
        checks = [entry["qemu"]["ok"], entry["esp32c6"]["ok"], not entry["warnings"]]
        checks += [entry[key]["ok"] for key in ("simulator", "prg32qt", "qemu_run") if key in entry]
        entry["passed"] = all(checks)
        failures += not entry["passed"]
        report[name] = entry
        print(f"{name:15s} {'PASS' if entry['passed'] else 'FAIL'}  code={entry['qemu']['code_bytes']} bytes"
              f"  features={','.join(entry['features']) or '-'}"
              + "".join(f"  {key}={'ok' if entry[key]['ok'] else 'FAIL'}" for key in ("simulator", "prg32qt", "qemu_run") if key in entry),
              flush=True)
    (args.out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"report: {args.out / 'report.json'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
