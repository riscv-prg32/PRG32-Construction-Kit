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
# PRG32-QT keeps 4 cartridge slots (cart0..cart3); the console has 8.
SLOTS_BY_HOST = {"qt": SLOTS[:4]}
TIMEOUT = 30
MIN_FRAMES = 30          # frames of the selected cartridge before its screenshot counts


def git_commit(path: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=10, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def cartridge_facts(path: Path) -> dict:
    return {"file": path.name, **cartridge_facts_from_bytes(path.read_bytes(), str(path))}


def cartridge_facts_from_bytes(data: bytes, where: str = "cartridge") -> dict:
    facts = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    if data[:4] != b"PRG2" or len(data) < 20:
        raise SystemExit(f"{where} is not a PRG32 cartridge (no PRG2 header)")
    facts["header_size"], facts["code_size"] = struct.unpack_from("<I", data, 8)[0], struct.unpack_from("<I", data, 16)[0]
    name_at = struct.calcsize("<4sHHHHIIIIIII")          # the PRG2 header's 32-byte name (build_check)
    facts["name"] = data[name_at:name_at + 32].split(b"\0", 1)[0].decode("ascii", "replace")
    return facts


def runtime_shows(runtime: dict, facts: dict) -> bool:
    """Does the device's /api/runtime say that this cartridge is the one loaded now?"""
    cart = runtime.get("cart") or {}
    return bool(cart.get("loaded")) and cart.get("name") == facts["name"] and cart.get("code_size") == facts["code_size"]


def frames(runtime: dict) -> int | None:
    count = (runtime.get("diag") or {}).get("frame_count")
    return count if isinstance(count, int) else None


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


def check_on_device(url: str, slot: str, cartridge: Path, wait: float, keep: Path | None = None,
                    settle: float = 20.0) -> dict:
    facts = cartridge_facts(cartridge)
    base = url.rstrip("/")
    try:
        status, runtime = http("GET", base + "/api/runtime")
        facts["runtime"] = json.loads(runtime or b"{}") if status == 200 else {"status": status}
        allowed = SLOTS_BY_HOST.get(facts["runtime"].get("host"), SLOTS)
        if slot not in allowed:          # nothing is sent: say which slots this host has
            return {**facts, "outcome": "refused",
                    "error": f"{facts['runtime'].get('host')} has slots {allowed[0]}..{allowed[-1]}, not {slot}"}
        status, answer = http("POST", f"{base}/api/games?slot={slot}", cartridge.read_bytes())
        facts["upload"] = {"status": status, "answer": answer.decode("utf-8", "replace")[:500]}
        if status != 200:
            return {**facts, "outcome": "refused"}
        status, answer = http("POST", f"{base}/api/games/select?slot={slot}")
        facts["select"] = {"status": status, "answer": answer.decode("utf-8", "replace")[:500]}
        if status != 200:
            return {**facts, "outcome": "refused"}
        # Evidence integrity: wait until the device reports this cartridge (name, code size,
        # loaded) and has run frames of it, so the screenshot cannot be the previous game's.
        deadline = time.monotonic() + settle
        selected, first_frames = None, None
        while time.monotonic() < deadline:
            status, runtime = http("GET", base + "/api/runtime")
            now = json.loads(runtime or b"{}") if status == 200 else {}
            if runtime_shows(now, facts):
                selected = selected or now
                first_frames = first_frames if first_frames is not None else frames(now)
                current = frames(now)
                if current is None or first_frames is None or current - first_frames >= MIN_FRAMES:
                    break
            time.sleep(0.2)
        else:
            facts["runtime_selected"] = selected
            return {**facts, "outcome": "failed", "error": "the device never reported this cartridge as running"}
        facts["runtime_selected"] = now
        time.sleep(wait)
        status, screenshot = http("GET", base + "/api/screenshot.bmp")
        if keep and status == 200:
            keep.mkdir(parents=True, exist_ok=True)
            (keep / f"{cartridge.stem}.bmp").write_bytes(screenshot)
        facts["screenshot"] = {"status": status, "sha256": hashlib.sha256(screenshot).hexdigest(),
                               "drawn": status == 200 and drawn_something(screenshot)}
        status, runtime = http("GET", base + "/api/runtime")
        facts["runtime_after_screenshot"] = json.loads(runtime or b"{}") if status == 200 else {"status": status}
        if not runtime_shows(facts["runtime_after_screenshot"], facts):
            return {**facts, "outcome": "failed", "error": "another cartridge was running when the screenshot was taken"}
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
    device.add_argument("--screenshots", type=Path, help="keep each screenshot here as <cartridge>.bmp")
    device.add_argument("--settle", type=float, default=20.0,
                        help="seconds to wait for the device to report the selected cartridge running")
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
               [check_on_device(args.url, args.slot, path, args.wait, args.screenshots, args.settle)
                for path in args.cartridges])
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
