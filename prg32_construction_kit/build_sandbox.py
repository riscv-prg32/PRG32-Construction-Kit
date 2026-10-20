"""Where a cartridge build runs: inside a bubblewrap sandbox (docs/adr/0010-build-sandbox.md).

Students' C and assembly are checked first (source_project.py), but the
compiler is still a big program reading untrusted input. So every compiler run
is isolated:

- **bubblewrap** (``bwrap``, Linux): new user, PID, network, IPC, UTS and
  cgroup namespaces; no network at all; the operating system, Python, the
  PRG32 SDK and the RISC-V compiler mounted **read-only**; only this build's
  own folder writable; a fresh empty ``/tmp``; a read-only root; a cleared
  environment; no capabilities; a seccomp filter that refuses system calls a
  compiler never needs (mount, ptrace, new namespaces, kernel modules, ...).
- inside it, ``build_guard.py`` sets resource limits (CPU, memory, processes,
  file size, open files), keeps the output small and kills every process of
  the build at the timeout.

``PRG32_BUILD_SANDBOX`` chooses: ``bwrap`` (required: builds are refused
without it; the Docker image uses this), ``rlimit`` (only the guard's limits,
**not an isolation boundary**, for a teacher's laptop), or ``auto`` (bwrap
when it works, otherwise rlimit, except on a production server).
"""

from __future__ import annotations

import importlib.util
import os
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

GUARD = Path(__file__).resolve().parent / "build_guard.py"
GUARD_IN_SANDBOX = "/run/prg32/build_guard.py"
SYSTEM_PATHS = ("/usr", "/bin", "/sbin", "/lib", "/lib32", "/lib64", "/libx32",
                "/etc/ld.so.cache", "/etc/ld.so.conf", "/etc/ld.so.conf.d", "/etc/alternatives")
# Environment variables a build may see; everything else (secret keys, SSO secret,
# SMTP and database passwords, tokens) is left out.
ALLOWED_ENV = ("PATH", "PYTHONPATH", "LANG", "LC_ALL", "SOURCE_DATE_EPOCH")


class SandboxUnavailable(RuntimeError):
    """The required sandbox cannot run on this server; builds are refused."""


@dataclass(frozen=True)
class SandboxSettings:
    mode: str = "auto"                 # bwrap | rlimit | auto
    production: bool = False
    cpu_seconds: int = 180
    memory_bytes: int = 1536 * 1024 * 1024
    processes: int = 128            # processes the build may add to those that exist
    file_size_bytes: int = 64 * 1024 * 1024
    open_files: int = 256
    output_bytes: int = 256 * 1024
    tmp_size_bytes: int = 256 * 1024 * 1024
    build_disk_bytes: int = 256 * 1024 * 1024   # the whole build folder (build_guard --disk-budget)
    read_only_paths: tuple[str, ...] = ()
    forbidden_paths: tuple[str, ...] = ()   # data folders: never mounted
    tool_prefix: str = "riscv32-esp-elf-"


def settings_from_config(config: Any) -> SandboxSettings:
    extra = tuple(item for item in str(config.get("PRG32_BUILD_RO_PATHS") or "").split(os.pathsep) if item)
    forbidden = tuple(str(Path(config[key]).resolve()) for key in ("DATA_DIR", "BUILD_ROOT", "ARTIFACT_ROOT")
                      if config.get(key))
    return SandboxSettings(mode=str(config.get("PRG32_BUILD_SANDBOX") or "auto").lower(),
                           production=config.get("KIT_ENV") == "production",
                           memory_bytes=int(config.get("PRG32_BUILD_MEMORY_MB") or 1536) * 1024 * 1024,
                           processes=int(config.get("PRG32_BUILD_MAX_PROCESSES") or 128),
                           build_disk_bytes=int(config.get("PRG32_BUILD_MAX_MB") or 256) * 1024 * 1024,
                           read_only_paths=extra, forbidden_paths=forbidden)


# --- seccomp -------------------------------------------------------------------------
# A small classic-BPF filter (struct sock_filter, the format bwrap --seccomp reads).
# It refuses, with EPERM, system calls that a compiler never makes and that are
# typical first steps of a sandbox escape. Everything else is allowed: the
# namespaces and read-only mounts above do the main work.

