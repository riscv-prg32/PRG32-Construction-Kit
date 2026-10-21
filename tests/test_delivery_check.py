"""tools/delivery_check.py against an in-process stand-in for a PRG32 console / PRG32-QT web API.

The real devices are not available here (docs/delivery.md); this proves the tool sends
only to the given address, uses only the given slot, and records honest outcomes.
"""

from __future__ import annotations

import hashlib
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


def runtime_cart(cartridge: bytes) -> dict:
    """What PRG32-QT and the console report about the running cartridge."""
    if not cartridge:
        return {"loaded": False, "name": "", "code_size": 0}
    facts = delivery_check.cartridge_facts_from_bytes(cartridge)
    return {"loaded": True, "name": facts["name"], "code_size": facts["code_size"]}


class FakeDevice(BaseHTTPRequestHandler):
    slots: dict[str, bytes] = {}
    selected = ""
    requests: list[str] = []
    refuse = False
    host = "fake"
    running = b""          # the cartridge the device reports as running
    lag = 0                # runtime answers that still show the previous cartridge after a select
    stale = False          # never reports the newly selected cartridge
    swap_after_shot = b""  # another cartridge starts right after the screenshot
    frame_count = 0
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
        device = type(self)
        if self.path == "/api/runtime":
            device.frame_count += 10
            if device.lag:
                device.lag -= 1
                shown = device.previous
            else:
                shown = device.previous if device.stale else device.running
            return self.answer(200, {"abi": "1.6", "host": device.host, "diag": {"frame_count": device.frame_count},
                                     "cart": runtime_cart(shown)})
        if self.path == "/api/screenshot.bmp":
            if device.swap_after_shot:
                device.running = device.swap_after_shot
            return self.answer(200, device.screen, "image/bmp")
        self.answer(404, {"ok": False})

    def do_POST(self):
        type(self).requests.append("POST " + self.path)
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        slot = self.path.split("slot=", 1)[-1]
        if self.path.startswith("/api/games/select"):
            type(self).selected = slot
            type(self).previous, type(self).running = type(self).running, type(self).slots.get(slot, b"")
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
    FakeDevice.refuse, FakeDevice.screen, FakeDevice.host = False, bmp(b"\x10\x80\xff"), "fake"
    FakeDevice.running = FakeDevice.previous = FakeDevice.swap_after_shot = b""
    FakeDevice.lag, FakeDevice.stale, FakeDevice.frame_count = 0, False, 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeDevice)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def run(*args, out):
    if args and args[0] == "device":
        args = (*args, "--settle", "3")
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


def test_prg32_qt_slots_are_checked_before_anything_is_uploaded(tmp_path, device):
    """PRG32-QT keeps 4 slots (cart0..cart3): a higher slot is refused by the tool, nothing is sent."""
    FakeDevice.host = "qt"
    code, record = run("device", "--url", device, "--slot", "cart7", "--wait", "0", str(CARTRIDGES[0]),
                       out=tmp_path / "qt7.json")
    assert code == 1 and record["cartridges"][0]["outcome"] == "refused"
    assert "cart0..cart3" in record["cartridges"][0]["error"]
    assert not any(request.startswith("POST") for request in FakeDevice.requests)
    code, record = run("device", "--url", device, "--slot", "cart3", "--wait", "0", str(CARTRIDGES[0]),
                       "--screenshots", str(tmp_path / "shots"), out=tmp_path / "qt3.json")
    assert code == 0 and set(FakeDevice.slots) == {"cart3"}
    assert (tmp_path / "shots" / "pong.bmp").read_bytes() == FakeDevice.screen


