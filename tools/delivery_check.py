"""Put kit PRG32 cartridges on a PRG32 console or PRG32-QT and record what happened (docs/delivery.md).

    python3 tools/delivery_check.py record  game.prg32 ...                 # hashes only
    python3 tools/delivery_check.py device --url http://192.168.4.1 --slot cart7 game.prg32 ...

``device`` speaks the HTTP API that both the PRG32 firmware (over its Wi-Fi) and
PRG32-QT (port 8080) offer, the same one ``python3 -m prg32 esp32c6 upload`` uses:

1. ``GET  /api/runtime``                  which firmware/host answers;
2. ``POST /api/games?slot=<slot>``        store the cartridge in that slot;
3. ``POST /api/games/select?slot=<slot>`` start it;
4. ``GET  /api/screenshot.bmp``           after a few seconds: is something drawn?

The slot is required on purpose: uploading replaces what is in it, so the teacher picks
one they do not need (``cart7``, say). Nothing is sent anywhere except the ``--url``
given. The record (JSON) has, per cartridge: SHA-256, size, header fields, the slot,
each answer, the screenshot's SHA-256 and whether it has any non-black pixel, and an
outcome (``launched``, ``refused`` or ``failed``); plus the kit and PRG32 SDK commits.
Add ``--notes`` for what you saw (a launched cartridge that misbehaves is still a
finding).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
SLOTS = [f"cart{number}" for number in range(8)]
TIMEOUT = 30


def git_commit(path: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=10, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def cartridge_facts(path: Path) -> dict:
    data = path.read_bytes()
    facts = {"file": path.name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    if data[:4] != b"PRG2" or len(data) < 20:
        raise SystemExit(f"{path} is not a PRG32 cartridge (no PRG2 header)")
    facts["header_size"], facts["code_size"] = struct.unpack_from("<I", data, 8)[0], struct.unpack_from("<I", data, 16)[0]
    return facts


def drawn_something(bmp: bytes) -> bool:
    """True if the BMP screenshot has any non-black pixel."""
    if bmp[:2] != b"BM" or len(bmp) < 14:
        return False
    offset = struct.unpack_from("<I", bmp, 10)[0]
    return any(bmp[offset:])


def http(method: str, url: str, body: bytes | None = None) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, method=method,
                                     headers={"Content-Type": "application/octet-stream"} if body is not None else {})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def check_on_device(url: str, slot: str, cartridge: Path, wait: float) -> dict:
    facts = cartridge_facts(cartridge)
    base = url.rstrip("/")
    try:
        status, runtime = http("GET", base + "/api/runtime")
        facts["runtime"] = json.loads(runtime or b"{}") if status == 200 else {"status": status}
        status, answer = http("POST", f"{base}/api/games?slot={slot}", cartridge.read_bytes())
        facts["upload"] = {"status": status, "answer": answer.decode("utf-8", "replace")[:500]}
        if status != 200:
            return {**facts, "outcome": "refused"}
        status, answer = http("POST", f"{base}/api/games/select?slot={slot}")
        facts["select"] = {"status": status, "answer": answer.decode("utf-8", "replace")[:500]}
        if status != 200:
            return {**facts, "outcome": "refused"}
        time.sleep(wait)
        status, screenshot = http("GET", base + "/api/screenshot.bmp")
        facts["screenshot"] = {"status": status, "sha256": hashlib.sha256(screenshot).hexdigest(),
                               "drawn": status == 200 and drawn_something(screenshot)}
    except (urllib.error.URLError, OSError, ValueError) as error:
        return {**facts, "outcome": "failed", "error": str(error)[:300]}
    return {**facts, "outcome": "launched" if facts["screenshot"]["drawn"] else "failed"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    record = commands.add_parser("record", help="hashes and header facts only")
    device = commands.add_parser("device", help="upload, start and screenshot on a PRG32 console or PRG32-QT")
    device.add_argument("--url", required=True, help="the device, e.g. http://192.168.4.1 or http://127.0.0.1:8080")
    device.add_argument("--slot", required=True, choices=SLOTS, help="the slot to use; what is in it is replaced")
    device.add_argument("--wait", type=float, default=3.0, help="seconds to let the game draw before the screenshot")
    for command in (record, device):
        command.add_argument("cartridges", nargs="+", type=Path)
        command.add_argument("--target", default="", help="what was used: 'PRG32 console', 'PRG32-QT 1.x on macOS', ...")
        command.add_argument("--notes", default="", help="what you saw")
        command.add_argument("--out", type=Path, help="write the record here (JSON) instead of printing it")
    args = parser.parse_args(argv)
    if args.command == "device" and urlsplit(args.url).scheme not in ("http", "https"):
        parser.error("--url must start with http:// or https://")
    prg32_source = Path(os.environ.get("PRG32_SOURCE") or ROOT.parent / "PRG32")
    results = ([cartridge_facts(path) for path in args.cartridges] if args.command == "record" else
               [check_on_device(args.url, args.slot, path, args.wait) for path in args.cartridges])
    document = {"tool": "tools/delivery_check.py", "command": args.command,
                "date": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
                "target": args.target, "url": getattr(args, "url", ""), "slot": getattr(args, "slot", ""),
                "kit_commit": git_commit(ROOT), "prg32_sdk_commit": git_commit(prg32_source),
                "notes": args.notes, "cartridges": results}
    text = json.dumps(document, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    else:
        sys.stdout.write(text)
    return 0 if all(item.get("outcome", "launched") == "launched" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