_AUDIT_ARCH = {"x86_64": 0xC000003E, "aarch64": 0xC00000B7}
_BLOCKED = {
    "x86_64": {"ptrace": 101, "mount": 165, "umount2": 166, "pivot_root": 155, "chroot": 161, "swapon": 167,
               "swapoff": 168, "reboot": 169, "kexec_load": 246, "init_module": 175, "finit_module": 313,
               "delete_module": 176, "unshare": 272, "setns": 308, "keyctl": 250, "add_key": 248,
               "request_key": 249, "bpf": 321, "perf_event_open": 298, "userfaultfd": 323,
               "process_vm_readv": 310, "process_vm_writev": 311, "open_by_handle_at": 304,
               "name_to_handle_at": 303, "mknod": 133, "mknodat": 259},
    "aarch64": {"ptrace": 117, "mount": 40, "umount2": 39, "pivot_root": 41, "chroot": 51, "swapon": 224,
                "swapoff": 225, "reboot": 142, "kexec_load": 104, "init_module": 105, "finit_module": 273,
                "delete_module": 106, "unshare": 97, "setns": 268, "keyctl": 219, "add_key": 217,
                "request_key": 218, "bpf": 280, "perf_event_open": 241, "userfaultfd": 282,
                "process_vm_readv": 270, "process_vm_writev": 271, "open_by_handle_at": 265,
                "name_to_handle_at": 264, "mknodat": 33},
}
_CLONE = {"x86_64": 56, "aarch64": 220}
_CLONE3 = 435
# CLONE_NEWNS | NEWCGROUP | NEWUTS | NEWIPC | NEWUSER | NEWPID | NEWNET (a nested sandbox).
_CLONE_NAMESPACES = 0x00020000 | 0x02000000 | 0x04000000 | 0x08000000 | 0x10000000 | 0x20000000 | 0x40000000
_RET_ALLOW, _RET_KILL = 0x7FFF0000, 0x80000000
_EPERM, _ENOSYS = 1, 38


def _insn(code: int, jt: int, jf: int, k: int) -> bytes:
    return struct.pack("<HBBI", code, jt, jf, k & 0xFFFFFFFF)


def seccomp_filter(machine: str | None = None) -> bytes:
    """The BPF program for this machine (x86_64 or aarch64)."""
    machine = machine or os.uname().machine
    if machine not in _AUDIT_ARCH:
        raise SandboxUnavailable(f"no seccomp filter for {machine}")
    ld_nr, ld_arch, ld_arg0 = (0x20, 0, 0, 0), (0x20, 0, 0, 4), (0x20, 0, 0, 16)
    ret = lambda value: _insn(0x06, 0, 0, value)
    program = [_insn(*ld_arch), _insn(0x15, 1, 0, _AUDIT_ARCH[machine]), ret(_RET_KILL), _insn(*ld_nr)]
    if machine == "x86_64":  # the x32 ABI uses numbers from 0x40000000: refuse it entirely
        program += [_insn(0x35, 0, 1, 0x40000000), ret(_RET_KILL)]
    # clone3's arguments are in memory BPF cannot read: ENOSYS makes the C library use clone instead.
    program += [_insn(0x15, 0, 1, _CLONE3), ret(0x00050000 | _ENOSYS)]
    # clone with any namespace flag: EPERM (load argument 0 = flags, check, reload nr).
    program += [_insn(0x15, 0, 4, _CLONE[machine]), _insn(*ld_arg0), _insn(0x45, 0, 1, _CLONE_NAMESPACES),
                ret(0x00050000 | _EPERM), _insn(*ld_nr)]
    for number in sorted(_BLOCKED[machine].values()):
        program += [_insn(0x15, 0, 1, number), ret(0x00050000 | _EPERM)]
    program.append(ret(_RET_ALLOW))
    return b"".join(program)


# --- read-only mounts --------------------------------------------------------------------

def _existing(path: str | Path) -> str | None:
    try:
        real = Path(path).resolve()
    except OSError:
        return None
    return str(real) if real.exists() else None


