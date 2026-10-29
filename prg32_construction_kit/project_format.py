"""The portable project format: ``prg32.project.json`` and the project archive.

A project archive is a zip file that a student can download, keep, e-mail to a
teacher and import again on any PRG32-Construction-Kit:

```text
prg32.project.json          what the project is (the manifest, see below)
src/blocks.json             the Blockly program   (authoring_mode "blocks")
src/game.c                  the Advanced C source (authoring_mode "c")
src/game.S                  handwritten RISC-V assembly (authoring_mode "assembly")
src/game.py                 PRG32 Python          (authoring_mode "python", schema_version 2)
assets/sprites/01-ship.json one file per sprite
assets/data/01-level.json   one file per asset
audio/samples/01-drum.u8    one file per AudioStudio sample (8-bit sound, 22050 Hz)
```

Only the source the student wrote is saved. Generated C and assembly are made
again from it, the same way every time, so they are not in the archive.

The manifest has a ``schema_version``. Older documents are upgraded step by
step by the functions in ``MIGRATIONS``; the old single-file JSON export
(``prg32-construction-kit-project-1.0``) counts as version 0. See
docs/adr/0001-project-manifest.md. Version 2 adds the "python" authoring mode and the
``python_language_version`` field (docs/adr/0026-prg32-python-projects.md); a version-1
document means the same in version 2.
"""

from __future__ import annotations

import io
import json
import re
import stat
import zipfile
from collections.abc import Callable
from typing import Any

from . import audio_block
from .generator import c_identifier
from .packager import SUPPORTED_ARCHITECTURES
from .source_project import validate_features

SCHEMA = "prg32-project"
SCHEMA_VERSION = 2
MANIFEST_NAME = "prg32.project.json"
ARCHIVE_SUFFIX = ".prg32project.zip"
ARCHIVE_CONTENT_TYPE = "application/zip"
LEGACY_EXPORT_ABI = "prg32-construction-kit-project-1.0"

# Which source file each authoring mode keeps. In the database the mode is
# game_json.source_mode: "c", "asm" (handwritten assembly), "python" (PRG32 Python) or absent (Blocks).
AUTHORING_MODES = ("blocks", "c", "assembly", "python")
SOURCE_FILES = {"blocks": "src/blocks.json", "c": "src/game.c", "assembly": "src/game.S", "python": "src/game.py"}
# The PRG32 Python version this kit reads and writes (python_project.LANGUAGE_VERSION).
PYTHON_LANGUAGE_VERSION = 1

# The portable PRG32 cartridge ABI the kit builds for. These copy
# prg32/abi/abi_generated.py in the PRG32 SDK (tests check they still match).
SDK_ABI = {"name": "prg32-portable-abi", "major": 1, "minor": 6, "hash": "0x260f6136"}
# Older ABI hashes a firmware with SDK_ABI still runs (COMPATIBLE_ABI_HASHES there).
SDK_COMPATIBLE_ABI_HASHES = (6563778, 1810294992)

# Limits for archives coming from outside. They are far above any classroom
# project and stop a "zip bomb" from filling the server's memory.
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 512
MAX_ENTRY_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_TEXT_FIELD = 4000

# Zip entries get this date so the same project always gives the same bytes.
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_ASSET_PATH = re.compile(r"^assets/(sprites|data)/[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.json$")
# AudioStudio samples (docs/audio_studio.md): raw sound, listed under "audio_samples" in the
# manifest so that kits from before AudioStudio skip them instead of refusing the archive.
_SAMPLE_PATH = re.compile(r"^audio/samples/[0-9]{2,3}-[A-Za-z0-9._-]{1,80}\.u8$")
_SAMPLE_ID = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
MAX_SAMPLE_BYTES = audio_block.MAX_SAMPLE_BYTES

SPRITE_FIELDS = ("name", "width", "height", "pixels", "data_url", "palette")
ASSET_FIELDS = ("name", "kind", "content_type", "data")


class ProjectFormatError(ValueError):
    """The archive or manifest cannot be used; the message says why, for a student."""


# --- reading a project row ---------------------------------------------------

