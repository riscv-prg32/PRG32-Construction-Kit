"""Record a cartridge's sound from the real PRG32 firmware in QEMU and compare it with the browser (ADR-0021).

    python3 tools/qemu_audio_capture.py --firmware build/qemu-audio tests/fixtures/audio/conformance.prg32 \\
        --seconds 7 --out build/audio-evidence

    python3 tools/qemu_audio_capture.py --build tests/fixtures/audio/conformance.prg32 --seconds 7 --out DIR

Opt-in evidence, not a CI test: it needs Espressif's QEMU for ESP32-C3 and a PRG32 firmware
built with the QEMU profile and the kit's overlay (--build makes one from a clean clone of
--sdk with ESP-IDF; the SDK checkout itself is never changed). The firmware
streams every 20 ms of its stereo mix (441 frames, 22050 Hz, signed 16-bit) over its second
serial port and waits for one acknowledgement byte per chunk (components/prg32_audio/audio.c,
tools/qemu_audio_player.py in the SDK); this tool is that listener.

The comparison: the firmware mixes each 20 ms chunk at once, so a note always starts at a
chunk boundary, on the console as in the kit. When a cartridge event happens (which chunk)
depends on the emulated clock, so the two recordings are aligned segment by segment: each
non-silent chunk of the browser recording is looked up in the firmware recording, and the
run of identical chunks that follows is counted. Identical means every sample equal.

Writes to --out: firmware.wav, browser.wav and comparison.json (hashes, segments, versions).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHUNK_FRAMES = 441
CHUNK_BYTES = CHUNK_FRAMES * 4          # stereo, 16-bit
OVERLAY = ROOT / "tests" / "fixtures" / "audio" / "sdkconfig.qemu-stereo"
MENU = b"setup_menu => prg32_input_read_menu()"
STARTED = b"prg32_init => cart_is_loaded()"     # printed once the cartridge runs
# Extra QEMU options, e.g. "-icount shift=3,sleep=off": emulated time from instructions, not the host.
MARGIN_CHUNKS = 10
QEMU_EXTRA = os.environ.get("PRG32_QEMU_EXTRA", "").split()
DEFAULT_QEMU = next(iter(sorted(Path.home().glob(".espressif/tools/qemu-riscv32/*/qemu/bin/qemu-system-riscv32"))),
                    None)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def build_firmware(sdk: Path, work: Path, patches: list[Path] | None = None) -> Path:
    """Build the QEMU firmware from a clean clone of the SDK checkout (never the checkout itself) with the
    kit's overlay (tests/fixtures/audio/sdkconfig.qemu-stereo): stereo output, and I2S pin numbers so the
    firmware's audio set-up accepts the QEMU board. Needs ESP-IDF (``. $HOME/esp-idf/export.sh``)."""
    source = work / "prg32"
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(sdk), str(source)], check=True)
    for patch in patches or []:          # proposed SDK changes (docs/upstream), applied to the clone only
        subprocess.run(["git", "apply", str(patch.resolve())], cwd=source, check=True)
    defaults = f"profiles/sdkconfig.defaults;profiles/sdkconfig.defaults.qemu;{OVERLAY}"
    for action in ("set-target", "build"):
        command = ["idf.py", "-B", "build-qemu", "-D", "SDKCONFIG=build-qemu/sdkconfig", "-D",
                   f"SDKCONFIG_DEFAULTS={defaults}", *(["set-target", "esp32c3"] if action == "set-target" else ["build"])]
        subprocess.run(command, cwd=source, check=True, capture_output=True)
    build = source / "build-qemu"
    esptool = ["esptool.py"] if shutil.which("esptool.py") else [sys.executable, "-m", "esptool"]   # ESP-IDF's
    subprocess.run([*esptool, "--chip=esp32c3", "merge_bin", "--output=qemu_flash.bin",
                    "--fill-flash-size=4MB", "@flash_args"], cwd=build, check=True, capture_output=True)
    sys.path.insert(0, str(source))
    cwd = os.getcwd()
    try:
        os.chdir(source)
        from prg32.utilities.environment_check import ensure_qemu_efuse

        ensure_qemu_efuse()
    finally:
        os.chdir(cwd)
    return build