def _toolchain_paths(build_command: str, tool_prefix: str) -> list[str]:
    paths = [sys.prefix, sys.base_prefix, sys.exec_prefix]
    try:
        program = shlex.split(build_command)[0]
    except (ValueError, IndexError):
        program = ""
    found = shutil.which(program) if program else None
    if found:
        paths.append(str(Path(found).resolve().parent.parent))
    gcc = shutil.which(tool_prefix + "gcc")
    if gcc:
        paths.append(str(Path(gcc).resolve().parent.parent))
    spec = importlib.util.find_spec("prg32")
    if spec and spec.origin:
        package = Path(spec.origin).resolve().parent
        # A PRG32 checkout (pip install -e): the SDK headers and components live next to the package.
        paths.append(str(package.parent if (package.parent / "components").is_dir() else package))
    paths += [item for item in os.environ.get("PYTHONPATH", "").split(os.pathsep) if item]
    return paths


def read_only_mounts(settings: SandboxSettings, build_command: str) -> list[str]:
    """System, Python, SDK and compiler folders to mount read-only (never the kit's data)."""
    wanted = [*SYSTEM_PATHS, *_toolchain_paths(build_command, settings.tool_prefix), *settings.read_only_paths]
    forbidden = [Path(item) for item in settings.forbidden_paths]
    mounts: list[str] = []
    for item in wanted:
        if item in SYSTEM_PATHS and item.count("/") == 1 and os.path.islink(item):
            continue  # recreated as a symlink (system_symlinks)
        real = _existing(item)
        if real is None or real in mounts:
            continue
        path = Path(real)
        # Mounting a data folder, or a folder that contains one, would show other students' builds.
        if any(path == bad or bad.is_relative_to(path) or path.is_relative_to(bad) for bad in forbidden):
            continue
        mounts.append(real)
    return sorted(mounts, key=lambda item: (item.count("/"), item))


# --- the command line ---------------------------------------------------------------------

def build_env(work_dir: Path) -> dict[str, str]:
    tmp_dir = str(work_dir / "tmp")
    env = {name: os.environ[name] for name in ALLOWED_ENV if os.environ.get(name)}
    env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    env.setdefault("LANG", "C.UTF-8")
    # A build runs inside its own folder, so relative entries (PYTHONPATH=../PRG32) must
    # mean what they meant where the kit was started.
    for name in ("PATH", "PYTHONPATH"):
        if env.get(name):
            env[name] = os.pathsep.join(os.path.abspath(item) if item and not os.path.isabs(item) else item
                                        for item in env[name].split(os.pathsep))
    env.update(HOME=tmp_dir, TMPDIR=tmp_dir, TEMP=tmp_dir, TMP=tmp_dir, PYTHONDONTWRITEBYTECODE="1",
               PYTHONNOUSERSITE="1")
    return env


def process_limit(settings: SandboxSettings) -> int:
    """RLIMIT_NPROC for a build: the processes this user has now plus the build's allowance (Linux)."""
    if not sys.platform.startswith("linux") or not os.path.isdir("/proc"):
        return 0
    from .build_guard import processes_of_this_user

    return processes_of_this_user() + settings.processes


def guard_arguments(settings: SandboxSettings, timeout: float, guard_path: str, work_dir: Path | None = None) -> list[str]:
    watch = ["--disk-budget", str(settings.build_disk_bytes), "--watch", str(work_dir)] if work_dir else []
    return [sys.executable, guard_path, "--timeout", f"{timeout:g}", "--cpu", str(settings.cpu_seconds),
            "--memory", str(settings.memory_bytes), "--processes", str(process_limit(settings)),
            "--file-size", str(settings.file_size_bytes), "--open-files", str(settings.open_files),
            "--output", str(settings.output_bytes), *watch, "--"]


def system_symlinks() -> list[tuple[str, str]]:
    """Top-level system paths that are symlinks (merged /usr: /bin -> usr/bin, /lib -> usr/lib)."""
    links = []
    for path in SYSTEM_PATHS:
        if path.count("/") == 1 and os.path.islink(path):
            links.append((os.readlink(path), path))
    return links


