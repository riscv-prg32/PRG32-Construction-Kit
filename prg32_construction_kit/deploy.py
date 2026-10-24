"""Deploy: put a compiled PRG32 cartridge on a PRG32 console, in PRG32-QT or in QEMU (ADR-0028).

Three kinds of target, one way of working (docs/deploy.md):

- ``prg32``    a PRG32 console, over the HTTP API its firmware offers on its Wi-Fi;
- ``prg32qt``  PRG32-QT on a computer, over the same API (port 8080);
- ``qemu``     Espressif's QEMU on this server, booting a PRG32 firmware image the operator
               built with ``tools/build_qemu_firmware.py`` (its folder is PRG32_QEMU_FIRMWARE).

An administrator registers the console and PRG32-QT targets (name and address): the server
only ever talks to addresses an administrator chose, never to one a student typed. QEMU is
there when the operator configured it.

Every deployment goes the same way and stops at the first step that fails, with a code the
student and the tests can rely on:

1. the cartridge: a PRG32 cartridge this kit built (``not_built_here``), its file still has the
   SHA-256 recorded at build time (``hash_mismatch``), it was built from the project as it is
   saved now (``stale_build``), for an architecture this target runs (``wrong_architecture``);
2. the target, asked again right before sending: the same one the student looked at
   (``target_changed``), reachable (``disconnected``), with this ABI (``unsupported_abi``),
   enough room (``target_full``);
3. the slot: named by the student (``slot_unknown``) and holding exactly what they saw
   (``slot_changed``), so nothing is overwritten that nobody looked at;
4. upload (a broken connection is retried twice, sending the whole cartridge each time);
5. launch (select the slot, or boot QEMU) and verify that the target reports this cartridge
   running (``launch_failed``); then a screenshot.

``Cancel`` stops before the next step. Every answer says what kind of evidence it is: only a
``prg32`` target is a physical device; a PRG32-QT or QEMU run is an emulator run, never
physical-device evidence. Each failure also says what state the target is left in.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import threading
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, request, send_file
from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column

from .auth import admin_required
from .db import db, get_resource, new_id, utcnow
from .messages import Message, body as message_body, fields as message_fields, text as say
from .project_format import SDK_ABI, SDK_COMPATIBLE_ABI_HASHES

bp = Blueprint("deploy", __name__)

KINDS = ("prg32", "prg32qt", "qemu")
# What a run on each kind proves. Only a console is a physical device.
EVIDENCE = {"prg32": "physical device", "prg32qt": "emulator (PRG32-QT)", "qemu": "emulator (QEMU)"}
# Which kit cartridge each kind runs (packager.SUPPORTED_ARCHITECTURES).
ARCHITECTURES = {"prg32": ("esp32c6",), "prg32qt": ("qemu", "esp32c6"), "qemu": ("qemu",)}
SLOT_NAME = re.compile(r"^cart[0-9]{1,2}$")
RUNNING = ("queued", "checking", "uploading", "starting", "verifying")
FINAL = ("launched", "refused", "failed", "cancelled")
RETRIES = 2                 # extra tries after a broken connection
HTTP_TIMEOUT = 20           # seconds for one request
SETTLE_SECONDS = 20         # for the target to report the cartridge running
MIN_FRAMES = 30             # frames of the new cartridge before its screenshot counts
JOB_LIMIT_SECONDS = 300     # a deployment still "running" after this was interrupted
MAX_JSON_BYTES = 64 * 1024
MAX_SCREENSHOT_BYTES = 512 * 1024

# The PRG2 header (PRG32 SDK prg32/utilities/env_variables.py: CART_HEADER, CART_HEADER_V2).
HEADER_V1 = struct.Struct("<4sHHHHIIIIIII32s")
HEADER_V2 = struct.Struct("<4sHHHHIIIIIII32sIIIIIII")
IMPORT_MODEL_ABI_TABLE = 1


# --- the records ------------------------------------------------------------------

class DeployTarget(db.Model):
    """A console or PRG32-QT an administrator registered (QEMU needs no row)."""
    __tablename__ = "deploy_targets"
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(db.Text, nullable=False)
    kind: Mapped[str] = mapped_column(db.Text, nullable=False)
    url: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    notes: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    created_by: Mapped[int | None] = mapped_column(db.Integer)
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)


class Deployment(db.Model):
    """One deployment: what went where, each step, and what it proves."""
    __tablename__ = "deployments"
    id: Mapped[str] = mapped_column(db.Text, primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(db.Integer, index=True)
    project_id: Mapped[str | None] = mapped_column(db.Text, index=True)
    artifact_id: Mapped[str] = mapped_column(db.Text, nullable=False)
    target: Mapped[str] = mapped_column(db.Text, nullable=False)        # "qemu" or a target row id
    target_kind: Mapped[str] = mapped_column(db.Text, nullable=False)
    target_name: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    slot: Mapped[str] = mapped_column(db.Text, nullable=False)
    status: Mapped[str] = mapped_column(db.Text, nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    cancel_requested: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)
    log: Mapped[str] = mapped_column(db.Text, nullable=False, default="[]")
    result: Mapped[str] = mapped_column(db.Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)
    updated_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)


class DeployProblem(Exception):
    """A step that cannot go on: ``code`` for programs, the Message for people, and the target's state."""

    def __init__(self, code: str, message: Message, *, final: str = "refused", left: Message | None = None):
        super().__init__(message)
        self.code, self.final = code, final
        self.left = left or say("deploy", "Nothing was sent: the target is as it was.")


class Cancelled(Exception):
    pass


# --- the cartridge ----------------------------------------------------------------

