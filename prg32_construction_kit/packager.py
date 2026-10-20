from __future__ import annotations

import hashlib
import json
import re
import shlex
import shutil
import struct
import subprocess
import zipfile
import zlib
from pathlib import Path
from typing import Any

from . import build_guard, build_sandbox, debug_build, debug_info, store_contract
from .generator import c_identifier

# Cartridge targets the kit knows how to build: the real board and the QEMU emulator.
SUPPORTED_ARCHITECTURES = ["esp32c6", "qemu"]


def slugify(value: str | None, fallback: str = "game") -> str:
    slug = c_identifier(value, fallback).replace("_", "-")
    return slug or fallback


def write_png_icon(path: Path, size: int = 64) -> None:
    """Write a tiny dependency-free PNG icon for store bundles."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for y in range(size):
        row = bytearray([0])  # filter byte
        for x in range(size):
            checker = ((x // 8) + (y // 8)) % 2
            r = 20 + (40 if checker else 0)
            g = 120 + (80 if x > y else 0)
            b = 180 + (40 if checker else 0)
            a = 255
            row.extend([r, g, b, a])
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def project_manifest(project: dict[str, Any], game_ir: dict[str, Any], architectures: list[dict[str, str]]) -> dict[str, Any]:
    slug = slugify(project.get("title") or game_ir.get("title"), "game")
    tags = project.get("tags") if isinstance(project.get("tags"), list) else []
    return {
        "abi": "prg32-metadata-1.0",
        "id": f"org.prg32kit.{slug}",
        "title": project.get("title") or game_ir.get("title") or "PRG32 Blocks Game",
        # A saved change makes a new version; an unchanged project keeps it (contracts/prg32-store-contract-1.json).
        "version": f"0.1.{int(project.get('version') or 0)}",
        "summary": project.get("description") or "A PRG32 game made with blocks.",
        "description": project.get("description") or "Built with PRG32-Construction-Kit.",
        "authors": [project.get("author") or "Student"],
        "license": "MIT",
        "tags": tags,
        "assets": {"icon": "icon.png"},
        "architectures": architectures,
        "generator": {
            "name": "PRG32-Construction-Kit",
            "abi": game_ir.get("abi", "prg32-construction-kit-game-1.0"),
        },
    }


def build_environment(work_dir: Path) -> dict[str, str]:
    """Environment for one build: a short allow-list (no secrets) and a private ``<build_id>/tmp``.

    The PRG32 builder already compiles in a fresh temporary folder, but pointing
    TMPDIR at ``<build_id>/tmp`` means nothing a build writes can ever land next
    to another student's build. Nothing else of the server's environment
    (secret keys, passwords, tokens) is passed on (build_sandbox.ALLOWED_ENV).
    """
    (work_dir / "tmp").mkdir(parents=True, exist_ok=True)
    return build_sandbox.build_env(work_dir)


# An absolute folder path such as /opt/PRG32/components/ (not part of a URL or <build>/).
_HOST_FOLDER = re.compile(r"(?<![\w>.:/])/(?:[^\s/:'\"()<>]+/)+")
_SECRET_WORDS = ("token", "password", "secret", "key", "auth")


def redact_build_path(log: str, work_dir: Path) -> str:
    """Keep compiler logs useful without exposing the server's directory layout.

    The build's own folder becomes ``<build>``; any other absolute folder (the
    SDK, the Python installation) is dropped, keeping the file name.
    """
    return _HOST_FOLDER.sub("", log.replace(str(work_dir), "<build>"))


def public_command(parts: list[str]) -> str:
    """A build command as students may see it: program names only, secret-looking options hidden."""
    shown = []
    for part in parts:
        if "=" in part and any(word in part.split("=", 1)[0].lower() for word in _SECRET_WORDS):
            shown.append(part.split("=", 1)[0] + "=<hidden>")
        elif "/" in part or "\\" in part:
            shown.append(Path(part.replace("\\", "/")).name)
        else:
            shown.append(part)
    return " ".join(shown)


def run_prg32_build(build_command: str, source_path: Path, out_path: Path, entry_prefix: str, name: str, architecture: str, cart_ram_kib: int, required_features: list[str] | None = None, timeout: float = 120, sandbox: build_sandbox.SandboxSettings | None = None, extra_args: list[str] | None = None) -> tuple[bool, str]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    program = shlex.split(build_command)
    command = program + [
        str(source_path),
        "--portable",
        "--architecture",
        architecture,
        "--cart-ram-kib",
        str(cart_ram_kib),
        "--entry-prefix",
        entry_prefix,
        "--name",
        name,
        "--out",
        str(out_path),
    ]
    for feature in required_features or []:
        command.extend(["--required-feature", feature])
    command.extend(extra_args or [])  # --tool-prefix of a debug build (debug_build.py)
    if "multiplayer" in (required_features or []):
        # Also sets the cartridge header's multiplayer flag (PRG32 builder option).
        command.append("--multiplayer")
    # The log shows the build command by program name (no server folders or secrets);
    # the build's own paths stay and become <build>/... in redact_build_path.
    shown = " ".join([public_command(program), *command[len(program):]])
    # Every compiler run goes through the build sandbox (build_sandbox.py, ADR-0010): bubblewrap
    # isolation plus build_guard.py's limits, timeout and process-group kill.
    try:
        prepared = build_sandbox.prepare(sandbox or build_sandbox.SandboxSettings(), command, out_path.parent,
                                         build_command, timeout)
    except build_sandbox.SandboxUnavailable as exc:
        return False, f"{exc}\nCommand: {shown}"
    try:
        # The guard stops the build at `timeout`; the extra time only covers starting the sandbox.
        result = subprocess.run(prepared.argv, check=False, capture_output=True, text=True, timeout=timeout + 30,
                                env=prepared.env, pass_fds=prepared.pass_fds, cwd=prepared.cwd)
    except FileNotFoundError:
        return False, f"Build command not found: {public_command(program[:1])}\nCommand: {shown}"
    except subprocess.TimeoutExpired:
        return False, f"Build command timed out after {timeout:g} seconds.\nCommand: {shown}"
    finally:
        prepared.close()
    log = "$ " + shown + "\n" + (result.stdout or "") + (result.stderr or "")
    if result.returncode == build_guard.TIMEOUT_EXIT:
        log += f"\nBuild command timed out after {timeout:g} seconds."
    elif result.returncode == build_guard.DISK_EXIT:
        log += "\nThe build was stopped because it wrote more than one build may (PRG32_BUILD_MAX_MB)."
    return result.returncode == 0 and out_path.exists(), log


def sha256_file(path: Path) -> tuple[str, int]:
    """SHA-256 (hex) and size in bytes of a file."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def prepare_package(
    *,
    data_dir: Path,
    project: dict[str, Any],
    game_ir: dict[str, Any],
    c_source: str | None,
    build_id: str,
    build_command: str,
    cart_ram_kib: int,
    project_json: dict[str, Any],
    build_root: Path | None = None,
    architectures: list[str] | None = None,
    build_timeout: float = 120,
    asm_source: str | None = None,
    build_language: str = "c",
    sandbox: build_sandbox.SandboxSettings | None = None,
    debug_info_enabled: bool = False,
) -> dict[str, Any]:
    """Write the sources, compile one cartridge per architecture and zip a Store bundle.

    ``c_source`` and ``asm_source`` are the generated files (either may be None);
    ``build_language`` ("c" or "asm") says which one the PRG32 builder compiles.
    Both files are put in the bundle so students can study them side by side.
    """
    slug = slugify(project.get("title") or game_ir.get("title"), "game")
    entry_prefix = game_ir.get("entry_prefix") or c_identifier(slug, "game")
    work_dir = (build_root or data_dir / "builds") / build_id
    work_dir.mkdir(parents=True, exist_ok=True)
    sources: dict[str, Path] = {}
    if c_source is not None:
        sources["c"] = work_dir / "game.c"
        sources["c"].write_text(c_source, encoding="utf-8")
    if asm_source is not None:
        # Capital .S: the PRG32 builder runs the C preprocessor, then assembles.
        sources["asm"] = work_dir / "game.S"
        sources["asm"].write_text(asm_source, encoding="utf-8")
    if build_language not in sources:
        raise ValueError(f"No {build_language} source to build")
    source_path = sources[build_language]
    (work_dir / "project.blocks.json").write_text(json.dumps(project_json, indent=2), encoding="utf-8")
    (work_dir / "game.ir.json").write_text(json.dumps(game_ir, indent=2), encoding="utf-8")
    icon_path = work_dir / "icon.png"
    write_png_icon(icon_path)

    logs: list[str] = []
    targets = architectures or SUPPORTED_ARCHITECTURES
    architectures: list[dict[str, str]] = []
    attempts: list[dict[str, Any]] = []
    cartridges: list[dict[str, Any]] = []
    # Debug information (ADR-0015): the same cartridge, plus an ELF with DWARF kept aside.
    tools = debug_build.prepare(work_dir, (sandbox or build_sandbox.SandboxSettings()).tool_prefix,
                                build_command) if debug_info_enabled else None
    debug_maps: dict[str, dict[str, Any]] = {}
    for arch in targets:
        out_name = f"{slug}-{arch}.prg32"
        out_path = work_dir / out_name
        if tools:
            tools.elf_out.unlink(missing_ok=True)
        ok, log = run_prg32_build(build_command, source_path, out_path, str(entry_prefix), slug, arch, cart_ram_kib,
                                  game_ir.get("required_features", []), build_timeout, sandbox,
                                  ["--tool-prefix", tools.prefix] if tools else None)
        logs.append(f"[{arch}]\n{redact_build_path(log, work_dir)}")
        attempts.append({"architecture": arch, "ok": ok})
        if ok:
            architectures.append({"id": arch, "file": out_name})
            # The cartridge's fingerprint: the same source and tools give the same SHA-256.
            digest, size = sha256_file(out_path)
            cartridges.append({"architecture": arch, "file": out_name, "sha256": digest, "bytes": size})
            if tools:
                elf = debug_build.collect(tools, arch, out_path)
                debug_maps[arch] = debug_info.build_debug_map(elf) if elf else debug_info.unavailable(
                    "no debug information matched this cartridge")
    shutil.rmtree(work_dir / "tmp", ignore_errors=True)
    if tools:
        shutil.rmtree(work_dir / debug_build.WRAPPED_TOOLS_DIR, ignore_errors=True)

    manifest = project_manifest(project, game_ir, architectures)
    if architectures:
        store_contract.validate_manifest(manifest)  # a manifest the Store would refuse never becomes a bundle
    manifest_path = work_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    bundle_path = work_dir / f"{slug}-store-bundle.zip"
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(manifest_path, "manifest.json")
        zf.write(icon_path, "icon.png")
        for path in sources.values():
            zf.write(path, f"source/{path.name}")
        zf.write(work_dir / "project.blocks.json", "source/project.blocks.json")
        zf.write(work_dir / "game.ir.json", "source/game.ir.json")
        for arch in architectures:
            zf.write(work_dir / arch["file"], arch["file"])
        if not architectures:
            zf.writestr(
                "BUILD_TOOLCHAIN_REQUIRED.txt",
                "No .prg32 files were produced: this server cannot compile PRG32 cartridges yet.\n"
                "Run the kit with its Docker image (docker compose up -d --build), or install the\n"
                "PRG32 build tools by hand. See docs/install_cartridge_build.md.\n",
            )

    status = "ready" if architectures else "source-only"
    return {
        "status": status,
        "work_dir": str(work_dir),
        "source_path": str(source_path),
        "bundle_path": str(bundle_path),
        "manifest": manifest,
        "architectures": architectures,
        "cart_ram_kib": cart_ram_kib,
        "log": "\n\n".join(logs),
        "publishable": bool(architectures),
        "attempts": attempts,
        "cartridges": cartridges,
        "sandbox": _sandbox_mode(sandbox),
        "debug_maps": debug_maps,
    }


def _sandbox_mode(sandbox: build_sandbox.SandboxSettings | None) -> str:
    try:
        return build_sandbox.effective_mode(sandbox or build_sandbox.SandboxSettings())
    except build_sandbox.SandboxUnavailable:
        return "unavailable"