def record_firmware(firmware: Path, cartridge: Path, seconds: float, sdk: Path, qemu: Path, work: Path) -> bytes:
    """The firmware's stereo chunks from the moment the cartridge starts, for ``seconds``.

    Two things QEMU needs that a person at the keyboard provides: a display that refreshes
    (Espressif's QEMU RGB panel only finishes a frame when its display is drawn, and the
    firmware waits for that; SDL's "dummy" driver draws nowhere), and Enter on RUN CARTRIDGE
    in the setup menu, typed on the first serial port.
    """
    flash = work / "qemu_flash.bin"
    shutil.copyfile(firmware / "qemu_flash.bin", flash)
    shutil.copyfile(firmware / "sdkconfig", work / "sdkconfig")
    efuse = work / "qemu_efuse.bin"
    shutil.copyfile(firmware / "qemu_efuse.bin" if (firmware / "qemu_efuse.bin").is_file()
                    else sdk / "build-qemu" / "qemu_efuse.bin", efuse)
    sys.path.insert(0, str(sdk))
    from prg32.qemu.upload_qemu import inject_cartridge

    inject_cartridge(str(cartridge), flash=str(flash))
    console_port, audio_port = free_port(), free_port()
    log = (work / "qemu.log").open("w")
    process = subprocess.Popen([str(qemu), "-M", "esp32c3", "-m", "4M",
                                "-drive", f"file={flash},if=mtd,format=raw",
                                "-drive", f"file={efuse},if=none,format=raw,id=efuse",
                                "-global", "driver=nvram.esp32c3.efuse,property=drive,value=efuse",
                                "-global", "driver=timer.esp32c3.timg,property=wdt_disable,value=true",
                                "-nic", "user,model=open_eth", "-display", "sdl", *QEMU_EXTRA,
                                "-serial", f"tcp:127.0.0.1:{console_port},server,nowait",
                                "-serial", f"tcp:127.0.0.1:{audio_port},server,wait,nodelay"],
                               stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "SDL_VIDEODRIVER": "dummy"})
    serial = bytearray()
    chunks: list[bytes] = []
    try:
        audio, console = connect(audio_port), connect(console_port)
        stop = threading.Event()

        def read_console():
            console.settimeout(0.5)
            while not stop.is_set():
                try:
                    data = console.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    return
                if not data:
                    return
                serial.extend(data)

        threading.Thread(target=read_console, daemon=True).start()
        audio.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        audio.settimeout(60)
        started, pressed, deadline = None, 0.0, time.monotonic() + 120
        # A margin after the browser's length, so an alignment shift still pairs every chunk.
        while started is None or len(chunks) - started < int(seconds * 50) + MARGIN_CHUNKS:
            if time.monotonic() > deadline:
                raise SystemExit("the cartridge did not start in QEMU (see qemu.log and firmware-serial.log)")
            if started is None and MENU in serial and time.monotonic() - pressed > 2:
                console.sendall(b"\r")                     # RUN CARTRIDGE is the first menu entry
                pressed = time.monotonic()
            if started is None and STARTED in serial:
                started = len(chunks)
            data = b""
            while len(data) < CHUNK_BYTES:
                part = audio.recv(CHUNK_BYTES - len(data))
                if not part:
                    raise SystemExit("the firmware stopped sending audio")
                data += part
            chunks.append(data)
            audio.sendall(b"K")
        stop.set()
        audio.close()
        console.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()
        (work / "serial0.log").write_bytes(bytes(serial))
    return b"".join(chunks[started:])


def connect(port: int) -> socket.socket:
    for _ in range(200):
        try:
            return socket.create_connection(("127.0.0.1", port), timeout=1)
        except OSError:
            time.sleep(0.1)
    raise SystemExit("QEMU did not open its serial ports")


def record_browser(cartridge: Path, seconds: float, work: Path) -> bytes:
    frames = int(seconds * 30) + 1
    wav = work / "browser-capture.wav"
    subprocess.run(["node", str(ROOT / "tools" / "audio_capture.mjs"), str(cartridge), str(frames), str(wav)],
                   check=True, capture_output=True, timeout=600)
    with wave.open(str(wav)) as source:
        return source.readframes(source.getnframes())


def chunks_of(pcm: bytes) -> list[bytes]:
    return [pcm[index:index + CHUNK_BYTES] for index in range(0, len(pcm) - CHUNK_BYTES + 1, CHUNK_BYTES)]


def compare(firmware: bytes, browser: bytes) -> dict:
    fw, br = chunks_of(firmware), chunks_of(browser)
    silent = bytes(CHUNK_BYTES)
    where = {}
    for index, chunk in enumerate(fw):
        where.setdefault(chunk, index)
    segments, index = [], 0
    while index < len(br):
        chunk = br[index]
        if chunk == silent or chunk not in where:
            index += 1
            continue
        start, fw_start, run = index, where[chunk], 0
        while start + run < len(br) and fw_start + run < len(fw) and br[start + run] == fw[fw_start + run]:
            run += 1
        segments.append({"browser_chunk": start, "firmware_chunk": fw_start, "identical_chunks": run,
                         "identical_ms": run * 20})
        index = start + max(run, 1)
    sounding = sum(chunk != silent for chunk in br)
    matched = sum(item["identical_chunks"] for item in segments if br[item["browser_chunk"]] != silent)
    return {"browser_chunks": len(br), "firmware_chunks": len(fw), "browser_sounding_chunks": sounding,
            "identical_sounding_chunks": matched, "segments": segments}