def bwrap_arguments(settings: SandboxSettings, work_dir: Path, build_command: str, env: dict[str, str],
                    seccomp_fd: int | None) -> list[str]:
    args = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL", "--clearenv"]
    for name, value in sorted(env.items()):
        args += ["--setenv", name, value]
    # A fresh, size-limited /tmp first: mounts made later (for example a build folder that
    # happens to live under /tmp) are placed on top of it instead of being hidden by it.
    args += ["--size", str(settings.tmp_size_bytes), "--tmpfs", "/tmp", "--dev", "/dev"]
    for path in read_only_mounts(settings, build_command):
        args += ["--ro-bind", path, path]
    # Recreate /bin, /lib, ... as the same symlinks, so the dynamic loader is where programs expect it.
    for target, path in system_symlinks():
        args += ["--symlink", target, path]
    # No /proc: a compiler does not need it, it would show the processes of the sandbox, and
    # Docker's masked /proc paths forbid mounting a fresh one anyway.
    args += ["--ro-bind", str(GUARD), GUARD_IN_SANDBOX,
             "--bind", str(work_dir), str(work_dir),
             "--remount-ro", "/", "--chdir", str(work_dir)]
    if seccomp_fd is not None:
        args += ["--seccomp", str(seccomp_fd)]
    return args


@dataclass
class SandboxRun:
    """One prepared run: pass ``argv``, ``env`` and ``pass_fds`` to subprocess.run, then call close()."""
    argv: list[str]
    env: dict[str, str]
    pass_fds: tuple[int, ...] = ()
    mode: str = "rlimit"
    cwd: str | None = None          # the build folder, in both modes (bwrap also does --chdir)
    _files: list[Any] = field(default_factory=list)

    def close(self) -> None:
        for item in self._files:
            item.close()


@lru_cache(maxsize=8)
def bwrap_works(settings: SandboxSettings) -> bool:
    """Can bwrap create its namespaces here? (Docker needs user namespaces allowed, see the docs.)"""
    if shutil.which("bwrap") is None or sys.platform != "linux":
        return False
    with tempfile.TemporaryDirectory(prefix="prg32-sandbox-probe-") as folder:
        probe = SandboxSettings(**{**settings.__dict__, "forbidden_paths": ()})
        args = bwrap_arguments(probe, Path(folder), sys.executable, {"PATH": "/usr/bin:/bin"}, None)
        try:
            # Popen, not subprocess.run, so tests that replace subprocess.run do not see the probe.
            with subprocess.Popen([*args, "--", sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL) as process:
                return process.wait(timeout=30) == 0
        except (OSError, subprocess.TimeoutExpired):
            return False


def effective_mode(settings: SandboxSettings) -> str:
    """"bwrap" or "rlimit"; raises SandboxUnavailable when bwrap is required and missing."""
    if settings.mode not in ("bwrap", "rlimit", "auto"):
        raise SandboxUnavailable(f"PRG32_BUILD_SANDBOX must be bwrap, rlimit or auto, not {settings.mode!r}")
    if settings.mode == "rlimit":
        return "rlimit"
    if bwrap_works(settings):
        return "bwrap"
    if settings.mode == "bwrap" or settings.production:
        raise SandboxUnavailable(
            "The build sandbox (bubblewrap) does not work on this server, so cartridge builds are refused. "
            "See docs/build_sandbox.md.")
    return "rlimit"


def prepare(settings: SandboxSettings, command: list[str], work_dir: Path, build_command: str,
            timeout: float) -> SandboxRun:
    """The argv/env for one compiler run in the chosen sandbox."""
    mode = effective_mode(settings)
    (work_dir / "tmp").mkdir(parents=True, exist_ok=True)
    env = build_env(work_dir)
    if mode == "rlimit":
        return SandboxRun([*guard_arguments(settings, timeout, str(GUARD), work_dir), *command], env, mode="rlimit",
                          cwd=str(work_dir))
    seccomp_file = tempfile.TemporaryFile()  # noqa: SIM115 - kept open for bwrap, closed by SandboxRun.close()
    seccomp_file.write(seccomp_filter())
    seccomp_file.seek(0)
    fd = seccomp_file.fileno()
    argv = [*bwrap_arguments(settings, work_dir, build_command, env, fd), "--",
            *guard_arguments(settings, timeout, GUARD_IN_SANDBOX, work_dir), *command]
    return SandboxRun(argv, env, pass_fds=(fd,), mode="bwrap", cwd=str(work_dir), _files=[seccomp_file])