def test_the_recorded_prg32_qt_delivery_matches_the_reproduced_builds():
    """docs/evidence: the cartridges delivered to PRG32-QT are byte for byte the ones the kit's Docker
    image builds (another host), and every one was stored, started and drew its own screen."""
    delivery = json.loads((ROOT / "docs/evidence/delivery/2026-10-21-prg32qt/delivery.json").read_text())
    built = json.loads((ROOT / "docs/evidence/toolchain/2026-10-21/check_build.json").read_text())
    container = {item["sha256"] for item in built["modes"]}
    delivered = {item["file"]: item for item in delivery["cartridges"]}
    assert all(item["outcome"] == "launched" for item in delivered.values())
    four = [item for name, item in delivered.items() if not name.startswith("audio_check")]
    assert len(four) == 4 and {item["sha256"] for item in four} <= container
    assert delivery["cartridges"][0]["runtime"]["host"] == "qt"
    shots = {item["file"]: item["screenshot"]["sha256"] for item in delivery["cartridges"]}
    # The same Blocks game as C and as generated assembly draws the same screen; the others differ.
    assert shots["blocks-generated-C-esp32c6.prg32"] == shots["blocks-generated-assembly-esp32c6.prg32"]
    assert len(set(shots.values())) == 4


def test_the_checked_prg32_qt_delivery_shows_each_cartridge_running_itself():
    """docs/evidence/delivery/2026-10-21-prg32qt-checked: the same five cartridges, delivered again
    with the integrity checks. For each, PRG32-QT reported that cartridge (name and code size)
    running before and after its screenshot, with frames advancing - unlike the first record,
    where the handwritten assembly was screenshotted while the console check was reported."""
    folder = ROOT / "docs/evidence/delivery/2026-10-21-prg32qt-checked"
    delivery = json.loads((folder / "delivery.json").read_text())
    first = {item["file"]: item for item in json.loads(
        (ROOT / "docs/evidence/delivery/2026-10-21-prg32qt/delivery.json").read_text())["cartridges"]}
    assert len(delivery["cartridges"]) == 5
    for item in delivery["cartridges"]:
        assert item["outcome"] == "launched" and item["sha256"] == first[item["file"]]["sha256"]
        for key in ("runtime_selected", "runtime_after_screenshot"):
            cart = item[key]["cart"]
            assert cart["loaded"] and cart["name"] == item["name"] and cart["code_size"] == item["code_size"], key
        assert item["runtime_after_screenshot"]["diag"]["frame_count"] >= 30
        shot = (folder / "screenshots" / item["file"].replace(".prg32", ".bmp")).read_bytes()
        assert hashlib.sha256(shot).hexdigest() == item["screenshot"]["sha256"]
    names = [item["name"] for item in delivery["cartridges"]]
    assert names[-1] == "audio-check" and len(set(names[2:])) == 3
    assert first["handwritten-assembly-esp32c6.prg32"]["runtime"]["cart"]["name"] == "audio-check"   # the stale record


def test_a_device_that_reports_the_new_cartridge_late_is_waited_for(tmp_path, device):
    FakeDevice.lag = 3
    code, record = run("device", "--url", device, "--slot", "cart1", "--wait", "0", str(CARTRIDGES[0]),
                       out=tmp_path / "late.json")
    item = record["cartridges"][0]
    assert code == 0 and item["outcome"] == "launched"
    assert item["runtime_selected"]["cart"]["name"] == item["name"]
    assert item["runtime_after_screenshot"]["cart"]["name"] == item["name"]


def test_stale_runtime_state_is_never_evidence(tmp_path, device):
    """A device still reporting the previous cartridge: no screenshot is taken as this one's."""
    run("device", "--url", device, "--slot", "cart1", "--wait", "0", str(CARTRIDGES[0]), out=tmp_path / "first.json")
    FakeDevice.stale = True
    code, record = run("device", "--url", device, "--slot", "cart1", "--wait", "0", str(CARTRIDGES[1]),
                       out=tmp_path / "stale.json")
    item = record["cartridges"][0]
    assert code == 1 and item["outcome"] == "failed" and "never reported" in item["error"]
    assert "screenshot" not in item


def test_a_cartridge_change_during_the_screenshot_is_caught(tmp_path, device):
    FakeDevice.swap_after_shot = CARTRIDGES[2].read_bytes()
    code, record = run("device", "--url", device, "--slot", "cart1", "--wait", "0", str(CARTRIDGES[0]),
                       out=tmp_path / "swap.json")
    item = record["cartridges"][0]
    assert code == 1 and item["outcome"] == "failed" and "another cartridge" in item["error"]