def cartridge_header(data: bytes) -> dict[str, Any]:
    """The fields of a PRG2 header the target checks (SDK runtime_handler.cartridge_contract)."""
    if len(data) < HEADER_V1.size or data[:4] != b"PRG2":
        raise DeployProblem("not_a_cartridge", say("deploy", "This file is not a PRG32 cartridge."))
    fields = HEADER_V1.unpack_from(data, 0)
    header = {"abi_major": fields[1], "abi_minor": fields[2], "header_size": fields[3], "code_size": fields[6],
              "mem_size": fields[7], "name": fields[12].split(b"\0", 1)[0].decode("ascii", "replace"),
              "abi_hash": None, "required_features": 0, "import_model": 0, "bytes": len(data),
              "sha256": hashlib.sha256(data).hexdigest()}
    if header["header_size"] >= HEADER_V2.size and len(data) >= HEADER_V2.size:
        v2 = HEADER_V2.unpack_from(data, 0)
        header.update({"abi_hash": v2[13], "required_features": v2[14], "import_model": v2[19]})
    return header


def abi_problems(header: dict[str, Any], probe: dict[str, Any]) -> list[Message]:
    """Why this target cannot run this cartridge (the same rules as the SDK's upload check)."""
    abi = probe["abi"]
    problems = []
    if header["abi_major"] != abi["major"]:
        problems.append(say("deploy", "The cartridge needs ABI {need}, the target has ABI {have}.",
                            need=header["abi_major"], have=abi["major"]))
    elif header["import_model"] == IMPORT_MODEL_ABI_TABLE:
        compatible = {abi["hash"]}
        if abi["hash"] == int(SDK_ABI["hash"], 16):        # as the SDK's own upload check does
            compatible |= set(SDK_COMPATIBLE_ABI_HASHES)
        if header["abi_hash"] not in compatible:
            problems.append(say("deploy", "The cartridge was built for ABI {need}, the target has ABI {have}: "
                                "the target's firmware is from another PRG32 version.",
                                need=f"0x{int(header['abi_hash'] or 0):08x}", have=f"0x{abi['hash']:08x}"))
        missing = int(header["required_features"]) & ~int(abi.get("features", 0))
        if missing:
            problems.append(say("deploy", "The cartridge needs features the target does not have ({bits}).",
                                bits=f"0x{missing:08x}"))
    return problems


def room_problems(header: dict[str, Any], probe: dict[str, Any], slot: dict[str, Any]) -> list[Message]:
    limits = probe["limits"]
    problems = []
    largest = min(value for value in (limits.get("cart_max_size"), slot.get("size")) if value) \
        if limits.get("cart_max_size") or slot.get("size") else None
    if largest and header["bytes"] > largest:
        problems.append(say("deploy", "The cartridge is {size} bytes; {slot} takes at most {limit}.",
                            size=header["bytes"], slot=slot["slot"], limit=largest))
    if limits.get("cart_ram_size") and header["mem_size"] > limits["cart_ram_size"]:
        problems.append(say("deploy", "The cartridge needs {need} bytes of RAM; the target has {have}.",
                            need=header["mem_size"], have=limits["cart_ram_size"]))
    return problems


def fingerprint(probe: dict[str, Any]) -> str:
    """Which target this is: changes when its firmware, ABI or limits change."""
    seen = {key: probe[key] for key in ("address", "identity", "abi", "limits")}
    return hashlib.sha256(json.dumps(seen, sort_keys=True).encode()).hexdigest()[:16]


def slot_content(slot: dict[str, Any]) -> dict[str, Any]:
    """What a slot holds, as the student saw it (compared again before anything is replaced)."""
    return {key: slot.get(key) for key in ("slot", "stored", "name", "code_size", "mem_size")}


# --- targets that speak the PRG32 web API (console firmware and PRG32-QT) -----------

