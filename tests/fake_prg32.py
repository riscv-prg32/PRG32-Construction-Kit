"""A stand-in for the PRG32 web API (console firmware and PRG32-QT) for the Deploy tests.

It answers like components/prg32/prg32_http_games.c: /api/runtime, /api/games (GET and POST
?slot=), /api/games/select?slot= and /api/screenshot.bmp, keeps the cartridges in memory and
counts frames while one runs. ``fail`` makes it misbehave the way real devices do:

- ``"drop_upload"``: closes the connection during the next N uploads (N = ``drops``);
- ``"full"``: refuses every upload as too big;
- ``"never_runs"``: accepts select but never reports the cartridge running;
- ``"select_refused"``: select answers 400;
- ``"gone_after_upload"``: stops answering after the cartridge is stored.

Like the firmware's performance broker, /api/performance.json gives the last finished suite:
each select starts a run, which "finishes" after ``suite_seconds``. Its numbers are made
from the run number, so tests know them; runs listed in ``silent_runs`` never finish.
"""

from __future__ import annotations

import json
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ABI_HASH = 0x260F6136


class FakePrg32:
    def __init__(self, slots: int = 8, host: str | None = None, abi_hash: int = ABI_HASH, abi_major: int = 1,
                 features: int = 0xFFFF, cart_max_size: int = 64 * 1024, cart_ram_size: int = 64 * 1024,
                 firmware_version: str = "679dfb5"):
        self.slots = {f"cart{index}": None for index in range(slots)}
        self.host, self.abi_hash, self.abi_major, self.features = host, abi_hash, abi_major, features
        self.cart_max_size, self.cart_ram_size, self.firmware_version = cart_max_size, cart_ram_size, firmware_version
        self.loaded: str | None = None
        self.started = 0.0
        self.fail: str | None = None
        self.drops = 0
        self.uploads: list[tuple[str, int]] = []
        self.gone = False
        self.suite_seconds = 0.2
        self.runs = 0                      # selects so far: each starts one run of the suite
        self.silent_runs: set[int] = set()
        self.finished_run = 0              # the last run whose result /api/performance.json gives
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def _send(self, status: int, body: bytes, kind: str = "application/json"):
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if fake.gone:
                    self.connection.close()
                    return
                path = urlsplit(self.path).path
                if path == "/api/runtime":
                    self._send(200, json.dumps(fake.runtime()).encode())
                elif path == "/api/games":
                    self._send(200, json.dumps([fake.slot_info(name) for name in fake.slots]).encode())
                elif path == "/api/screenshot.bmp":
                    self._send(200, fake.bmp(), "image/bmp")
                elif path == "/api/performance.json":
                    self._send(200, json.dumps(fake.performance()).encode())
                else:
                    self._send(404, b"not found")

            def do_POST(self):
                if fake.gone:
                    self.connection.close()
                    return
                parts = urlsplit(self.path)
                slot = (parse_qs(parts.query).get("slot") or ["cart0"])[0]
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                if slot not in fake.slots:
                    self._send(400, b"invalid cartridge slot")
                    return
                if parts.path == "/api/games":
                    if fake.fail == "drop_upload" and fake.drops > 0:
                        fake.drops -= 1
                        self.connection.close()
                        return
                    if fake.fail == "full" or len(body) > fake.cart_max_size:
                        self._send(400, f"invalid cartridge size {len(body)} (max {fake.cart_max_size})".encode())
                        return
                    fake.slots[slot] = body
                    fake.uploads.append((slot, len(body)))
                    self._send(200, json.dumps({"ok": True, **fake.slot_info(slot)}).encode())
                    if fake.fail == "gone_after_upload":
                        fake.gone = True
                elif parts.path == "/api/games/select":
                    if fake.fail == "select_refused" or fake.slots[slot] is None:
                        self._send(400, b"slot is empty" if fake.slots[slot] is None else b"cartridge rejected")
                        return
                    fake.loaded, fake.started = slot, time.monotonic()
                    fake.runs += 1
                    self._send(200, json.dumps({"ok": True, "slot": slot}).encode())
                else:
                    self._send(404, b"not found")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True          # a dropped connection must not keep pytest alive
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @staticmethod
    def name_of(data: bytes | None) -> str:
        return data[40:72].split(b"\0", 1)[0].decode() if data else ""

    def slot_info(self, slot: str) -> dict:
        data = self.slots[slot]
        return {"slot": slot, "name": self.name_of(data), "loaded": slot == self.loaded, "stored": data is not None,
                "code_size": struct.unpack_from("<I", data, 16)[0] if data else 0,
                "mem_size": struct.unpack_from("<I", data, 20)[0] if data else 0, "audio_size": 0, "audio": False,
                "generation": 1 if data else 0}

    def runtime(self) -> dict:
        running = self.loaded is not None and self.fail != "never_runs"
        cart = self.slot_info(self.loaded) if running else {"name": "", "loaded": False, "code_size": 0}
        answer = {"name": "PRG32", "firmware_version": self.firmware_version, "cart_magic": "PRG2",
                  "cart_abi_major": self.abi_major, "cart_abi_minor": 6, "cart_abi_hash": self.abi_hash,
                  "cart_abi_features": self.features, "cart_load_addr": 0x40800000,
                  "cart_max_size": self.cart_max_size, "cart_ram_size": self.cart_ram_size,
                  "cart_loaded": running, "qemu": False, "cart": cart,
                  "diag": {"frame_count": int((time.monotonic() - self.started) * 300) if running else 0,
                           "input_state": 0}}
        if self.host:
            answer["host"] = self.host
        return answer

    CASES = ("clear-fill", "text-overlay", "sprite-storm", "scrolling", "mixed-gameplay")

    @staticmethod
    def frame_us(run: int, case: int) -> int:
        """The mean frame time this fake reports for a run and case (microseconds)."""
        return 10000 + 1000 * case + 10 * run

    def performance(self) -> dict:
        if self.loaded is not None and self.runs not in self.silent_runs and time.monotonic() - self.started >= self.suite_seconds:
            self.finished_run = self.runs
        if not self.finished_run:
            return {"ok": False, "running": True} if self.loaded else {"ok": False, "error": "no performance test results"}
        run = self.finished_run
        cases = [{"screen_index": index, "screen_name": name, "color_mode": "rgb565", "frames": 60,
                  "fps_mean": round(1e6 / self.frame_us(run, index), 2), "frame_us_min": self.frame_us(run, index) - 500,
                  "frame_us_mean": self.frame_us(run, index), "frame_us_p50": self.frame_us(run, index),
                  "frame_us_p95": self.frame_us(run, index) + 800, "frame_us_p99": self.frame_us(run, index) + 900,
                  "frame_us_max": self.frame_us(run, index) + 1000, "missed_deadlines": 0, "update_us_mean": 20,
                  "draw_us_mean": 300 + index, "present_us_mean": self.frame_us(run, index) - 320 - index, "heap_min": 1000}
                 for index, name in enumerate(self.CASES)]
        return {"ok": True, "schema_version": 2, "run_id": f"perf-{run}", "target": "fake", "display_backend": "fake",
                "result_count": len(cases), "duration_us": 9_000_000, "screen_summaries": cases,
                "memory": {"baseline_free_bytes": 1}, "samples": []}

    def bmp(self) -> bytes:
        """A 4x2 24-bit BMP, yellow when a cartridge runs."""
        width, height = 4, 2
        pixel = b"\x00\xff\xff" if self.loaded else b"\x00\x00\x00"
        row = pixel * width
        image = row * height
        header = b"BM" + struct.pack("<IHHI", 54 + len(image), 0, 0, 54)
        info = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, len(image), 2835, 2835, 0, 0)
        return header + info + image

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def cartridge(name: str = "Deploy Me", code_size: int = 64, mem_size: int = 4096, abi_hash: int = ABI_HASH,
              abi_major: int = 1, features: int = 0, padding: int = 0) -> bytes:
    """A PRG2 v2 cartridge header (SDK CART_HEADER_V2) and some code bytes."""
    head = struct.Struct("<4sHHHHIIIIIII32sIIIIIII")
    fields = [b"PRG2", abi_major, 6, head.size, 0, 0, code_size, mem_size, 0, 0, 0, 0,
              name.encode()[:31], abi_hash, features, 0, 0, 0, 0, 1]
    return head.pack(*fields) + b"\x13" * (code_size + padding)
