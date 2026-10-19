"""Debug information for kit builds, without changing the cartridge (ADR-0015).

The PRG32 builder (``python -m prg32 cartridge build``) compiles with -Os and deletes
its ELF. The kit gives it a per-build ``--tool-prefix``: one small shell wrapper per
RISC-V tool, in ``<build>/debugtools/``. The wrappers call the real tools; the compiler
wrapper adds ``-g`` (debug information, which never changes the generated code) and
``-fdebug-prefix-map`` (so the build folder is not named in it), and the objcopy wrapper
keeps a copy of the linked ELF in ``<build>/debug/``.

After each cartridge the kit checks that the ELF's loadable bytes are exactly the
cartridge's code (debug_info.matches_cartridge). If not, the ELF is deleted and the
Player debugs at address level only. The wrappers run inside the build sandbox
(ADR-0010) like the tools they wrap.
"""

from __future__ import annotations

import os
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import debug_info

WRAPPED_TOOLS_DIR = "debugtools"
DEBUG_DIR = "debug"
LATEST_ELF = "latest.elf"


@dataclass
class DebugTools:
    prefix: str        # what the builder gets as --tool-prefix
    elf_out: Path      # where the objcopy wrapper copies the linked ELF
    debug_dir: Path


def is_prg32_builder(build_command: str) -> bool:
    """Only the real PRG32 builder understands --tool-prefix."""
    parts = shlex.split(build_command)
    if not parts:
        return False
    if Path(parts[0]).name == "prg32":
        return True
    return "-m" in parts and parts[parts.index("-m") + 1:parts.index("-m") + 2] == ["prg32"]


def _script(lines: list[str]) -> str:
    return "#!/bin/sh\n" + "\n".join(lines) + "\n"


def prepare(work_dir: Path, tool_prefix: str, build_command: str) -> DebugTools | None:
    """Write the wrappers for this build, or return None when the real tools are not here."""
    if not is_prg32_builder(build_command):
        return None
    gcc = shutil.which(tool_prefix + "gcc")
    if gcc is None:
        return None
    real_bin = Path(gcc).resolve().parent
    tools_dir = work_dir / WRAPPED_TOOLS_DIR
    debug_dir = work_dir / DEBUG_DIR
    tools_dir.mkdir(parents=True, exist_ok=True)
    debug_dir.mkdir(parents=True, exist_ok=True)
    elf_out = debug_dir / LATEST_ELF
    name_prefix = Path(tool_prefix).name
    for real in sorted(real_bin.iterdir()):
        if not real.name.startswith(name_prefix) or not os.access(real, os.X_OK) or real.is_dir():
            continue
        tool = real.name[len(name_prefix):]
        call = shlex.quote(str(real))
        if tool == "gcc":
            body = [f"exec {call} -g -fdebug-prefix-map={shlex.quote(str(work_dir))}=build \"$@\""]
        elif tool == "objcopy":
            body = ['for arg in "$@"; do',
                    f'  case "$arg" in *.elf) cp -- "$arg" {shlex.quote(str(elf_out))} 2>/dev/null ;; esac',
                    "done",
                    f'exec {call} "$@"']
        else:
            body = [f'exec {call} "$@"']
        wrapper = tools_dir / real.name
        wrapper.write_text(_script(body), encoding="utf-8")
        wrapper.chmod(0o755)
    return DebugTools(prefix=str(tools_dir / name_prefix), elf_out=elf_out, debug_dir=debug_dir)


def collect(tools: DebugTools, architecture: str, cartridge: Path) -> Path | None:
    """Keep the ELF of the cartridge just built, only if it describes exactly that cartridge."""
    elf = tools.elf_out
    if not elf.is_file():
        return None
    kept = tools.debug_dir / f"{architecture}.elf"
    elf.replace(kept)
    if debug_info.matches_cartridge(kept, cartridge):
        return kept
    kept.unlink(missing_ok=True)
    return None
