"""The build sandbox (ADR-0010, audit H-03).

Portable tests check the guard (limits, timeout, process-group kill, output
cap), the environment allow-list, the bubblewrap command line and the seccomp
program. The adversarial tests act as a *compromised compiler*: the build
command is a script that tries to read other students' files, reach the
network, fork without end, fill memory or disk, create device nodes or leave
the build folder. They need a working bubblewrap (Linux; in Docker the kit's
seccomp profile) and skip cleanly elsewhere.
"""

from __future__ import annotations

import os
import shlex
import struct
import subprocess
import sys
import textwrap
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from prg32_construction_kit import build_guard, build_sandbox, packager
from prg32_construction_kit.build_sandbox import SandboxSettings, SandboxUnavailable

BWRAP = build_sandbox.bwrap_works(SandboxSettings(mode="bwrap"))
# CI's container jobs set PRG32_REQUIRE_BWRAP=1: there a sandbox that does not work fails the
# run instead of skipping the escape tests (for example under the kit's AppArmor profile).
if os.environ.get("PRG32_REQUIRE_BWRAP") == "1" and not BWRAP:
    raise RuntimeError("PRG32_REQUIRE_BWRAP=1 but bubblewrap does not work here")
needs_bwrap = pytest.mark.skipif(not BWRAP, reason="bubblewrap does not work here (needs Linux user namespaces)")


def run_build(tmp_path: Path, script: str, *, mode: str, timeout: float = 20, **limits):
    """Run ``script`` as if it were the PRG32 build command, through the real build path."""
    tool = tmp_path / "tools" / "evil_compiler.py"
    tool.parent.mkdir(parents=True, exist_ok=True)
    tool.write_text(textwrap.dedent(script))
    work = tmp_path / "data" / "builds" / "build_1"
    work.mkdir(parents=True, exist_ok=True)
    source = work / "game.c"
    source.write_text("int x;\n")
    settings = SandboxSettings(mode=mode, read_only_paths=(str(tool.parent),),
                               forbidden_paths=(str(tmp_path / "data"),), **limits)
    command = f"{shlex.quote(sys.executable)} {shlex.quote(str(tool))}"
    ok, log = packager.run_prg32_build(command, source, work / "game-qemu.prg32", "game", "game", "qemu", 64,
                                       timeout=timeout, sandbox=settings)
    return ok, log, work


# --- the guard: limits, timeout, kill, output ------------------------------------------

def guard(tmp_path, *command, timeout=10, **extra):
    args = [sys.executable, str(build_guard.__file__), "--timeout", str(timeout)]
    for key, value in extra.items():
        args += [f"--{key.replace('_', '-')}", str(value)]
    return subprocess.run([*args, "--", *command], capture_output=True, text=True, timeout=60, cwd=tmp_path,
                          check=False)


def test_a_build_runs_inside_its_own_folder_and_keeps_relative_paths(tmp_path, monkeypatch):
    """Relative writes land in the build folder (never the server's folder), and a relative
    PYTHONPATH still means what it meant where the kit was started."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sdk").mkdir()
    (tmp_path / "sdk" / "fake_sdk.py").write_text("NAME = 'found'\n")
    monkeypatch.setenv("PYTHONPATH", "sdk")
    script = "import os, sys, fake_sdk\nopen('relative.txt', 'w').write(fake_sdk.NAME + ' ' + os.getcwd())\n"
    ok, log, work = run_build(tmp_path, script, mode="rlimit")
    assert (work / "relative.txt").read_text().startswith("found ")
    assert not (tmp_path / "relative.txt").exists()


def test_timeout_kills_the_whole_process_group(tmp_path):
    marker = tmp_path / "grandchild.pid"
    script = f"""
import subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import time, os; open({str(marker)!r}, 'w').write(str(os.getpid())); time.sleep(300)"])
time.sleep(300)
"""
    started = time.monotonic()
    result = guard(tmp_path, sys.executable, "-c", script, timeout=2)
    assert result.returncode == build_guard.TIMEOUT_EXIT and "stopped after 2" in result.stderr
    assert time.monotonic() - started < 20
    time.sleep(0.5)
    pid = int(marker.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)  # the grandchild is gone too


def test_endless_output_is_capped(tmp_path):
    result = guard(tmp_path, sys.executable, "-c", "import sys\nfor _ in range(200000): sys.stdout.write('x' * 100)",
                   output=4096)
    assert result.returncode == 0
    assert len(result.stdout) < 5000 and "output truncated" in result.stdout


def test_huge_files_are_stopped(tmp_path):
    script = "f = open('big.bin', 'wb')\nfor _ in range(100): f.write(b'0' * 1024 * 1024)"
    result = guard(tmp_path, sys.executable, "-c", script, file_size=1024 * 1024)
    assert result.returncode != 0
    assert (tmp_path / "big.bin").stat().st_size <= 1024 * 1024


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="RLIMIT_NPROC is set on Linux only")
def test_the_process_limit_starts_from_what_the_kernel_counts(tmp_path):
    # In Docker the kernel counts every process of the kit's user id on the host (other
    # containers too), which /proc inside the container cannot see: a limit taken from /proc
    # made every build fail with "Resource temporarily unavailable". The guard asks the kernel.
    sleepers = [subprocess.Popen(["sleep", "60"]) for _ in range(40)]
    try:
        assert build_guard.processes_the_kernel_counts() >= 40
        started = guard(tmp_path, sys.executable, "-c", "print('started')", processes=8)
        assert started.returncode == 0 and "started" in started.stdout, started.stderr
        # The allowance still bounds what the build itself may start.
        script = ("import subprocess\nkids = []\ntry:\n    for _ in range(40): kids.append(subprocess.Popen(['sleep', '5']))\n"
                  "except OSError: print('refused after', len(kids))\nfor kid in kids: kid.kill()")
        bomb = guard(tmp_path, sys.executable, "-c", script, processes=8)
        assert "refused after" in bomb.stdout, bomb.stdout + bomb.stderr
    finally:
        for sleeper in sleepers:
            sleeper.kill()
            sleeper.wait()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="RLIMIT_AS is enforced on Linux only")
def test_memory_hogs_are_stopped(tmp_path):
    result = guard(tmp_path, sys.executable, "-c", "x = bytearray(2 * 1024 ** 3)", memory=512 * 1024 * 1024)
    assert result.returncode != 0 and "MemoryError" in result.stderr


def test_the_build_sees_no_server_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "server-secret-123")
    monkeypatch.setenv("PRG32_SSO_SECRET", "sso-secret-456")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:pw@db/x")
    _ok, log, work = run_build(tmp_path, """
        import os, sys
        print(sorted(os.environ))
        print(os.environ.get("TMPDIR"))
        sys.exit(1)
    """, mode="rlimit")
    assert "server-secret" not in log and "SECRET_KEY" not in log and "DATABASE_URL" not in log
    assert "PRG32_SSO_SECRET" not in log
    assert f"{work}/tmp" in log or "<build>/tmp" in log


# --- choosing the sandbox ----------------------------------------------------------------

def test_production_never_falls_back_to_limits_only(monkeypatch):
    monkeypatch.setattr(build_sandbox, "bwrap_works", lambda settings: False)
    with pytest.raises(SandboxUnavailable):
        build_sandbox.effective_mode(SandboxSettings(mode="auto", production=True))
    with pytest.raises(SandboxUnavailable):
        build_sandbox.effective_mode(SandboxSettings(mode="bwrap"))
    assert build_sandbox.effective_mode(SandboxSettings(mode="auto")) == "rlimit"
    assert build_sandbox.effective_mode(SandboxSettings(mode="rlimit", production=True)) == "rlimit"
    with pytest.raises(SandboxUnavailable):
        build_sandbox.effective_mode(SandboxSettings(mode="docker"))


def test_a_refused_sandbox_means_no_build(tmp_path, monkeypatch):
    monkeypatch.setattr(build_sandbox, "bwrap_works", lambda settings: False)
    calls = []
    monkeypatch.setattr(packager.subprocess, "run", lambda *a, **k: calls.append(a))
    ok, log, _work = run_build(tmp_path, "print('never runs')", mode="bwrap")
    assert not ok and "sandbox" in log.lower() and calls == []


def test_the_api_reports_the_sandbox_in_provenance(app, client, monkeypatch):
    from types import SimpleNamespace

    from prg32_construction_kit.sample_data import default_blocks

    monkeypatch.setattr(build_sandbox, "bwrap_works", lambda settings: False)
    app.config.update(PRG32_BUILD_SANDBOX="auto", KIT_ENV="development")  # whatever this machine says

    def fake(command, **_kw):
        with open(command[command.index("--out") + 1], "wb") as out:
            out.write(b"PRG2")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(packager.subprocess, "run", fake)
    project = client.post("/api/projects", json={"title": "Sbx", "blocks_json": default_blocks()}).get_json()
    build = client.post(f"/api/projects/{project['id']}/package", json={"architectures": ["qemu"]}).get_json()["build"]
    assert build["metadata"]["provenance"]["sandbox"] == "rlimit"


# --- the bubblewrap command line and mounts ------------------------------------------------

def test_bwrap_command_line_isolates_everything(tmp_path):
    data = tmp_path / "data"
    work = data / "builds" / "build_9"
    work.mkdir(parents=True)
    settings = SandboxSettings(mode="bwrap", forbidden_paths=(str(data),))
    env = build_sandbox.build_env(work)
    args = build_sandbox.bwrap_arguments(settings, work, sys.executable + " -m prg32", env, 7)
    text = " ".join(args)
    for flag in ("--unshare-all", "--die-with-parent", "--new-session", "--clearenv", "--remount-ro /",
                 "--seccomp 7", "--cap-drop ALL"):
        assert flag in text
    assert args[args.index("--bind") + 1] == str(work)            # the only writable mount
    assert args.count("--bind") == 1
    ro = [args[i + 1] for i, item in enumerate(args) if item == "--ro-bind"]
    assert not any(Path(path) == data or data.is_relative_to(Path(path)) and Path(path) != Path("/")
                   for path in ro if Path(path) != Path(build_sandbox.GUARD))
    assert "--share-net" not in text


def test_data_folders_and_their_parents_are_never_mounted(tmp_path):
    data = tmp_path / "kit" / "data"
    data.mkdir(parents=True)
    settings = SandboxSettings(read_only_paths=(str(tmp_path / "kit"), str(data), str(data / "builds"),
                                                str(tmp_path / "sdk")), forbidden_paths=(str(data),))
    (tmp_path / "sdk").mkdir()
    mounts = build_sandbox.read_only_mounts(settings, sys.executable)
    assert str((tmp_path / "sdk").resolve()) in mounts
    assert not any(str(data.resolve()).startswith(m) and m.startswith(str(tmp_path)) for m in mounts)


# --- the seccomp program ------------------------------------------------------------------------

def decode(program: bytes):
    return [struct.unpack("<HBBI", program[i:i + 8]) for i in range(0, len(program), 8)]


@pytest.mark.parametrize("machine, arch, unshare", [("x86_64", 0xC000003E, 272), ("aarch64", 0xC00000B7, 97)])
def test_seccomp_program_checks_the_architecture_and_blocks_escape_calls(machine, arch, unshare):
    insns = decode(build_sandbox.seccomp_filter(machine))
    assert insns[0] == (0x20, 0, 0, 4)                 # load arch
    assert insns[1] == (0x15, 1, 0, arch)              # right arch: skip the kill
    assert insns[2] == (0x06, 0, 0, 0x80000000)        # wrong arch: kill
    assert insns[-1] == (0x06, 0, 0, 0x7FFF0000)       # default: allow
    blocked = {k for code, _jt, _jf, k in insns if code == 0x15}
    assert unshare in blocked and 435 in blocked       # unshare, clone3
    assert any(code == 0x45 for code, *_ in insns)     # clone namespace flags checked
    # Every jump stays inside the program.
    for index, (code, jt, jf, _k) in enumerate(insns):
        if code in (0x15, 0x35, 0x45):
            assert index + 1 + max(jt, jf) < len(insns)


def test_unknown_machines_get_no_silent_filter():
    with pytest.raises(SandboxUnavailable):
        build_sandbox.seccomp_filter("riscv64")


# --- adversarial builds inside bubblewrap ---------------------------------------------------------

@needs_bwrap
def test_a_compiler_cannot_read_other_builds_or_the_kit_data(tmp_path):
    secret = tmp_path / "data" / "secret_key"
    other = tmp_path / "data" / "builds" / "build_2" / "game.c"
    other.parent.mkdir(parents=True)
    secret.write_text("cookie-signing-key")
    other.write_text("another student's game")
    _ok, log, _ = run_build(tmp_path, f"""
        for path in [{str(secret)!r}, {str(other)!r}, "/etc/shadow", "/proc/1/environ"]:
            try:
                print("READ", path, open(path).read()[:40])
            except OSError as exc:
                print("DENIED", path, exc.errno)
    """, mode="bwrap")
    assert "cookie-signing-key" not in log and "another student" not in log
    assert log.count("DENIED") == 4


@needs_bwrap
def test_a_compiler_cannot_reach_the_network(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"reached")

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        _ok, log, _ = run_build(tmp_path, f"""
            import socket
            for host in ["127.0.0.1", "1.1.1.1"]:
                try:
                    s = socket.create_connection((host, {server.server_port} if host == "127.0.0.1" else 443), timeout=3)
                    s.sendall(b"GET / HTTP/1.0\\r\\n\\r\\n")
                    print("CONNECTED", host, s.recv(100))
                except OSError as exc:
                    print("NO NETWORK", host, exc.errno)
        """, mode="bwrap")
    finally:
        server.shutdown()
    assert "CONNECTED" not in log and log.count("NO NETWORK") == 2


@needs_bwrap
def test_a_compiler_cannot_write_outside_its_build_folder(tmp_path):
    outside = tmp_path / "data" / "planted.txt"
    _ok, log, work = run_build(tmp_path, f"""
        for path in [{str(outside)!r}, "/usr/planted", "/planted", "/tmp/ok.txt", "planted-in-build.txt"]:
            try:
                open(path, "w").write("x")
                print("WROTE", path)
            except OSError as exc:
                print("DENIED", path, exc.errno)
    """, mode="bwrap")
    # Nothing reaches the real data folder. (Here the data folder lives under /tmp, so the write
    # lands in the sandbox's own throwaway /tmp, which disappears with the build.)
    assert not outside.exists()
    assert "WROTE /tmp/ok.txt" in log and "WROTE planted-in-build.txt" in log  # its own scratch space
    assert "DENIED /usr/planted" in log and "DENIED /planted" in log            # read-only everywhere else
    assert (work / "planted-in-build.txt").exists()


@needs_bwrap
def test_device_nodes_and_escape_calls_are_refused(tmp_path):
    _ok, log, _ = run_build(tmp_path, """
        import ctypes, os
        libc = ctypes.CDLL(None, use_errno=True)
        for name, call in [("mknod", lambda: os.mknod("dev0", 0o600 | 0o020000, os.makedev(1, 3))),
                           ("unshare", lambda: libc.unshare(0x10000000) == 0 or (_ for _ in ()).throw(OSError(ctypes.get_errno(), "unshare"))),
                           ("ptrace", lambda: libc.ptrace(16, 1, 0, 0) == 0 or (_ for _ in ()).throw(OSError(ctypes.get_errno(), "ptrace"))),
                           ("mount", lambda: libc.mount(b"none", b"/tmp", b"tmpfs", 0, None) == 0 or (_ for _ in ()).throw(OSError(ctypes.get_errno(), "mount")))]:
            try:
                call()
                print("ALLOWED", name)
            except OSError as exc:
                print("REFUSED", name, exc.errno)
    """, mode="bwrap")
    assert "ALLOWED" not in log and log.count("REFUSED") == 4


@needs_bwrap
def test_fork_bombs_and_cpu_loops_are_contained(tmp_path):
    started = time.monotonic()
    ok, log, _ = run_build(tmp_path, """
        import os, time
        children = 0
        try:
            while True:
                if os.fork() == 0:
                    time.sleep(60)
                    os._exit(0)
                children += 1
        except OSError as exc:
            print("FORK LIMIT after", children, exc.errno, flush=True)
        while True:
            pass
    """, mode="bwrap", timeout=5, processes=32)
    assert not ok and "FORK LIMIT" in log and "stopped after 5" in log
    assert time.monotonic() - started < 40


@needs_bwrap
def test_memory_and_file_bombs_are_contained(tmp_path):
    _ok, log, work = run_build(tmp_path, """
        try:
            data = bytearray(4 * 1024 ** 3)
            print("GOT MEMORY")
        except MemoryError:
            print("MEMORY LIMIT")
        with open("fill.bin", "wb") as out:
            for _ in range(1024):
                out.write(b"0" * 1024 * 1024)
    """, mode="bwrap", memory_bytes=512 * 1024 * 1024, file_size_bytes=8 * 1024 * 1024)
    assert "MEMORY LIMIT" in log and "GOT MEMORY" not in log
    assert (work / "fill.bin").stat().st_size <= 8 * 1024 * 1024
