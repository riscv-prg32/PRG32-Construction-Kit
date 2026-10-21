"""Record a cartridge's sound from the real PRG32 firmware in QEMU and compare it with the browser (ADR-0021).

    python3 tools/qemu_audio_capture.py --firmware build/qemu-audio tests/fixtures/audio/conformance.prg32 \\
        --seconds 7 --out build/audio-evidence

Opt-in evidence, not a CI test: it needs Espressif's QEMU for ESP32-C3 and a PRG32 firmware
built with the QEMU, CI and stereo profiles (docs/audio_engine.md says how). The firmware
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
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHUNK_FRAMES = 441
CHUNK_BYTES = CHUNK_FRAMES * 4          # stereo, 16-bit
DEFAULT_QEMU = next(iter(sorted(Path.home().glob(".espressif/tools/qemu-riscv32/*/qemu/bin/qemu-system-riscv32"))),
                    None)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def record_firmware(firmware: Path, cartridge: Path, seconds: float, sdk: Path, qemu: Path, work: Path) -> bytes:
    flash = work / "qemu_flash.bin"
    shutil.copyfile(firmware / "qemu_flash.bin", flash)
    shutil.copyfile(firmware / "sdkconfig", work / "sdkconfig")
    efuse = work / "qemu_efuse.bin"
    shutil.copyfile(sdk / "build-qemu" / "qemu_efuse.bin", efuse)
    sys.path.insert(0, str(sdk))
    from prg32.qemu.upload_qemu import inject_cartridge

    inject_cartridge(str(cartridge), flash=str(flash))
    port = free_port()
    log = (work / "firmware.log").open("w")
    process = subprocess.Popen([str(qemu), "-M", "esp32c3", "-m", "4M",
                                "-drive", f"file={flash},if=mtd,format=raw",
                                "-drive", f"file={efuse},if=none,format=raw,id=efuse",
                                "-global", "driver=nvram.esp32c3.efuse,property=drive,value=efuse",
                                "-global", "driver=timer.esp32c3.timg,property=wdt_disable,value=true",
                                "-nic", "user,model=open_eth", "-display", "none",
                                "-serial", f"file:{work / 'serial0.log'}",
                                "-serial", f"tcp:127.0.0.1:{port},server,wait,nodelay"],
                               stdout=log, stderr=subprocess.STDOUT)
    chunks = []
    try:
        for _ in range(200):
            try:
                connection = socket.create_connection(("127.0.0.1", port), timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise SystemExit("QEMU did not open its audio port")
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        connection.settimeout(60)
        wanted = int(seconds * 50)
        while len(chunks) < wanted:
            data = b""
            while len(data) < CHUNK_BYTES:
                part = connection.recv(CHUNK_BYTES - len(data))
                if not part:
                    raise SystemExit("the firmware stopped sending audio")
                data += part
            chunks.append(data)
            connection.sendall(b"K")
        connection.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()
    return b"".join(chunks)


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


def write_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(22050)
        out.writeframes(pcm)


def revision(path: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cartridge", type=Path)
    parser.add_argument("--firmware", type=Path, required=True, help="folder with qemu_flash.bin and sdkconfig")
    parser.add_argument("--sdk", type=Path, default=Path(os.environ.get("PRG32_SOURCE") or ROOT.parent / "PRG32"))
    parser.add_argument("--qemu", type=Path, default=DEFAULT_QEMU)
    parser.add_argument("--seconds", type=float, default=7.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not args.qemu or not Path(args.qemu).is_file():
        print("Espressif's qemu-system-riscv32 was not found (--qemu)", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        firmware = record_firmware(args.firmware.resolve(), args.cartridge.resolve(), args.seconds + 3,
                                   args.sdk.resolve(), Path(args.qemu), Path(tmp))
        browser = record_browser(args.cartridge.resolve(), args.seconds, Path(tmp))
        shutil.copyfile(Path(tmp) / "serial0.log", args.out / "firmware-serial.log")
    write_wav(args.out / "firmware.wav", firmware)
    write_wav(args.out / "browser.wav", browser)
    report = {
        "cartridge": {"file": args.cartridge.name, "sha256": hashlib.sha256(args.cartridge.read_bytes()).hexdigest()},
        "firmware": {"sdk_revision": revision(args.sdk), "flash_sha256": hashlib.sha256(
            (args.firmware / "qemu_flash.bin").read_bytes()).hexdigest(), "qemu": str(args.qemu)},
        "kit_revision": revision(ROOT),
        "firmware_pcm_sha256": hashlib.sha256(firmware).hexdigest(),
        "browser_pcm_sha256": hashlib.sha256(browser).hexdigest(),
        **compare(firmware, browser),
    }
    (args.out / "comparison.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({key: report[key] for key in ("browser_sounding_chunks", "identical_sounding_chunks")}))
    for segment in report["segments"]:
        print(segment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