def authoring_mode(project: dict[str, Any]) -> str:
    saved = project.get("game_json")
    if isinstance(saved, dict) and saved.get("source_mode") == "c":
        return "c"
    if isinstance(saved, dict) and saved.get("source_mode") == "asm":
        return "assembly"
    if isinstance(saved, dict) and saved.get("source_mode") == "python":
        return "python"
    return "blocks"


def _slug(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")[:40]
    return slug or fallback


def _numbered(kind: str, index: int, name: str) -> str:
    """``assets/sprites/01-ship.json``: the number keeps two sprites with one name apart."""
    fallback = "sprite" if kind == "sprites" else "asset"
    return f"assets/{kind}/{index:02d}-{_slug(name, fallback)}.json"


def build_manifest(project: dict[str, Any], sprites: list[dict[str, Any]], assets: list[dict[str, Any]],
                   samples: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Describe a saved project as a ``prg32.project.json`` manifest.

    ``samples`` are the AudioStudio samples: ``{"artifact_id", "name", "pcm"}``.
    """
    mode = authoring_mode(project)
    prefix = c_identifier(project.get("title") or "", "prg32_game")
    saved = project.get("game_json") if isinstance(project.get("game_json"), dict) else {}
    features = saved.get("required_features", []) if mode in ("c", "assembly") else []
    asset_list = [{"kind": "sprite", "name": str(sprite.get("name") or "sprite"),
                   "path": _numbered("sprites", index, sprite.get("name") or "")}
                  for index, sprite in enumerate(sprites, start=1)]
    asset_list += [{"kind": "asset", "name": str(asset.get("name") or "asset"),
                    "path": _numbered("data", index, asset.get("name") or "")}
                   for index, asset in enumerate(assets, start=1)]
    manifest = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "title": project.get("title") or "Untitled PRG32 Game",
        "description": project.get("description") or "",
        "author": project.get("author") or "",
        "tags": list(project.get("tags") or []),
        "authoring_mode": mode,
        "source": SOURCE_FILES[mode],
        # The cartridge's three lifecycle functions, all named after the title.
        "entry_points": {"prefix": prefix, "init": f"{prefix}_init", "update": f"{prefix}_update",
                         "draw": f"{prefix}_draw"},
        "required_features": list(features) if isinstance(features, list) else [],
        "sdk": dict(SDK_ABI),
        "targets": list(SUPPORTED_ARCHITECTURES),
        # Advanced C builds its C, assembly its assembly; Blocks and Python may also build from generated assembly.
        "build_profiles": {"default": {"source_language": "asm" if mode == "assembly" else "c"}},
        "assets": asset_list,
        "tests": [],
    }
    if mode == "python":
        manifest["python_language_version"] = PYTHON_LANGUAGE_VERSION
    if samples:
        manifest["audio_samples"] = [{"name": sample["name"], "artifact_id": sample["artifact_id"],
                                      "path": f"audio/samples/{index:02d}-{_slug(sample['name'], 'sample')}.u8"}
                                     for index, sample in enumerate(samples, start=1)]
    return manifest


def _dumps(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def project_files(project: dict[str, Any], sprites: list[dict[str, Any]],
                  assets: list[dict[str, Any]], samples: list[dict[str, Any]] | None = None) -> dict[str, bytes]:
    """All files of the archive, by path."""
    manifest = build_manifest(project, sprites, assets, samples)
    files = {MANIFEST_NAME: _dumps(manifest)}
    if manifest["authoring_mode"] == "c":
        files[manifest["source"]] = str(project["game_json"].get("source_c") or "").encode("utf-8")
    elif manifest["authoring_mode"] == "assembly":
        files[manifest["source"]] = str(project["game_json"].get("source_asm") or "").encode("utf-8")
    elif manifest["authoring_mode"] == "python":
        files[manifest["source"]] = str(project["game_json"].get("source_python") or "").encode("utf-8")
    else:
        files[manifest["source"]] = _dumps(project.get("blocks_json") or {})
    rows = [*sprites, *assets]
    for entry, row in zip(manifest["assets"], rows):
        fields = SPRITE_FIELDS if entry["kind"] == "sprite" else ASSET_FIELDS
        files[entry["path"]] = _dumps({field: row.get(field) for field in fields})
    for entry, sample in zip(manifest.get("audio_samples", []), samples or []):
        files[entry["path"]] = bytes(sample["pcm"])
    return files


def write_archive(files: dict[str, bytes]) -> bytes:
    """Zip the files deterministically: manifest first, then sorted paths, fixed dates."""
    order = [MANIFEST_NAME] + sorted(path for path in files if path != MANIFEST_NAME)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in order:
            info = zipfile.ZipInfo(path, date_time=_FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, files[path])
    return buffer.getvalue()


def export_archive(project: dict[str, Any], sprites: list[dict[str, Any]], assets: list[dict[str, Any]],
                   samples: list[dict[str, Any]] | None = None) -> bytes:
    return write_archive(project_files(project, sprites, assets, samples))


def archive_filename(project: dict[str, Any]) -> str:
    return _slug(project.get("title") or "", "prg32-project") + ARCHIVE_SUFFIX


# --- migrations --------------------------------------------------------------

def _v0_to_v1(document: dict[str, Any]) -> dict[str, Any]:
    """The old single-file export (a whole project row) becomes manifest + files."""
    project = document.get("project")
    if not isinstance(project, dict):
        raise ProjectFormatError("The old project export has no project in it")
    files = project_files(project, [], [])
    manifest = json.loads(files.pop(MANIFEST_NAME))
    return {**manifest, "_files": files}


def _v1_to_v2(document: dict[str, Any]) -> dict[str, Any]:
    """Version 2 only adds the "python" mode: a version-1 project (Blocks, C or assembly) is unchanged."""
    if document.get("authoring_mode") == "python":
        raise ProjectFormatError("A schema_version 1 project cannot be written in Python")
    return {**document, "schema_version": 2}


# MIGRATIONS[n] turns a version-n document into a version n+1 document.
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {0: _v0_to_v1, 1: _v1_to_v2}


def document_version(document: dict[str, Any]) -> int:
    if document.get("abi") == LEGACY_EXPORT_ABI:
        return 0
    if document.get("schema") != SCHEMA:
        raise ProjectFormatError(f"This is not a PRG32 project (expected schema '{SCHEMA}')")
    version = document.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ProjectFormatError("schema_version must be a whole number from 1 up")
    return version


def upgrade(document: dict[str, Any]) -> dict[str, Any]:
    """Bring any known version of a project document up to SCHEMA_VERSION."""
    if not isinstance(document, dict):
        raise ProjectFormatError("A project document must be a JSON object")
    version = document_version(document)
    if version > SCHEMA_VERSION:
        raise ProjectFormatError(f"This project was saved by a newer kit (schema_version {version}); "
                                 f"this kit reads up to {SCHEMA_VERSION}")
    while version < SCHEMA_VERSION:
        document = MIGRATIONS[version](document)
        version += 1
    return document


# --- reading an archive -----------------------------------------------------

def _safe_path(name: str) -> bool:
    if not name or name.startswith("/") or "\\" in name or ":" in name or "\x00" in name:
        return False
    return all(part not in ("", ".", "..") for part in name.split("/"))


def _text(value: Any, field: str, limit: int = MAX_TEXT_FIELD) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ProjectFormatError(f"{field} must be text")
    if len(value) > limit:
        raise ProjectFormatError(f"{field} is longer than {limit} characters")
    return value


def read_archive_files(data: bytes) -> dict[str, bytes]:
    """Open an archive from outside and return its files, after the safety checks."""
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ProjectFormatError(f"The project archive is larger than {MAX_ARCHIVE_BYTES // (1024 * 1024)} MiB")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ProjectFormatError("The file is not a zip archive") from None
    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_ENTRIES:
            raise ProjectFormatError(f"The project archive has more than {MAX_ENTRIES} files")
        files: dict[str, bytes] = {}
        total = 0
        for info in entries:
            if info.is_dir():
                continue
            if not _safe_path(info.filename):
                raise ProjectFormatError(f"Unsafe file name in the archive: {info.filename!r}")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ProjectFormatError(f"Links are not allowed in a project archive: {info.filename!r}")
            if info.flag_bits & 0x1:
                raise ProjectFormatError("Encrypted project archives are not supported")
            if info.filename in files:
                raise ProjectFormatError(f"The archive holds {info.filename!r} twice")
            if info.file_size > MAX_ENTRY_BYTES:
                raise ProjectFormatError(f"{info.filename} is larger than {MAX_ENTRY_BYTES // (1024 * 1024)} MiB")
            # Read at most one byte more than allowed: the size in the header may lie.
            with archive.open(info) as stream:
                content = stream.read(MAX_ENTRY_BYTES + 1)
            if len(content) > MAX_ENTRY_BYTES:
                raise ProjectFormatError(f"{info.filename} is larger than {MAX_ENTRY_BYTES // (1024 * 1024)} MiB")
            total += len(content)
            if total > MAX_TOTAL_BYTES:
                raise ProjectFormatError("The project archive unpacks to more than "
                                         f"{MAX_TOTAL_BYTES // (1024 * 1024)} MiB")
            files[info.filename] = content
    return files


def _json_file(files: dict[str, bytes], path: str) -> Any:
    if path not in files:
        raise ProjectFormatError(f"The archive is missing {path}")
    try:
        return json.loads(files[path].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProjectFormatError(f"{path} is not valid JSON: {exc}") from None


def _check_manifest(manifest: dict[str, Any]) -> None:
    mode = manifest.get("authoring_mode")
    if mode not in AUTHORING_MODES:
        raise ProjectFormatError("authoring_mode must be one of: " + ", ".join(AUTHORING_MODES))
    if manifest.get("source") != SOURCE_FILES[mode]:
        raise ProjectFormatError(f"A {mode} project keeps its source in {SOURCE_FILES[mode]}")
    if mode == "python" and manifest.get("python_language_version") != PYTHON_LANGUAGE_VERSION:
        raise ProjectFormatError(f"This project is written in PRG32 Python version "
                                 f"{manifest.get('python_language_version')!r}; this kit reads version "
                                 f"{PYTHON_LANGUAGE_VERSION}")
    tags = manifest.get("tags", [])
    if not isinstance(tags, list) or len(tags) > 50 or any(not isinstance(tag, str) or len(tag) > 60 for tag in tags):
        raise ProjectFormatError("tags must be a list of at most 50 short words")
    if not isinstance(manifest.get("assets", []), list):
        raise ProjectFormatError("assets must be a list")
    try:
        validate_features(manifest.get("required_features", []))
    except ValueError as exc:
        raise ProjectFormatError(str(exc)) from None


def contents_from_files(files: dict[str, bytes]) -> dict[str, Any]:
    """Turn archive files into what the kit stores: one project, its sprites and assets.

    Returns ``{"manifest", "project", "sprites", "assets", "audio_samples", "ignored"}``. The
    project has no owner here; the caller makes it belong to the importer.
    """
    manifest = upgrade(_json_file(files, MANIFEST_NAME))
    if "_files" in manifest:  # an upgraded legacy export carries its files inline
        files = {**files, **manifest.pop("_files")}
    _check_manifest(manifest)
    mode = manifest["authoring_mode"]
    project: dict[str, Any] = {
        "title": _text(manifest.get("title"), "title", 200) or "Imported PRG32 Game",
        "description": _text(manifest.get("description"), "description"),
        "author": _text(manifest.get("author"), "author", 200),
        "tags": list(manifest.get("tags", [])),
    }
    source_path = manifest["source"]
    if mode in ("c", "assembly", "python"):
        if source_path not in files:
            raise ProjectFormatError(f"The archive is missing {source_path}")
        try:
            text = files[source_path].decode("utf-8")
        except UnicodeDecodeError:
            raise ProjectFormatError(f"{source_path} is not UTF-8 text") from None
        project["blocks_json"] = {}
        if mode == "python":
            # The text is only stored: it is checked (never run) when it is generated or built.
            project["game_json"] = {"source_mode": "python", "source_python": text,
                                    "python_language_version": PYTHON_LANGUAGE_VERSION}
        else:
            source_mode, field = ("c", "source_c") if mode == "c" else ("asm", "source_asm")
            project["game_json"] = {"source_mode": source_mode, field: text,
                                    "required_features": list(manifest.get("required_features", []))}
    else:
        blocks = _json_file(files, source_path)
        if not isinstance(blocks, dict):
            raise ProjectFormatError(f"{source_path} must hold a Blockly workspace object")
        project["blocks_json"] = blocks
        project["game_json"] = {}
    sprites: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    used = {MANIFEST_NAME, source_path}
    for entry in manifest.get("assets", []):
        path = entry.get("path") if isinstance(entry, dict) else None
        kind = entry.get("kind") if isinstance(entry, dict) else None
        if not isinstance(path, str) or not _ASSET_PATH.match(path) or kind not in ("sprite", "asset"):
            raise ProjectFormatError(f"Unknown asset entry in the manifest: {entry!r}")
        if (kind == "sprite") != path.startswith("assets/sprites/"):
            raise ProjectFormatError(f"{path} is in the wrong folder for a {kind}")
        if path in used:
            raise ProjectFormatError(f"{path} is listed twice")
        used.add(path)
        row = _json_file(files, path)
        if not isinstance(row, dict):
            raise ProjectFormatError(f"{path} must hold a JSON object")
        if kind == "sprite":
            sprites.append(_sprite_row(row, path))
        else:
            assets.append(_asset_row(row, path))
    samples = _samples(manifest.get("audio_samples", []), files, used)
    ignored = sorted(path for path in files if path not in used)
    return {"manifest": manifest, "project": project, "sprites": sprites, "assets": assets,
            "audio_samples": samples, "ignored": ignored}


def _samples(entries: Any, files: dict[str, bytes], used: set[str]) -> list[dict[str, Any]]:
    """The AudioStudio samples of an archive: raw sound bytes, never run or interpreted."""
    if not isinstance(entries, list) or len(entries) > 64:
        raise ProjectFormatError("audio_samples must be a list of at most 64 samples")
    samples = []
    for entry in entries:
        path = entry.get("path") if isinstance(entry, dict) else None
        artifact_id = entry.get("artifact_id") if isinstance(entry, dict) else None
        if not isinstance(path, str) or not _SAMPLE_PATH.match(path) or not isinstance(artifact_id, str) \
                or not _SAMPLE_ID.match(artifact_id):
            raise ProjectFormatError(f"Unknown audio sample entry in the manifest: {entry!r}")
        if path in used:
            raise ProjectFormatError(f"{path} is listed twice")
        if path not in files:
            raise ProjectFormatError(f"The archive is missing {path}")
        if len(files[path]) > MAX_SAMPLE_BYTES:
            raise ProjectFormatError(f"{path} is longer than a PRG32 sample can be")
        used.add(path)
        samples.append({"name": _text(entry.get("name"), f"{path} name", 32) or "sample",
                        "artifact_id": artifact_id, "pcm": files[path]})
    return samples


def _sprite_row(row: dict[str, Any], path: str) -> dict[str, Any]:
    width, height = row.get("width", 16), row.get("height", 16)
    for value in (width, height):
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 320:
            raise ProjectFormatError(f"{path}: width and height must be whole numbers from 1 to 320")
    pixels = row.get("pixels", [])
    if not isinstance(pixels, list):
        raise ProjectFormatError(f"{path}: pixels must be a list")
    from . import sprite_palette

    try:
        palette = sprite_palette.checked(row.get("palette", {}), width, height)
    except sprite_palette.PaletteError as error:
        raise ProjectFormatError(f"{path}: {error}") from error
    return {"name": _text(row.get("name"), f"{path} name", 120) or "sprite", "width": width, "height": height,
            "pixels": sprite_palette.pixels_of(palette) if palette else pixels,
            "data_url": _text(row.get("data_url"), f"{path} data_url", MAX_ENTRY_BYTES), "palette": palette}


def _asset_row(row: dict[str, Any], path: str) -> dict[str, Any]:
    return {"name": _text(row.get("name"), f"{path} name", 120) or "asset",
            "kind": _text(row.get("kind"), f"{path} kind", 60) or "text",
            "content_type": _text(row.get("content_type"), f"{path} content_type", 120) or "text/plain",
            "data": row.get("data", {})}


def import_archive(data: bytes) -> dict[str, Any]:
    return contents_from_files(read_archive_files(data))


def import_legacy_export(document: dict[str, Any]) -> dict[str, Any]:
    """Read an old ``prg32-construction-kit-project-1.0`` JSON export through the migrations."""
    return contents_from_files({MANIFEST_NAME: _dumps(document)})


def is_archive(data: bytes) -> bool:
    return data[:4] == b"PK\x03\x04"
