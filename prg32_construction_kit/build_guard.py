#!/usr/bin/env python3
"""Run one compiler command with limits, then make sure nothing it started is left running.

    python3 build_guard.py --timeout 120 --cpu 120 --memory 1073741824 --processes 256 \
        --file-size 67108864 --open-files 256 --output 262144 -- COMMAND ...

This small program is the parent of every cartridge build (see build_sandbox.py
and docs/build_sandbox.md). Inside the bubblewrap sandbox it is the only kit
code that runs. It uses only the Python standard library, on purpose: it is
mounted read-only into the sandbox on its own.

What it does:
- sets resource limits that every compiler process inherits: CPU seconds,
  memory, number of processes, size of any file written, open files, no core
  files;
- starts the command in a new process group and waits for it;
- at the timeout, kills the whole group (exit status 124);
- passes on at most --output bytes of stdout and stderr, so a compiler that
  prints without end cannot fill the server's memory;
- with --disk-budget and --watch, checks the size of the build folder four times a
  second and stops the whole group when it grows beyond the budget (exit status
  125). Together with the per-file limit this bounds what one build can write.
"""

from __future__ import annotations

import argparse
import os
import resource
import signal
import subprocess
import sys
import threading
import time

TIMEOUT_EXIT = 124
DISK_EXIT = 125
WATCH_SECONDS = 0.25


def limit(name: str, value: int) -> None:
    kind = getattr(resource, name, None)
    if kind is None or value <= 0:
        return
    try:
        resource.setrlimit(kind, (value, value))
    except (ValueError, OSError):
        # macOS does not enforce some limits (for example RLIMIT_AS); the sandbox on Linux does.
        pass


def processes_of_this_user() -> int:
    """How many processes (threads included) this user has now, as Linux counts them for RLIMIT_NPROC."""
    uid = os.getuid()
    count = 0
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/status", encoding="ascii", errors="replace") as status:
                fields = dict(line.split(":", 1) for line in status if ":" in line)
        except OSError:
            continue
        if fields.get("Uid", "").split()[:1] == [str(uid)]:
            count += int(fields.get("Threads", "1").strip() or 1)
    return count


def folder_bytes(path: str) -> int:
    """Bytes of every file under ``path`` (symbolic links not followed). A copy of build_budget's,
    because this file runs on its own inside the sandbox."""
    total, stack = 0, [path]
    while stack:
        try:
            entries = list(os.scandir(stack.pop()))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                else:
                    total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                pass
    return total


def watch_disk(child: subprocess.Popen, folder: str, budget: int, over: threading.Event) -> None:
    """Stop the build's process group as soon as its folder is bigger than ``budget`` bytes."""
    while child.poll() is None:
        if folder_bytes(folder) > budget:
            over.set()
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            return
        time.sleep(WATCH_SECONDS)


def apply_limits(args: argparse.Namespace) -> None:
    os.umask(0o077)
    limit("RLIMIT_CORE", 0)
    limit("RLIMIT_CPU", args.cpu)
    limit("RLIMIT_AS", args.memory)
    # RLIMIT_NPROC counts all of this user's processes, so the kit passes "what exists now + the
    # build's allowance" (counted outside the sandbox, which has no /proc). macOS: not set
    # (the limits-only fallback there is not a sandbox anyway).
    if sys.platform.startswith("linux"):
        limit("RLIMIT_NPROC", args.processes)
    limit("RLIMIT_FSIZE", args.file_size)
    limit("RLIMIT_NOFILE", args.open_files)


def pump(source, target, budget: int) -> None:
    """Copy at most ``budget`` bytes, then keep reading (and dropping) so the child never blocks."""
    written = 0
    truncated = False
    while True:
        chunk = source.read(65536)
        if not chunk:
            break
        if written < budget:
            part = chunk[: budget - written]
            target.write(part)
            written += len(part)
        if written >= budget and not truncated and len(chunk) > 0:
            truncated = True
    if truncated:
        target.write(b"\n[build_guard: output truncated]\n")
    target.flush()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run a build command with limits.")
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--cpu", type=int, default=0)
    parser.add_argument("--memory", type=int, default=0)
    parser.add_argument("--processes", type=int, default=0, help="RLIMIT_NPROC for the build (Linux)")
    parser.add_argument("--file-size", type=int, default=0)
    parser.add_argument("--open-files", type=int, default=0)
    parser.add_argument("--output", type=int, default=256 * 1024)
    parser.add_argument("--disk-budget", type=int, default=0, help="bytes the --watch folder may hold")
    parser.add_argument("--watch", default="", help="the build folder")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        print("build_guard: no command", file=sys.stderr)
        return 2
    apply_limits(args)
    try:
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                 start_new_session=True)
    except OSError as exc:
        print(f"build_guard: cannot start {os.path.basename(command[0])}: {exc.strerror}", file=sys.stderr)
        return 127
    pumps = [threading.Thread(target=pump, args=(child.stdout, sys.stdout.buffer, args.output), daemon=True),
             threading.Thread(target=pump, args=(child.stderr, sys.stderr.buffer, args.output), daemon=True)]
    for thread in pumps:
        thread.start()
    over_budget = threading.Event()
    if args.disk_budget > 0 and args.watch:
        threading.Thread(target=watch_disk, args=(child, args.watch, args.disk_budget, over_budget), daemon=True).start()
    try:
        child.wait(timeout=args.timeout)
        code = child.returncode
    except subprocess.TimeoutExpired:
        code = TIMEOUT_EXIT
    # Whatever happened, no process of this build may stay behind.
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    child.wait()
    for thread in pumps:
        thread.join(timeout=5)
    if over_budget.is_set():
        print(f"\nbuild_guard: stopped: the build folder grew beyond {args.disk_budget // (1024 * 1024)} MB",
              file=sys.stderr)
        return DISK_EXIT
    if code == TIMEOUT_EXIT:
        print(f"\nbuild_guard: stopped after {args.timeout:g} seconds", file=sys.stderr)
    elif code < 0:
        name = signal.Signals(-code).name if -code in signal.valid_signals() else str(-code)
        print(f"\nbuild_guard: the compiler was stopped by {name} (a resource limit may have been reached)",
              file=sys.stderr)
    return code if code >= 0 else 128 - code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
