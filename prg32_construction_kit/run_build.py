"""Run builds: compile a project to run it in the IDE's simulator, and keep nothing (ADR-0024).

The IDE's **Run** button needs a real cartridge for the WebAssembly simulator, for Blocks, C
and assembly projects alike. A run build is a normal PRG32 build (validated source, the build
sandbox, a build slot and the disk budget) for the one target the browser core runs (qemu),
with debug information when the kit has it. Its folder is removed as soon as the cartridge is
read, and no database row is written: the cartridge and its debug maps go straight back to
the browser. Compile (``/package``) is still what makes cartridges to download or publish.

Signed-in students run their saved project (``POST /api/projects/<id>/run``); visitors without
an account send theirs (``POST /api/guest/run``, limited per address).
"""

from __future__ import annotations

import base64
import shutil
import uuid
from pathlib import Path
from typing import Any

from flask import current_app

from . import build_budget, debug_info
from . import settings as site_settings
from .build_check import toolchain_present
from .build_sandbox import settings_from_config
from .build_slots import BuildServerBusy, build_slot
from .db import release_connection
from .packager import prepare_package
from .messages import text as say

RUN_ARCHITECTURE = "qemu"   # the portable cartridge the browser core runs (static/wasm/BUILD.json)


class RunRefused(Exception):
    """A run build that cannot happen: the answer's status, code and message."""

    def __init__(self, message: str, status: int = 400, code: str = "run_refused", **details: Any):
        super().__init__(message)
        self.status = status
        self.code = code
        self.details = details


def run(project: dict[str, Any], audio: tuple[bytes, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build ``project`` (a project dict, saved or a guest's) for the simulator.

    ``project["audio_studio"]`` is its AudioStudio document (or None), as for /package;
    ``audio`` is the packed AUD0 block with that document. Returns
    ``{"ok", "log", "language", "cartridge": base64 or None, "sha256", "debug": {...}}``,
    where ``debug`` has the shape of /api/artifacts/<id>/debug for the source debugger.
    """
    from .routes import _generated_sources, generate_sources

    game_ir, c_source, refusal = generate_sources(project)
    if refusal is not None:
        problem = getattr(refusal, "problem", None)
        raise RunRefused(refusal, code=problem["code"] if problem else "run_refused",
                         **({"problems": [problem]} if problem else {}))
    assert game_ir is not None and c_source is not None
    language = "asm" if game_ir.get("source_mode") == "asm" else "c"
    sources = _generated_sources(language, game_ir, c_source)
    build_command = current_app.config["PRG32_BUILD_COMMAND"]
    if not toolchain_present(build_command):
        raise RunRefused(say("run", "This server cannot compile cartridges yet, so games cannot run in the simulator. Ask your teacher (docs/install_cartridge_build.md)."), 503, "no_toolchain")
    build_root = Path(current_app.config["BUILD_ROOT"])
    build_id = f"build_{uuid.uuid4().hex[:12]}"   # the name retention sweeps if a worker dies mid-build
    release_connection()
    try:
        with build_slot(build_root / ".slots", site_settings.get("PRG32_MAX_PARALLEL_BUILDS"),
                        site_settings.get("PRG32_BUILD_QUEUE_TIMEOUT")), \
                build_budget.reserve(build_root, site_settings.get("PRG32_BUILD_MAX_MB") * 1024 * 1024,
                                     site_settings.get("PRG32_BUILD_ROOT_MAX_MB") * 1024 * 1024):
            try:
                result = prepare_package(
                    data_dir=current_app.config["DATA_DIR"], build_root=build_root, project=project,
                    game_ir=game_ir, c_source=sources.get("c"), asm_source=sources.get("asm"),
                    build_language=language, build_id=build_id, build_command=build_command,
                    cart_ram_kib=site_settings.get("PRG32_CART_RAM_KIB"), project_json=project,
                    architectures=[RUN_ARCHITECTURE], build_timeout=site_settings.get("PRG32_BUILD_TIMEOUT"),
                    sandbox=settings_from_config(site_settings.view()),
                    debug_info_enabled=site_settings.get("PRG32_DEBUG_INFO"), audio=audio)
                return _answer(project, game_ir, language, sources, result)
            finally:
                shutil.rmtree(build_root / build_id, ignore_errors=True)
    except BuildServerBusy as busy:
        raise RunRefused(str(busy), 503, "build_busy", retry_after=10) from None
    except build_budget.BuildDiskFull as full:
        raise RunRefused(str(full), 507, "build_disk_full") from None


def _answer(project: dict[str, Any], game_ir: dict[str, Any], language: str, sources: dict[str, str],
            result: dict[str, Any]) -> dict[str, Any]:
    from .routes import _sha256_text
    from .routes import debug_python_source, project_type
    from .source_maps import project_source_map

    built = next((item for item in result["architectures"] if item["id"] == RUN_ARCHITECTURE), None)
    answer: dict[str, Any] = {"ok": built is not None, "log": result.get("log", ""), "language": language,
                              "cartridge": None, "sha256": None, "warnings": game_ir.get("warnings", [])}
    if built is None:
        return answer
    data = (Path(result["work_dir"]) / built["file"]).read_bytes()
    answer["cartridge"] = base64.b64encode(data).decode("ascii")
    answer["sha256"] = next((c["sha256"] for c in result.get("cartridges", []) if c["architecture"] == RUN_ARCHITECTURE),
                            None)
    debug_map = (result.get("debug_maps") or {}).get(RUN_ARCHITECTURE) or debug_info.unavailable(
        "this server builds without debug information")
    source = {"file": "game.c" if language == "c" else "game.S", "language": language, "text": sources[language]}
    source_map, blocks_json, python_source = None, None, None
    if project_type(project.get("game_json")) in ("blocks", "python") and result.get("debug_maps"):
        try:
            _, text, source_map = project_source_map(project, language)
        except Exception:  # noqa: BLE001 - no block map: the debugger shows source and addresses only
            text, source_map = None, None
        if source_map and text == source["text"] and source_map.get("source_sha256") == _sha256_text(text):
            python_source = debug_python_source(project, source_map)
            blocks_json = None if python_source is not None else project.get("blocks_json")
        else:
            source_map = None
    answer["debug"] = {"cartridge": {"project_id": project.get("id"), "name": built["file"],
                                     "metadata": {"architecture": RUN_ARCHITECTURE, "built_from": language}},
                       "debug_map": debug_map, "source_map": source_map, "source": source, "blocks_json": blocks_json,
                       "python_source": python_source}
    return answer
