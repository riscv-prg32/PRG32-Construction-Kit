"""A disk budget for all cartridge builds together (docs/build_sandbox.md).

Each build may use at most ``PRG32_BUILD_MAX_MB`` (build_guard.py stops it beyond
that). All builds together, finished ones included, may use at most
``PRG32_BUILD_ROOT_MAX_MB`` of ``BUILD_ROOT``. Before a build starts it *reserves* its
maximum, under one lock, so builds that start at the same moment cannot together
promise more space than there is:

    used now (every file under BUILD_ROOT)  +  reservations of running builds
    +  this build's reservation  <=  budget

A reservation is a small file in ``<BUILD_ROOT>/.budget`` that its build keeps locked.
The operating system drops the lock if the server process crashes, so a reservation
whose lock can be taken belongs to nobody and is removed. Counting is conservative:
a running build's files are counted both as used space and in its reservation.
When the budget is full the build is refused (507) and nothing is written; old builds
are removed by retention (``PRG32_KIT_KEEP_BUILDS``, ``POST /api/admin/retention``).
"""

from __future__ import annotations

import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .build_slots import _try_lock, _unlock

BUDGET_DIR = ".budget"


class BuildDiskFull(Exception):
    """All builds together would go over PRG32_BUILD_ROOT_MAX_MB."""


def folder_bytes(path: Path) -> int:
    """Bytes of every file under ``path``; symbolic links are not followed."""
    total = 0
    stack = [path]
    while stack:
        try:
            entries = list(os.scandir(stack.pop()))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                else:
                    total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                pass   # removed while counting
    return total


def _reserved(budget_dir: Path) -> int:
    """Bytes reserved by running builds; reservations of crashed processes are removed."""
    total = 0
    for item in budget_dir.glob("*.reservation"):
        try:
            handle = open(item, "r+b")
        except OSError:
            continue
        with handle:
            if _try_lock(handle):      # nobody holds it: its build is gone
                _unlock(handle)
                item.unlink(missing_ok=True)
                continue
            try:
                total += int(handle.read().decode("ascii").strip() or 0)
            except ValueError:
                pass
    return total


@contextmanager
def reserve(build_root: Path, build_bytes: int, budget_bytes: int) -> Iterator[None]:
    """Hold a reservation of ``build_bytes`` while the build runs; BuildDiskFull if it does not fit."""
    if budget_bytes <= 0:      # 0 = no budget (a single-user laptop)
        yield
        return
    budget_dir = Path(build_root) / BUDGET_DIR
    budget_dir.mkdir(parents=True, exist_ok=True)
    mine = budget_dir / f"{uuid.uuid4().hex}.reservation"
    with open(budget_dir / "count.lock", "a+b") as gate:
        while not _try_lock(gate):     # one counter at a time, across threads and workers
            time.sleep(0.05)
        try:
            used, reserved = folder_bytes(Path(build_root)), _reserved(budget_dir)
            if used + reserved + build_bytes > budget_bytes:
                megabytes = budget_bytes // (1024 * 1024)
                raise BuildDiskFull(f"The build area of this server is full ({megabytes} MB for all builds). "
                                    "Try again later; old builds are removed regularly. If this keeps happening, "
                                    "tell your teacher or the administrator.")
            handle = open(mine, "w+b")
            handle.write(str(build_bytes).encode("ascii"))
            handle.flush()
            # Shared would do, but the count above needs "can I lock it?" to mean "is its owner gone?".
            if not _try_lock(handle):
                handle.close()
                raise BuildDiskFull("The build area could not be reserved. Try again.")
        finally:
            _unlock(gate)
    try:
        yield
    finally:
        _unlock(handle)
        handle.close()
        mine.unlink(missing_ok=True)
