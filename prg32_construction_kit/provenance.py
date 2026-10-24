"""Build provenance: what made a cartridge, written next to every build.

A teacher (or a student) can open a build and see exactly which kit, PRG32
tools, ABI, compiler, source and settings produced each ``.prg32`` file, plus
the SHA-256 fingerprint of the source and of every cartridge. Two builds of
the same saved project with the same tools give the same fingerprints; only
the build id and the start/finish times differ.

Nothing here contains a server path or a secret: commands are shortened to
program names, and versions are read without showing where things are
installed.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import os
import re
import shlex
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from .packager import (  # noqa: F401 - sha256_file re-exported
    public_command,
    sha256_file,
)
from .project_format import SDK_ABI

SCHEMA = "prg32-kit-build-provenance-1"
KIT_ROOT = Path(__file__).resolve().parent.parent
_ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:)?[\\/](?:[^\s\\/]+[\\/])+")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_revision(folder: Path) -> str | None:
    """The commit id of a git checkout, read from .git without running git (the image has no git)."""
    git_dir = folder / ".git"
    if git_dir.is_file():  # a linked worktree: ".git" names the real folder
        git_dir = (folder / git_dir.read_text(encoding="utf-8").strip().removeprefix("gitdir:").strip()).resolve()
    head_file = git_dir / "HEAD"
    if not head_file.is_file():
        return None
    head = head_file.read_text(encoding="utf-8").strip()
    if not head.startswith("ref:"):
        return head if re.fullmatch(r"[0-9a-f]{40}", head) else None
    ref = head.removeprefix("ref:").strip()
    common = git_dir
    if (git_dir / "commondir").is_file():  # branches of a worktree live in the main .git folder
        common = (git_dir / (git_dir / "commondir").read_text(encoding="utf-8").strip()).resolve()
    for base in (git_dir, common):
        if (base / ref).is_file():
            return (base / ref).read_text(encoding="utf-8").strip()
    packed = common / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8").splitlines():
            if line.endswith(" " + ref):
                return line.split(" ", 1)[0]
    return None


def _version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


@lru_cache(maxsize=1)
def kit_identity() -> dict[str, Any]:
    """This kit's version and commit (PRG32_KIT_REVISION when the image was built without .git)."""
    version = _version("prg32-construction-kit")
    if version is None:
        match = re.search(r'^version\s*=\s*"([^"]+)"', (KIT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
                          if (KIT_ROOT / "pyproject.toml").is_file() else "", re.MULTILINE)
        version = match.group(1) if match else None
    return {"name": "PRG32-Construction-Kit", "version": version,
            "revision": os.environ.get("PRG32_KIT_REVISION") or git_revision(KIT_ROOT)}


@lru_cache(maxsize=1)
def sdk_identity() -> dict[str, Any]:
    """The PRG32 SDK that the kit's Python can import (the default build command uses the same Python)."""
    spec = importlib.util.find_spec("prg32")
    revision = os.environ.get("PRG32_SDK_REVISION")
    if revision is None and spec is not None and spec.origin:
        revision = git_revision(Path(spec.origin).resolve().parent.parent)
    return {"name": "prg32", "installed": spec is not None, "version": _version("prg32"), "revision": revision}


def _no_paths(text: str) -> str:
    return _ABSOLUTE_PATH.sub("", text).strip()


@lru_cache(maxsize=4)
def toolchain_identity(tool_prefix: str = "riscv32-esp-elf-") -> dict[str, Any]:
    """The RISC-V compiler's name and the first line of ``--version``."""
    compiler = tool_prefix + "gcc"
    found = shutil.which(compiler)
    version = None
    if found:
        try:
            with subprocess.Popen([found, "--version"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True) as process:
                output, _ = process.communicate(timeout=20)
            version = _no_paths(output.splitlines()[0]) if output else None
        except Exception:  # noqa: BLE001 - a missing version must never stop a build
            version = None
    return {"compiler": compiler, "found": found is not None, "version": version}


def command_identity(build_command: str) -> dict[str, Any]:
    """The build command without folders or secrets, plus a fingerprint of the exact command."""
    try:
        parts = shlex.split(build_command)
    except ValueError:
        parts = build_command.split()
    return {"command": public_command(parts), "sha256": sha256_text(build_command)}


def build_provenance(*, build_id: str, started_at: str, finished_at: str, status: str, build_command: str,
                     game_ir: dict[str, Any], sources: dict[str, str], built_from: str,
                     requested: list[str], cart_ram_kib: int, cartridges: list[dict[str, Any]],
                     attempts: list[dict[str, Any]], sandbox: str = "not run",
                     python_source: str | None = None) -> dict[str, Any]:
    """Everything needed to explain (and repeat) one build.

    ``python_source`` is the saved game.py of a PRG32 Python project (ADR-0026): its fingerprint,
    the language and grammar versions and the fingerprint of the IR made from it are recorded.
    """
    mode = game_ir.get("source_mode") or "blocks"
    record = {
        "schema": SCHEMA,
        "build_id": build_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "status": status,
        "kit": kit_identity(),
        "sdk": sdk_identity(),
        "abi": dict(SDK_ABI),
        "toolchain": toolchain_identity(),
        "build_command": command_identity(build_command),
        # Where the source came from: blocks (generated), "c" (Advanced C), "asm" (handwritten) or "python".
        "authoring": {"blocks": "blocks", "c": "c", "asm": "assembly"}.get(mode, mode),
        "source_language": built_from,
        "entry_prefix": game_ir.get("entry_prefix"),
        "required_features": list(game_ir.get("required_features") or []),
        "cart_ram_kib": cart_ram_kib,
        "architectures_requested": list(requested),
        "source_sha256": sha256_text(sources[built_from]),
        "sources": {language: {"sha256": sha256_text(text), "bytes": len(text.encode("utf-8"))}
                    for language, text in sorted(sources.items())},
        "attempts": attempts,
        "cartridges": cartridges,
        # How the compiler was isolated: "bwrap", "rlimit" (limits only) or "unavailable".
        "sandbox": sandbox,
    }
    if mode == "python" and python_source is not None:
        from .python_project import GRAMMAR, LANGUAGE, LANGUAGE_VERSION

        record["python"] = {"language": LANGUAGE, "language_version": LANGUAGE_VERSION, "grammar": GRAMMAR,
                            "file": "game.py", "source_sha256": sha256_text(python_source),
                            "ir_abi": game_ir.get("abi"), "ir_sha256": ir_fingerprint(game_ir)}
    return record


def ir_fingerprint(game_ir: dict[str, Any]) -> str:
    """The SHA-256 of the game IR written with sorted keys: the same source gives the same IR."""
    import json

    return sha256_text(json.dumps(game_ir, sort_keys=True, separators=(",", ":"), ensure_ascii=True))


# Fields that may differ between two builds of the same inputs.
VOLATILE_FIELDS = ("build_id", "started_at", "finished_at")