class HttpTarget:
    """``GET /api/runtime`` and ``/api/games``, ``POST /api/games?slot=`` and ``/api/games/select?slot=``,
    ``GET /api/screenshot.bmp``: the API of the console's firmware (components/prg32/prg32_http_games.c)
    and of PRG32-QT (src/qt/WebApiServer.cpp)."""

    def __init__(self, kind: str, url: str):
        self.kind, self.base = kind, url.rstrip("/")

    def _call(self, method: str, path: str, body: bytes | None = None, limit: int = MAX_JSON_BYTES) -> tuple[int, bytes]:
        headers = {"Content-Type": "application/octet-stream"} if body is not None else {}
        call = urllib.request.Request(self.base + path, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(call, timeout=HTTP_TIMEOUT) as answer:
                return answer.status, answer.read(limit + 1)[:limit + 1]
        except urllib.error.HTTPError as error:
            return error.code, error.read(2000)
        except (urllib.error.URLError, OSError) as error:
            raise ConnectionError(str(error)[:200]) from error

    def _json(self, path: str) -> Any:
        status, data = self._call("GET", path)
        if status != 200 or len(data) > MAX_JSON_BYTES:
            raise ConnectionError(f"{path} answered {status}")
        return json.loads(data or b"null")

    def probe(self) -> dict[str, Any]:
        runtime, games = self._json("/api/runtime"), self._json("/api/games")
        if not isinstance(runtime, dict) or runtime.get("cart_magic") not in (None, "PRG2") or not isinstance(games, list):
            raise ConnectionError("not a PRG32 web API")
        slots = [{"slot": str(item.get("slot")), "stored": bool(item.get("stored")), "name": str(item.get("name") or ""),
                  "code_size": int(item.get("code_size") or 0), "mem_size": int(item.get("mem_size") or 0),
                  "loaded": bool(item.get("loaded"))}
                 for item in games if isinstance(item, dict) and SLOT_NAME.match(str(item.get("slot")))]
        return {"address": self.base,
                "identity": {"name": str(runtime.get("name") or ""), "firmware_version": str(runtime.get("firmware_version") or ""),
                             "host": str(runtime.get("host") or "console"), "qemu": bool(runtime.get("qemu"))},
                "abi": {"major": int(runtime.get("cart_abi_major", 0)), "minor": int(runtime.get("cart_abi_minor", 0)),
                        "hash": int(runtime.get("cart_abi_hash", 0)), "features": int(runtime.get("cart_abi_features", 0))},
                "limits": {"cart_max_size": int(runtime.get("cart_max_size") or 0),
                           "cart_ram_size": int(runtime.get("cart_ram_size") or 0)},
                "slots": slots}

    def upload(self, slot: str, data: bytes) -> dict[str, Any]:
        status, answer = self._call("POST", f"/api/games?slot={slot}", data)
        text = answer.decode("utf-8", "replace")[:300]
        if status != 200:
            raise DeployProblem("target_full" if "size" in text or "space" in text else "upload_refused",
                                say("deploy", "The target refused the cartridge: {answer}", answer=text),
                                left=say("deploy", "{slot} may no longer hold its old game: deploy again, or choose another slot.",
                                         slot=slot))
        return {"status": status, "answer": text}

    def launch(self, slot: str) -> dict[str, Any]:
        status, answer = self._call("POST", f"/api/games/select?slot={slot}")
        text = answer.decode("utf-8", "replace")[:300]
        if status != 200:
            raise DeployProblem("launch_failed", say("deploy", "The target did not start the cartridge: {answer}", answer=text),
                                final="failed", left=stored_but_not_started(slot))
        return {"status": status, "answer": text}

    def verify(self, header: dict[str, Any], slot: str, wait: Callable[[float], None]) -> dict[str, Any]:
        """Until the target reports this cartridge loaded and MIN_FRAMES frames of it drawn."""
        deadline, first = time.monotonic() + SETTLE_SECONDS, None
        while time.monotonic() < deadline:
            runtime = self._json("/api/runtime")
            cart = runtime.get("cart") or {}
            if cart.get("loaded") and cart.get("name") == header["name"] and cart.get("code_size") == header["code_size"]:
                frames = (runtime.get("diag") or {}).get("frame_count")
                first = frames if first is None else first
                if not isinstance(frames, int) or frames - first >= MIN_FRAMES:
                    return {"running": True, "frames": frames}
            wait(0.25)
        raise DeployProblem("launch_failed", say("deploy", "The target never reported this cartridge running."),
                            final="failed", left=stored_but_not_started(slot))

    def screenshot(self) -> bytes | None:
        status, data = self._call("GET", "/api/screenshot.bmp", limit=MAX_SCREENSHOT_BYTES)
        return bmp_to_png(data) if status == 200 and data[:2] == b"BM" else None

    def close(self) -> None:
        pass


def stored_but_not_started(slot: str) -> Message:
    return say("deploy", "{slot} holds this cartridge, but it did not start. Deploy again, or start it from the menu.",
               slot=slot)


# --- QEMU on this server --------------------------------------------------------------

QEMU_STARTED = (b"loaded cartridge", b"prg32_init => cart_is_loaded()")
QEMU_MENU = b"setup_menu => prg32_input_read_menu()"
QEMU_CRASHED = (b"Guru Meditation", b"abort() was called", b"cartridge rejected")
_qemu_lock = threading.Lock()   # one QEMU at a time per server process


def qemu_settings() -> dict[str, Any] | None:
    """PRG32_QEMU (the binary) and PRG32_QEMU_FIRMWARE (a folder from tools/build_qemu_firmware.py)."""
    firmware = current_app.config.get("QEMU_FIRMWARE")
    if not firmware:
        return None
    folder = Path(firmware)
    binary = current_app.config.get("QEMU_BINARY") or next(
        iter(sorted(Path.home().glob(".espressif/tools/qemu-riscv32/*/qemu/bin/qemu-system-riscv32"))), None)
    if not (folder / "prg32-firmware.json").is_file() or not binary:
        return None
    return {"firmware": folder, "binary": str(binary), "gdb": current_app.config.get("QEMU_GDB") or
            shutil.which("riscv32-esp-elf-gdb-no-python") or shutil.which("riscv32-esp-elf-gdb")}


class QemuTarget:
    """Espressif's QEMU (ESP32-C3 machine) booting the PRG32 firmware with the cartridge in its flash.

    Each deployment starts from a fresh copy of the operator's flash image, in the deployment's own
    folder, so nothing another deployment did is overwritten. The firmware boots ``cart0`` (no
    default slot is stored in a fresh image), so that is the one slot. It has no network: it is
    seen running from its serial console, and the screen is read from the framebuffer through
    QEMU's GDB stub (Espressif's QEMU has no screendump)."""

    kind = "qemu"

    def __init__(self, settings: dict[str, Any], work: Path):
        self.settings, self.work = settings, work
        self.manifest = json.loads((settings["firmware"] / "prg32-firmware.json").read_text())
        self.process: subprocess.Popen | None = None
        self.serial = bytearray()
        self.gdb_port = 0
        self._stop = threading.Event()

    def probe(self) -> dict[str, Any]:
        flash = self.settings["firmware"] / "qemu_flash.bin"
        if hashlib.sha256(flash.read_bytes()).hexdigest() != self.manifest["flash_sha256"]:
            raise ConnectionError("the QEMU flash image does not match its manifest")
        slot = next(item for item in self.manifest["slots"] if item["name"] == "cart0")
        abi = self.manifest["abi"]
        return {"address": "qemu",
                "identity": {"name": "PRG32", "firmware_version": self.manifest["firmware_version"], "host": "qemu",
                             "qemu": True, "sdk_commit": self.manifest["sdk_commit"]},
                "abi": {"major": abi["major"], "minor": abi["minor"], "hash": abi["hash"], "features": abi["features"]},
                "limits": {"cart_max_size": self.manifest["cart_max_size"], "cart_ram_size": self.manifest["cart_ram_size"]},
                "slots": [{"slot": "cart0", "stored": False, "name": "", "code_size": 0, "mem_size": 0,
                           "loaded": False, "size": slot["size"], "fresh": True}]}

    def upload(self, slot: str, data: bytes) -> dict[str, Any]:
        part = next(item for item in self.manifest["slots"] if item["name"] == slot)
        flash = self.work / "qemu_flash.bin"
        shutil.copyfile(self.settings["firmware"] / "qemu_flash.bin", flash)
        shutil.copyfile(self.settings["firmware"] / "qemu_efuse.bin", self.work / "qemu_efuse.bin")
        stage_in_flash(flash, part["offset"], part["size"], data)
        return {"staged": slot, "offset": part["offset"]}

    def launch(self, slot: str) -> dict[str, Any]:
        if not _qemu_lock.acquire(blocking=False):
            raise DeployProblem("target_busy", say("deploy", "QEMU is busy with another deployment. Try again in a minute."))
        self._locked = True
        console, audio = _free_port(), _free_port()
        self.gdb_port = _free_port()
        self.log_file = (self.work / "qemu.log").open("wb")
        self.process = subprocess.Popen(
            [self.settings["binary"], "-M", "esp32c3", "-m", "4M",
             "-drive", f"file={self.work / 'qemu_flash.bin'},if=mtd,format=raw",
             "-drive", f"file={self.work / 'qemu_efuse.bin'},if=none,format=raw,id=efuse",
             "-global", "driver=nvram.esp32c3.efuse,property=drive,value=efuse",
             "-global", "driver=timer.esp32c3.timg,property=wdt_disable,value=true",
             "-nic", "user,model=open_eth", "-display", "sdl",
             "-serial", f"tcp:127.0.0.1:{console},server,nowait",
             "-serial", f"tcp:127.0.0.1:{audio},server,nowait",
             "-gdb", f"tcp:127.0.0.1:{self.gdb_port}"],
            cwd=self.work, stdout=self.log_file, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            env={**os.environ, "SDL_VIDEODRIVER": "dummy"})
        self.console = _connect(console)
        self.audio = _connect(audio)
        threading.Thread(target=self._read_console, daemon=True).start()
        threading.Thread(target=self._acknowledge_audio, daemon=True).start()
        return {"qemu": "started", "pid": self.process.pid}

    def _read_console(self) -> None:
        self.console.settimeout(0.5)
        pressed = 0.0
        while not self._stop.is_set():
            try:
                data = self.console.recv(4096)
            except socket.timeout:
                data = b""
            except OSError:
                return
            if data:
                self.serial.extend(data[: max(0, 2_000_000 - len(self.serial))])
            # A firmware that waits in its setup menu: Enter on RUN CARTRIDGE (the first entry).
            if QEMU_MENU in self.serial and not any(mark in self.serial for mark in QEMU_STARTED) \
                    and time.monotonic() - pressed > 2:
                self.console.sendall(b"\r")
                pressed = time.monotonic()

    def _acknowledge_audio(self) -> None:
        """The firmware streams 20 ms of audio at a time and waits for one byte back for each."""
        self.audio.settimeout(0.5)
        pending = 0
        try:
            self.audio.sendall(b"K" * 10)
            while not self._stop.is_set():
                try:
                    data = self.audio.recv(65536)
                except socket.timeout:
                    continue
                if not data:
                    return
                pending += len(data)
                chunk = int(self.manifest.get("audio_chunk_bytes", 882))   # 441 frames, mono or stereo
                while pending >= chunk:
                    pending -= chunk
                    self.audio.sendall(b"K")
        except OSError:
            return

    def verify(self, header: dict[str, Any], slot: str, wait: Callable[[float], None]) -> dict[str, Any]:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if any(mark in self.serial for mark in QEMU_CRASHED):
                break
            if any(mark in self.serial for mark in QEMU_STARTED):
                wait(3.0)                          # still running a few seconds later?
                if not any(mark in self.serial for mark in QEMU_CRASHED) and self.process.poll() is None:
                    return {"running": True, "serial_bytes": len(self.serial)}
                break
            if self.process.poll() is not None:
                break
            wait(0.25)
        raise DeployProblem("launch_failed", say("deploy", "The firmware in QEMU did not start the cartridge."),
                            final="failed", left=say("deploy", "QEMU was stopped; nothing else was changed."))

    def screenshot(self) -> bytes | None:
        """The firmware's framebuffer g_fb at the next prg32_gfx_present, through QEMU's GDB stub."""
        elf = self.settings["firmware"] / "PRG32.elf"
        symbols = self.manifest.get("symbols", {})
        if not self.settings.get("gdb") or not elf.is_file() or not {"g_fb", "prg32_gfx_present"} <= set(symbols):
            return None
        raw = self.work / "screen.rgb565"
        base = symbols["g_fb"]
        commands = ["set pagination off", "set confirm off", f"target remote 127.0.0.1:{self.gdb_port}",
                    f"hbreak *0x{symbols['prg32_gfx_present']:x}", "continue", "delete",
                    f"dump binary memory {raw} 0x{base:x} 0x{base + 320 * 240 * 2:x}", "detach"]
        try:
            subprocess.run([self.settings["gdb"], "-nx", "-batch", *[part for command in commands for part in ("-ex", command)]],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
        except subprocess.TimeoutExpired:
            return None
        return rgb565_to_png(raw.read_bytes(), 320, 240) if raw.is_file() else None

    def close(self) -> None:
        self._stop.set()
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.log_file.close()
            (self.work / "serial.log").write_bytes(bytes(self.serial))
        if getattr(self, "_locked", False):
            _qemu_lock.release()
            self._locked = False


def stage_in_flash(flash: Path, offset: int, size: int, data: bytes) -> None:
    """Write the cartridge into its slot of a flash image: the whole slot, so nothing old is left
    after it (SDK prg32/qemu/upload_qemu.py inject_cartridge)."""
    if len(data) > size:
        raise DeployProblem("target_full", say("deploy", "The cartridge is {size} bytes; {slot} takes at most {limit}.",
                                               size=len(data), slot="cart0", limit=size))
    with flash.open("r+b") as image:
        image.seek(0, os.SEEK_END)
        if image.tell() < offset + size:
            raise DeployProblem("target_full", say("deploy", "The QEMU flash image has no room for this slot."))
        image.seek(offset)
        image.write(data + b"\xff" * (size - len(data)))


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _connect(port: int) -> socket.socket:
    for _ in range(200):
        try:
            return socket.create_connection(("127.0.0.1", port), timeout=2)
        except OSError:
            time.sleep(0.05)
    raise ConnectionError("QEMU did not open its serial port")


# --- pictures -----------------------------------------------------------------------

def png(width: int, height: int, rows: list[bytes]) -> bytes:
    """An 8-bit RGB PNG from rows of RGB bytes (no extra library)."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"".join(b"\0" + row for row in rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def bmp_to_png(bmp: bytes) -> bytes | None:
    """The 24-bit bottom-up BMP the PRG32 web API sends, as PNG."""
    try:
        offset, width, height, bits = (struct.unpack_from("<I", bmp, 10)[0], struct.unpack_from("<i", bmp, 18)[0],
                                       struct.unpack_from("<i", bmp, 22)[0], struct.unpack_from("<H", bmp, 28)[0])
    except struct.error:
        return None
    if bits != 24 or not 0 < width <= 1024 or not 0 < abs(height) <= 1024:
        return None
    stride = (width * 3 + 3) & ~3
    rows = []
    for y in range(abs(height)):
        source = (abs(height) - 1 - y) if height > 0 else y
        line = bmp[offset + source * stride: offset + source * stride + width * 3]
        if len(line) < width * 3:
            return None
        rows.append(bytes(value for index in range(0, len(line), 3) for value in (line[index + 2], line[index + 1], line[index])))
    return png(width, abs(height), rows)


def rgb565_to_png(data: bytes, width: int, height: int) -> bytes | None:
    if len(data) < width * height * 2:
        return None
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            pixel = data[2 * (y * width + x)] | (data[2 * (y * width + x) + 1] << 8)
            row += bytes((((pixel >> 11) & 31) * 255 // 31, ((pixel >> 5) & 63) * 255 // 63, (pixel & 31) * 255 // 31))
        rows.append(bytes(row))
    return png(width, height, rows)


# --- which targets there are ----------------------------------------------------------

def checked_url(url: str) -> str:
    """An http(s) address with a host, no name or password in it, no path beyond "/"."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password \
            or parts.path not in ("", "/") or parts.query or parts.fragment:
        raise ValueError(say("deploy", "The address must look like http://192.168.4.1 or http://127.0.0.1:8080."))
    return f"{parts.scheme}://{parts.netloc}"


def targets() -> list[dict[str, Any]]:
    rows = [{"id": str(row.id), "name": row.name, "kind": row.kind, "address": row.url, "notes": row.notes,
             "evidence": EVIDENCE[row.kind], "architectures": list(ARCHITECTURES[row.kind])}
            for row in db.session.scalars(select(DeployTarget).order_by(DeployTarget.name))]
    if qemu_settings():
        rows.append({"id": "qemu", "name": "QEMU (this server)", "kind": "qemu", "address": "", "notes": "",
                     "evidence": EVIDENCE["qemu"], "architectures": list(ARCHITECTURES["qemu"])})
    return rows


def target_named(target_id: str) -> dict[str, Any] | None:
    return next((item for item in targets() if item["id"] == str(target_id)), None)


def adapter_for(target: dict[str, Any], work: Path):
    if target["kind"] == "qemu":
        settings = qemu_settings()
        if settings is None:
            raise DeployProblem("target_unknown", say("deploy", "QEMU is not set up on this server."))
        return QemuTarget(settings, work)
    return HttpTarget(target["kind"], target["address"])


def probe_target(adapter) -> dict[str, Any]:
    """The target's answer, tried again after a broken connection."""
    for attempt in range(RETRIES + 1):
        try:
            probe = adapter.probe()
            probe["fingerprint"] = fingerprint(probe)
            return probe
        except (ConnectionError, ValueError, KeyError, OSError) as error:
            if attempt == RETRIES:
                raise DeployProblem("disconnected", say("deploy", "The target does not answer: {error}",
                                                        error=str(error)[:200])) from error
            time.sleep(0.5 * (attempt + 1))
    raise AssertionError("unreachable")


# --- the cartridge to deploy ------------------------------------------------------------

def cartridge_for(artifact_id: str, principal) -> tuple[dict[str, Any], bytes]:
    """The student's own (or a shared) cartridge, checked as in step 1 of the module docstring."""
    artifact = get_resource("artifacts", str(artifact_id))
    if artifact is None or not (principal.is_admin or artifact.get("owner_id") in (None, principal.id)):
        raise DeployProblem("not_found", say("deploy", "Cartridge not found."))
    metadata = artifact.get("metadata") or {}
    if artifact.get("kind") != "prg32_cartridge" or not metadata.get("sha256") or not metadata.get("build_id"):
        raise DeployProblem("not_built_here", say("deploy", "Only cartridges this kit compiled can be deployed: press Compile first."))
    path = Path(artifact.get("path") or "")
    if not path.is_file():
        raise DeployProblem("not_found", say("deploy", "The cartridge file is gone: press Compile again."))
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != metadata["sha256"]:
        raise DeployProblem("hash_mismatch", say("deploy", "The cartridge file changed after it was built (its SHA-256 is not "
                                                 "the recorded one). Nothing was sent: press Compile again."))
    build = get_resource("builds", str(metadata["build_id"]))
    project = get_resource("projects", str(artifact.get("project_id") or ""))
    built_from = ((build or {}).get("metadata") or {}).get("project_version")
    if project is not None and built_from is not None and built_from != project.get("version"):
        raise DeployProblem("stale_build", say("deploy", "The project changed after this cartridge was compiled: "
                                               "press Compile to deploy what you see."))
    return artifact, data


# --- one deployment, step by step -----------------------------------------------------

def as_dict(item: Deployment) -> dict[str, Any]:
    result = json.loads(item.result or "{}")
    return {"id": item.id, "project_id": item.project_id, "artifact_id": item.artifact_id, "target": item.target,
            "target_kind": item.target_kind, "target_name": item.target_name, "slot": item.slot, "status": item.status,
            "progress": item.progress, "cancel_requested": item.cancel_requested, "log": json.loads(item.log or "[]"),
            "result": result, "evidence": EVIDENCE[item.target_kind], "physical_device": item.target_kind == "prg32",
            "screenshot": f"/api/deployments/{item.id}/screenshot" if result.get("screenshot") else None,
            "created_at": item.created_at, "updated_at": item.updated_at}


class Job:
    """The running deployment's record: each step, its progress and log lines, saved as it goes."""

    def __init__(self, deployment_id: str):
        self.id = deployment_id

    def _row(self) -> Deployment:
        db.session.expire_all()
        return db.session.get(Deployment, self.id)

    def say(self, line: Message | str) -> None:
        row = self._row()
        log = json.loads(row.log or "[]")
        log.append({"at": utcnow(), "text": str(line), **message_fields(line)})
        row.log, row.updated_at = json.dumps(log[-200:]), utcnow()
        db.session.commit()

    def step(self, status: str, progress: int, line: Message) -> None:
        row = self._row()
        if row.cancel_requested:
            raise Cancelled()
        row.status, row.progress = status, progress
        db.session.commit()
        self.say(line)

    def finish(self, status: str, result: dict[str, Any]) -> None:
        row = self._row()
        row.status, row.progress = status, 100
        row.result, row.updated_at = json.dumps(result, sort_keys=True), utcnow()
        db.session.commit()

    def cancelled(self) -> bool:
        return bool(self._row().cancel_requested)


def run_deployment(deployment_id: str, target: dict[str, Any], data: bytes, expect: dict[str, Any]) -> None:
    """The steps 2-5 of the module docstring, recorded in the deployment's row as they happen."""
    job = Job(deployment_id)
    row = db.session.get(Deployment, deployment_id)
    slot = row.slot
    work = Path(current_app.config["DATA_DIR"]) / "deployments" / deployment_id
    work.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {"evidence": EVIDENCE[target["kind"]], "physical_device": target["kind"] == "prg32",
                              "cartridge": {key: value for key, value in cartridge_header(data).items()}}
    adapter = None
    sent = False

    def wait(seconds: float) -> None:
        if job.cancelled():
            raise Cancelled()
        time.sleep(seconds)

    try:
        job.step("checking", 10, say("deploy", "Asking {target} who it is", target=target["name"]))
        adapter = adapter_for(target, work)
        probe = probe_target(adapter)
        result["target"] = {key: probe[key] for key in ("identity", "abi", "limits", "fingerprint")}
        if probe["fingerprint"] != expect.get("fingerprint"):
            raise DeployProblem("target_changed", say("deploy", "The target is not the one you looked at (its firmware or "
                                                      "address changed). Look at it again."))
        seen = next((item for item in probe["slots"] if item["slot"] == slot), None)
        if seen is None:
            raise DeployProblem("slot_unknown", say("deploy", "The target has no slot {slot}.", slot=slot))
        if slot_content(seen) != slot_content(expect.get("slot_content") or {}):
            raise DeployProblem("slot_changed", say("deploy", "{slot} holds something else now than when you looked. "
                                                    "Look at the target again.", slot=slot))
        header = result["cartridge"]
        problems = abi_problems(header, probe)
        if problems:
            raise DeployProblem("unsupported_abi", say("deploy", "This target cannot run the cartridge: {problems}",
                                                       problems=" ".join(str(item) for item in problems)))
        problems = room_problems(header, probe, seen)
        if problems:
            raise DeployProblem("target_full", say("deploy", "The cartridge does not fit: {problems}",
                                                   problems=" ".join(str(item) for item in problems)))
        job.step("uploading", 30, say("deploy", "Sending {bytes} bytes to {slot}", bytes=len(data), slot=slot))
        for attempt in range(RETRIES + 1):
            try:
                sent = True
                result["upload"] = adapter.upload(slot, data)
                break
            except ConnectionError as error:
                if attempt == RETRIES:
                    raise DeployProblem("disconnected", say("deploy", "The connection broke while sending: {error}",
                                                            error=str(error)[:200]), final="failed",
                                        left=say("deploy", "{slot} may hold part of the cartridge: deploy again to the same slot, "
                                                 "or choose another slot.", slot=slot)) from error
                job.say(say("deploy", "The connection broke; trying again ({attempt} of {retries})",
                            attempt=attempt + 1, retries=RETRIES))
                wait(1.0 * (attempt + 1))
        job.step("starting", 60, say("deploy", "Starting {slot}", slot=slot))
        try:
            result["launch"] = adapter.launch(slot)
            job.step("verifying", 75, say("deploy", "Waiting for the target to show the cartridge running"))
            result["running"] = adapter.verify(header, slot, wait)
        except ConnectionError as error:
            raise DeployProblem("disconnected", say("deploy", "The connection broke: {error}", error=str(error)[:200]),
                                final="failed", left=stored_but_not_started(slot)) from error
        job.say(say("deploy", "Taking a screenshot"))
        try:
            picture = adapter.screenshot()
        except (ConnectionError, OSError):
            picture = None
        if picture:
            (work / "screenshot.png").write_bytes(picture)
            result["screenshot"] = {"sha256": hashlib.sha256(picture).hexdigest(), "bytes": len(picture)}
        job.say(say("deploy", "Running on {target} ({evidence})", target=target["name"], evidence=EVIDENCE[target["kind"]]))
        job.finish("launched", result)
    except Cancelled:
        result["left"] = str(stored_but_not_started(slot) if sent else say("deploy", "Nothing was sent: the target is as it was."))
        job.say(say("deploy", "Cancelled"))
        job.finish("cancelled", result)
    except DeployProblem as problem:
        result.update({"code": problem.code, "error": str(problem), **message_fields(problem),
                       "left": str(problem.left), "left_key": problem.left.key, "left_params": problem.left.params})
        job.say(problem.args[0])
        job.finish(problem.final, result)
    except Exception as error:   # noqa: BLE001 - the record must end, whatever happened
        current_app.logger.exception("Deployment %s failed", deployment_id)
        result.update({"code": "failed", "error": str(error)[:300],
                       "left": str(stored_but_not_started(slot) if sent else say("deploy", "Nothing was sent: the target is as it was."))})
        job.finish("failed", result)
    finally:
        if adapter is not None:
            adapter.close()


def interrupted(item: Deployment) -> bool:
    """A deployment still marked running long after its last step: its server process stopped."""
    if item.status not in RUNNING:
        return False
    from datetime import datetime

    last = datetime.fromisoformat(item.updated_at)
    return (datetime.fromisoformat(utcnow()) - last).total_seconds() > JOB_LIMIT_SECONDS


# --- the API ------------------------------------------------------------------------

def _principal():
    from .auth import current_principal

    return current_principal()


def _refused(problem: DeployProblem, status: int = 409):
    return jsonify({**message_body(problem.args[0]), "code": problem.code}), status


@bp.get("/deploy")
def deploy_page():
    from flask import render_template

    from .routes import open_project

    return render_template("deploy.html", nav_project=open_project(request.args.get("project")),
                           is_admin=_principal().is_admin)


@bp.get("/api/deploy/targets")
def api_targets():
    return jsonify(targets())


@bp.post("/api/deploy/targets/<target_id>/probe")
def api_probe(target_id: str):
    """Who the target is, its ABI and limits, and what each slot holds; with a cartridge, whether it fits."""
    target = target_named(target_id)
    if target is None:
        return jsonify({**message_body(say("deploy", "Target not found.")), "code": "target_unknown"}), 404
    payload = request.get_json(silent=True) or {}
    work = Path(current_app.config["DATA_DIR"]) / "deployments" / "probe"
    try:
        probe = probe_target(adapter_for(target, work))
    except DeployProblem as problem:
        return _refused(problem, 502 if problem.code == "disconnected" else 409)
    answer = {**probe, "target": target, "evidence": EVIDENCE[target["kind"]]}
    if payload.get("artifact_id"):
        try:
            _, data = cartridge_for(payload["artifact_id"], _principal())
            header = cartridge_header(data)
        except DeployProblem as problem:
            answer["cartridge_problem"] = {**message_body(problem.args[0]), "code": problem.code}
        else:
            answer["abi_problems"] = [{**message_body(item)} for item in abi_problems(header, probe)]
            answer["slots"] = [{**slot, "problems": [{**message_body(item)} for item in room_problems(header, probe, slot)]}
                               for slot in probe["slots"]]
    return jsonify(answer)


@bp.get("/api/deployments")
def api_deployments():
    principal = _principal()
    query = select(Deployment).order_by(Deployment.created_at.desc()).limit(50)
    if not principal.is_admin:
        query = query.where(Deployment.owner_id == principal.id)
    if request.args.get("project_id"):
        query = query.where(Deployment.project_id == request.args["project_id"])
    return jsonify([as_dict(_settled(item)) for item in db.session.scalars(query)])


def _settled(item: Deployment) -> Deployment:
    if interrupted(item):
        item.status, item.progress = "failed", 100
        result = json.loads(item.result or "{}")
        result.update({"code": "interrupted", "error": str(say("deploy", "The server stopped during this deployment.")),
                       "left": str(say("deploy", "Look at the target: deploy again if the game is not there."))})
        item.result = json.dumps(result, sort_keys=True)
        db.session.commit()
    return item


@bp.post("/api/deployments")
def api_deploy():
    """Start a deployment: {"artifact_id", "target", "slot", "expect": {"fingerprint", "slot_content"}, "confirm": true}.

    ``expect`` is what the student saw when they looked at the target (the probe's ``fingerprint`` and
    the slot as it was); ``confirm`` is their "replace what is in this slot". The steps then run in
    the background; GET the deployment to follow them."""
    principal = _principal()
    payload = request.get_json(silent=True) or {}
    target = target_named(str(payload.get("target") or ""))
    slot = str(payload.get("slot") or "")
    if target is None:
        return jsonify({**message_body(say("deploy", "Target not found.")), "code": "target_unknown"}), 404
    if not SLOT_NAME.match(slot):
        return jsonify({**message_body(say("deploy", "Choose the slot to use: nothing is replaced without a name.")),
                        "code": "slot_unknown"}), 400
    expect = payload.get("expect") if isinstance(payload.get("expect"), dict) else {}
    if payload.get("confirm") is not True or not expect.get("fingerprint") or not isinstance(expect.get("slot_content"), dict):
        return jsonify({**message_body(say("deploy", "Look at the target first, then confirm which slot to replace.")),
                        "code": "not_confirmed"}), 400
    try:
        artifact, data = cartridge_for(str(payload.get("artifact_id") or ""), principal)
        header = cartridge_header(data)
        architecture = (artifact.get("metadata") or {}).get("architecture")
        if architecture not in ARCHITECTURES[target["kind"]]:
            raise DeployProblem("wrong_architecture", say("deploy", "{target} runs {wanted} cartridges; this one is {architecture}.",
                                                          target=target["name"], wanted=" or ".join(ARCHITECTURES[target["kind"]]),
                                                          architecture=architecture or "?"))
    except DeployProblem as problem:
        return _refused(problem, 404 if problem.code == "not_found" else 409)
    busy = db.session.scalar(select(Deployment.id).where(Deployment.target == target["id"], Deployment.status.in_(RUNNING)))
    if busy and not interrupted(db.session.get(Deployment, busy)):
        return jsonify({**message_body(say("deploy", "Somebody is deploying to this target right now. Try again in a minute.")),
                        "code": "target_busy"}), 409
    item = Deployment(id=new_id("dep"), owner_id=principal.id, project_id=artifact.get("project_id"),
                      artifact_id=artifact["id"], target=target["id"], target_kind=target["kind"], target_name=target["name"],
                      slot=slot, result=json.dumps({"cartridge": header}, sort_keys=True))
    db.session.add(item)
    db.session.commit()
    from . import security

    security.record("deploy_started", target_type="deployment", target_id=item.id, outcome="started",
                    metadata={"target_kind": target["kind"], "slot": slot, "sha256": header["sha256"]})
    app = current_app._get_current_object()

    def background():
        with app.app_context():
            run_deployment(item.id, target, data, expect)

    if current_app.config.get("DEPLOY_INLINE"):       # tests: the steps run before the answer
        background()
        db.session.expire_all()
    else:
        threading.Thread(target=background, name=f"deploy-{item.id}", daemon=True).start()
    return jsonify(as_dict(db.session.get(Deployment, item.id))), 202


def _own(deployment_id: str) -> Deployment | None:
    principal = _principal()
    item = db.session.get(Deployment, deployment_id)
    if item is None or not (principal.is_admin or item.owner_id == principal.id):
        return None
    return item


@bp.get("/api/deployments/<deployment_id>")
def api_deployment(deployment_id: str):
    item = _own(deployment_id)
    if item is None:
        return jsonify({**message_body(say("deploy", "Deployment not found."))}), 404
    return jsonify(as_dict(_settled(item)))


@bp.post("/api/deployments/<deployment_id>/cancel")
def api_cancel(deployment_id: str):
    """Stop before the next step (a cartridge being written is finished first: half a write helps nobody)."""
    item = _own(deployment_id)
    if item is None:
        return jsonify({**message_body(say("deploy", "Deployment not found."))}), 404
    if item.status in RUNNING:
        item.cancel_requested = True
        db.session.commit()
    return jsonify(as_dict(item))


@bp.get("/api/deployments/<deployment_id>/screenshot")
def api_screenshot(deployment_id: str):
    item = _own(deployment_id)
    picture = Path(current_app.config["DATA_DIR"]) / "deployments" / deployment_id / "screenshot.png"
    if item is None or not picture.is_file():
        return jsonify({**message_body(say("deploy", "No screenshot."))}), 404
    return send_file(picture, mimetype="image/png", max_age=0)


# --- registering targets (administrators) ------------------------------------------------

@bp.route("/api/admin/deploy_targets", methods=["GET", "POST"])
@admin_required
def api_admin_targets():
    if request.method == "GET":
        return jsonify(targets())
    payload = request.get_json(silent=True) or {}
    name, kind = str(payload.get("name") or "").strip()[:80], str(payload.get("kind") or "")
    if not name or kind not in ("prg32", "prg32qt"):
        return jsonify({**message_body(say("deploy", "Give the target a name and a kind: prg32 (a console) or prg32qt."))}), 400
    try:
        url = checked_url(str(payload.get("address") or ""))
    except ValueError as error:
        return jsonify({**message_body(error.args[0])}), 400
    row = DeployTarget(name=name, kind=kind, url=url, notes=str(payload.get("notes") or "")[:500],
                       created_by=_principal().id)
    db.session.add(row)
    db.session.commit()
    from . import security

    security.record("deploy_target_added", target_type="deploy_target", target_id=str(row.id), outcome="ok",
                    metadata={"kind": kind})
    return jsonify(target_named(str(row.id))), 201


@bp.delete("/api/admin/deploy_targets/<int:target_id>")
@admin_required
def api_admin_target_delete(target_id: int):
    row = db.session.get(DeployTarget, target_id)
    if row is None:
        return jsonify({**message_body(say("deploy", "Target not found."))}), 404
    db.session.delete(row)
    db.session.commit()
    return jsonify({"deleted": True})


def delete_deployments_of(user_id: int) -> int:
    """Erasure (privacy.erase_account): the person's deployments and their folders."""
    rows = db.session.scalars(select(Deployment).where(Deployment.owner_id == user_id)).all()
    for row in rows:
        shutil.rmtree(Path(current_app.config["DATA_DIR"]) / "deployments" / row.id, ignore_errors=True)
        db.session.delete(row)
    for target in db.session.scalars(select(DeployTarget).where(DeployTarget.created_by == user_id)).all():
        target.created_by = None          # the console stays registered for the class
    db.session.commit()
    return len(rows)


def init_app(app) -> None:
    app.register_blueprint(bp)
