"""A small waiting line for cartridge builds.

Compiling a PRG32 cartridge starts a real compiler. If a whole classroom
clicks **Compile** at the same moment, starting thirty compilers at once would
make every build slow (or run the server out of memory). Instead the server
keeps a fixed number of *build slots*. A build takes a free slot, compiles,
and gives the slot back. When all slots are busy the next build waits its
turn, and gives up with a friendly "server busy" message after a timeout.

Each slot is a tiny lock file in ``<BUILD_ROOT>/.slots``. The operating system
releases a file lock automatically if a process crashes, and file locks work
for every thread *and* every worker process of one server, so the limit holds
for the Flask development server and for gunicorn with several workers.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:  # Linux and macOS
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt


class BuildServerBusy(Exception):
    """Raised when no build slot became free before the timeout."""


def _try_lock(handle) -> bool:
    try:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        return False


def _unlock(handle) -> None:
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    else:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


@contextmanager
def build_slot(slot_dir: Path, limit: int, timeout: float, poll_seconds: float = 0.2) -> Iterator[int]:
    """Wait for one of ``limit`` build slots, yield its number, then free it."""
    slot_dir.mkdir(parents=True, exist_ok=True)
    limit = max(1, int(limit))
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        for number in range(limit):
            handle = open(slot_dir / f"slot-{number}.lock", "a+b")
            if _try_lock(handle):
                try:
                    yield number
                finally:
                    _unlock(handle)
                    handle.close()
                return
            handle.close()
        if time.monotonic() >= deadline:
            raise BuildServerBusy(
                f"All {limit} cartridge build slots are busy. Wait a moment, then compile again."
            )
        time.sleep(poll_seconds)


def try_slot(slot_dir: Path, limit: int):
    """Take one free slot of ``limit`` without waiting: an open, locked file, or None when all are busy.

    For holders that start in one thread and finish in another (the mail queue, mail_queue.py);
    give the slot back with ``release_slot``.
    """
    slot_dir.mkdir(parents=True, exist_ok=True)
    for number in range(max(1, int(limit))):
        handle = open(slot_dir / f"slot-{number}.lock", "a+b")
        if _try_lock(handle):
            return handle
        handle.close()
    return None


def release_slot(handle) -> None:
    _unlock(handle)
    handle.close()
