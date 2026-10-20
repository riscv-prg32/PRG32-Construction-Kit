"""tools/delivery_check.py against an in-process stand-in for a PRG32 console / PRG32-QT web API.

The real devices are not available here (docs/delivery.md); this proves the tool sends
only to the given address, uses only the given slot, and records honest outcomes.
"""

from __future__ import annotations

import json
import struct
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import delivery_check  # noqa: E402

CARTRIDGES = [ROOT / "tests" / "fixtures" / "debug" / name for name in ("pong.prg32", "locals.prg32", "compressed.prg32")]


def bmp(pixel: bytes) -> bytes:
    """A 1x1 24-bit BMP."""
    row = pixel + b"\x00"
    return b"BM" + struct.pack("<IHHI", 54 + len(row), 0, 0, 54) + struct.pack("<IiiHHIIiiII", 40, 1, 1, 1, 24, 0,
                                                                              len(row), 0, 0, 0, 0) + row


class FakeDevice(BaseHTTPRequestHandler):
    slots: dict[str, bytes] = {}
    selected = ""
    requests: list[str] = []
    refuse = False
    screen = bmp(b"\x10\x80\xff")

    def log_message(self, *_args):
        pass

    def answer(self, status, body, kind="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        type(self).requests.append("GET " + self.path)
        if self.path == "/api/runtime":
            return self.answer(200, {"abi": "1.6", "host": "fake"})
        if self.path == "/api/screenshot.bmp":
            return self.answer(200, type(self).screen, "image/bmp")
        self.answer(404, {"ok": False})

    def do_POST(self):
        type(self).requests.append("POST " + self.path)
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        slot = self.path.split("slot=", 1)[-1]
        if self.path.startswith("/api/games/select"):
            type(self).selected = slot
            return self.answer(200, {"ok": True, "slot": slot})
        if self.path.startswith("/api/games"):
            if type(self).refuse or body[:4] != b"PRG2":
                return self.answer(400, {"ok": False, "error": "cartridge rejected"})
            type(self).slots[slot] = body
            return self.answer(200, {"ok": True, "slot": slot, "stored": True})
        self.answer(404, {"ok": False})


@pytest.fixture()
def device():
    FakeDevice.slots, FakeDevice.selected, FakeDevice.requests = {}, "", []
    FakeDevice.refuse, FakeDevice.screen = False, bmp(b"\x10\x80\xff")
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeDevice)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def run(*args, out):
    code = delivery_check.main([*args, "--out", str(out)])
    return code, json.loads(out.read_text())


def test_record_hashes_every_cartridge(tmp_path):
    code, record = run("record", *map(str, CARTRIDGES), "--target", "none", out=tmp_path / "r.json")
    assert code == 0 and [item["file"] for item in record["cartridges"]] == ["pong.prg32", "locals.prg32", "compressed.prg32"]
    assert all(len(item["sha256"]) == 64 and item["bytes"] > 0 for item in record["cartridges"])
    assert record["kit_commit"]


def test_a_file_that_is_not_a_cartridge_is_refused_before_anything_is_sent(tmp_path, device):
    bad = tmp_path / "bad.prg32"
    bad.write_bytes(b"hello")
    with pytest.raises(SystemExit):
        delivery_check.main(["device", "--url", device, "--slot", "cart7", str(bad)])
    assert FakeDevice.requests == []


def test_device_check_uses_only_the_given_slot_and_records_outcomes(tmp_path, device):
    code, record = run("device", "--url", device, "--slot", "cart7", "--wait", "0", *map(str, CARTRIDGES),
                       out=tmp_path / "d.json")
    assert code == 0
    assert set(FakeDevice.slots) == {"cart7"} and FakeDevice.selected == "cart7"
    assert all(item["outcome"] == "launched" and item["screenshot"]["drawn"] for item in record["cartridges"])
    assert record["slot"] == "cart7" and record["url"] == device


def test_a_black_screen_or_a_refusal_is_not_called_launched(tmp_path, device):
    FakeDevice.screen = bmp(b"\x00\x00\x00")
    code, record = run("device", "--url", device, "--slot", "cart6", "--wait", "0", str(CARTRIDGES[0]),
                       out=tmp_path / "black.json")
    assert code == 1 and record["cartridges"][0]["outcome"] == "failed"
    FakeDevice.refuse = True
    code, record = run("device", "--url", device, "--slot", "cart6", "--wait", "0", str(CARTRIDGES[0]),
                       out=tmp_path / "refused.json")
    assert code == 1 and record["cartridges"][0]["outcome"] == "refused"


def test_an_unreachable_device_is_a_failure_not_a_crash(tmp_path):
    code, record = run("device", "--url", "http://127.0.0.1:9", "--slot", "cart7", "--wait", "0", str(CARTRIDGES[0]),
                       out=tmp_path / "down.json")
    assert code == 1 and record["cartridges"][0]["outcome"] == "failed"


def test_the_slot_must_be_chosen(device):
    with pytest.raises(SystemExit):
        delivery_check.main(["device", "--url", device, str(CARTRIDGES[0])])
    with pytest.raises(SystemExit):
        delivery_check.main(["device", "--url", device, "--slot", "factory", str(CARTRIDGES[0])])
