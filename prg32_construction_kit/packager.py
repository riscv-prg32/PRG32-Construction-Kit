from __future__ import annotations

import json
import os
import shlex
import struct
import subprocess
import zlib
import zipfile
from pathlib import Path
from typing import Any

from .generator import c_identifier


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
        "version": "0.1.0",
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


def run_prg32_build(build_command: str, source_path: Path, out_path: Path, entry_prefix: str, name: str) -> tuple[bool, str]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    command = shlex.split(build_command) + [
        str(source_path),
        "--portable",
        "--entry-prefix",
        entry_prefix,
        "--name",
        name,
        "--out",
        str(out_path),
    ]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=60)
    except FileNotFoundError as exc:
        return False, f"Build command not found: {exc}\nCommand: {' '.join(command)}"
    except subprocess.TimeoutExpired:
        return False, f"Build command timed out after 60 seconds.\nCommand: {' '.join(command)}"
    log = "$ " + " ".join(command) + "\n" + result.stdout + result.stderr
    return result.returncode == 0 and out_path.exists(), log


def prepare_package(
    *,
    data_dir: Path,
    project: dict[str, Any],
    game_ir: dict[str, Any],
    c_source: str,
    build_id: str,
    build_command: str,
    project_json: dict[str, Any],
) -> dict[str, Any]:
    slug = slugify(project.get("title") or game_ir.get("title"), "game")
    entry_prefix = game_ir.get("entry_prefix") or c_identifier(slug, "game")
    work_dir = data_dir / "builds" / build_id
    work_dir.mkdir(parents=True, exist_ok=True)
    source_path = work_dir / "game.c"
    source_path.write_text(c_source, encoding="utf-8")
    (work_dir / "project.blocks.json").write_text(json.dumps(project_json, indent=2), encoding="utf-8")
    (work_dir / "game.ir.json").write_text(json.dumps(game_ir, indent=2), encoding="utf-8")
    icon_path = work_dir / "icon.png"
    write_png_icon(icon_path)

    logs: list[str] = []
    architectures: list[dict[str, str]] = []
    for arch in ["esp32c6", "qemu"]:
        out_name = f"{slug}-{arch}.prg32"
        out_path = work_dir / out_name
        ok, log = run_prg32_build(build_command, source_path, out_path, str(entry_prefix), slug)
        logs.append(f"[{arch}]\n{log}")
        if ok:
            architectures.append({"id": arch, "file": out_name})

    manifest = project_manifest(project, game_ir, architectures)
    manifest_path = work_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    bundle_path = work_dir / f"{slug}-store-bundle.zip"
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(manifest_path, "manifest.json")
        zf.write(icon_path, "icon.png")
        zf.write(source_path, "source/game.c")
        zf.write(work_dir / "project.blocks.json", "source/project.blocks.json")
        zf.write(work_dir / "game.ir.json", "source/game.ir.json")
        for arch in architectures:
            zf.write(work_dir / arch["file"], arch["file"])
        if not architectures:
            zf.writestr(
                "BUILD_TOOLCHAIN_REQUIRED.txt",
                "No .prg32 files were produced. Install the PRG32 Python build module or set PRG32_BUILD_COMMAND, then rebuild.\n",
            )

    status = "ready" if architectures else "source-only"
    return {
        "status": status,
        "work_dir": str(work_dir),
        "source_path": str(source_path),
        "bundle_path": str(bundle_path),
        "manifest": manifest,
        "architectures": architectures,
        "log": "\n\n".join(logs),
        "publishable": bool(architectures),
    }