def aligned(firmware: bytes, browser: bytes, reach: int = 10) -> dict:
    """The whole recordings at one fixed alignment (the best shift of up to ``reach`` chunks):
    how many 20 ms chunks are equal sample for sample, and whether all of them are."""
    fw, br = chunks_of(firmware), chunks_of(browser)
    best = None
    for shift in range(-reach, reach + 1):
        pairs = [(br[i], fw[i + shift]) for i in range(len(br)) if 0 <= i + shift < len(fw)]
        equal = sum(a == b for a, b in pairs)
        if best is None or equal > best["equal_chunks"]:
            best = {"shift_chunks": shift, "equal_chunks": equal, "compared_chunks": len(pairs),
                    "differing_chunks": [i for i in range(len(br)) if 0 <= i + shift < len(fw) and br[i] != fw[i + shift]]}
    # Whole-recording equality: every browser chunk has its firmware chunk at that one shift,
    # and they are all equal - so the aligned firmware slice hashes like the browser's PCM.
    shift = best["shift_chunks"]
    covered = best["compared_chunks"] == len(br) and len(br) > 0
    best["whole_recording_equal"] = covered and not best["differing_chunks"]
    if covered:
        best["firmware_aligned_sha256"] = hashlib.sha256(b"".join(fw[shift:shift + len(br)])).hexdigest()
    best["browser_sha256"] = hashlib.sha256(b"".join(br)).hexdigest()
    return best


def write_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(22050)
        out.writeframes(pcm)


def qemu_version(qemu: Path) -> str:
    try:
        return subprocess.run([str(qemu), "--version"], capture_output=True, text=True, timeout=30).stdout.splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return qemu.name


def revision(path: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cartridge", type=Path)
    parser.add_argument("--firmware", type=Path, help="folder with qemu_flash.bin and sdkconfig (else --build)")
    parser.add_argument("--build", action="store_true", help="build the QEMU firmware from --sdk first (ESP-IDF)")
    parser.add_argument("--patch", type=Path, action="append", default=[],
                        help="with --build: apply this SDK patch to the clone first; with --firmware: a patch that "
                             "firmware was built with (recorded only). Repeatable")
    parser.add_argument("--sdk", type=Path, default=Path(os.environ.get("PRG32_SOURCE") or ROOT.parent / "PRG32"))
    parser.add_argument("--qemu", type=Path, default=DEFAULT_QEMU)
    parser.add_argument("--seconds", type=float, default=7.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not args.qemu or not Path(args.qemu).is_file():
        print("Espressif's qemu-system-riscv32 was not found (--qemu)", file=sys.stderr)
        return 2
    if not args.firmware and not args.build:
        parser.error("give --firmware or --build")
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        if args.build:
            args.firmware = build_firmware(args.sdk.resolve(), Path(tmp), args.patch)
            shutil.copyfile(args.firmware / "sdkconfig", args.out / "firmware-sdkconfig")
        try:
            firmware = record_firmware(args.firmware.resolve(), args.cartridge.resolve(), args.seconds,
                                       args.sdk.resolve(), Path(args.qemu), Path(tmp))
        finally:
            for name, kept in (("serial0.log", "firmware-serial.log"), ("qemu.log", "qemu.log")):
                if (Path(tmp) / name).is_file():
                    shutil.copyfile(Path(tmp) / name, args.out / kept)
        browser = record_browser(args.cartridge.resolve(), args.seconds, Path(tmp))
        flash_sha256 = hashlib.sha256((args.firmware / "qemu_flash.bin").read_bytes()).hexdigest()
    write_wav(args.out / "firmware.wav", firmware)
    write_wav(args.out / "browser.wav", browser)
    report = {
        "cartridge": {"file": args.cartridge.name, "sha256": hashlib.sha256(args.cartridge.read_bytes()).hexdigest()},
        "firmware": {"sdk_revision": revision(args.sdk), "flash_sha256": flash_sha256, "qemu": qemu_version(Path(args.qemu)),
                     "patches": [{"file": patch.name, "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}
                                 for patch in args.patch],
                     "overlay": OVERLAY.read_text()},
        "kit_revision": revision(ROOT),
        "seconds": args.seconds,
        "firmware_pcm_sha256": hashlib.sha256(firmware).hexdigest(),
        "browser_pcm_sha256": hashlib.sha256(browser).hexdigest(),
        "qemu_options": QEMU_EXTRA,
        "aligned": aligned(firmware, browser),
        **compare(firmware, browser),
    }
    (args.out / "comparison.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({key: report[key] for key in ("browser_sounding_chunks", "identical_sounding_chunks")}))
    print(json.dumps({key: value for key, value in report["aligned"].items() if key != "differing_chunks"}))
    for segment in report["segments"]:
        print(segment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
