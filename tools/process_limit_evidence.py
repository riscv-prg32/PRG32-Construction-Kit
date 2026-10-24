#!/usr/bin/env python3
"""Record the process-limit scenario a Docker server is in (ADR-0010, 2026-10-22 amendment).

    python tools/process_limit_evidence.py --expect-hidden 200 --out evidence.json

RLIMIT_NPROC is checked against every process of this user id on the whole host, but a
container's /proc shows only its own. This prints both numbers and the limit a build gets
(build_guard: what the kernel counts + PRG32_BUILD_MAX_PROCESSES). With --expect-hidden N it
fails unless at least N of this user's processes are invisible here, so CI can prove it really
tested beside other containers of the same user id (where the old /proc-based limit made every
build fail with "Resource temporarily unavailable").
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prg32_construction_kit.build_guard import processes_the_kernel_counts  # noqa: E402
from prg32_construction_kit.build_sandbox import SandboxSettings  # noqa: E402


def processes_in_proc() -> int:
    """This user's processes (threads included) that /proc shows here: what the old limit used."""
    uid = str(os.getuid())
    count = 0
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/status", encoding="ascii", errors="replace") as status:
                fields = dict(line.split(":", 1) for line in status if ":" in line)
        except OSError:
            continue
        if fields.get("Uid", "").split()[:1] == [uid]:
            count += int(fields.get("Threads", "1").strip() or 1)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--expect-hidden", type=int, default=0,
                        help="fail unless at least this many of the user's processes are not in /proc")
    parser.add_argument("--out", type=Path, help="also write the record here as JSON")
    args = parser.parse_args()

    allowance = SandboxSettings().processes
    kernel = processes_the_kernel_counts()
    visible = processes_in_proc()
    record = {
        "uid": os.getuid(),
        "kernel_count": kernel,
        "visible_in_proc": visible,
        "hidden_from_proc": None if kernel is None else kernel - visible,
        "allowance": allowance,
        "old_limit_from_proc": visible + allowance,
        "limit_now": None if kernel is None else kernel + allowance,
        "old_limit_would_refuse_every_build": kernel is not None and kernel >= visible + allowance,
    }
    print(json.dumps(record, indent=2))
    if args.out:
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if kernel is None:
        print("FAIL: the kernel refused a process even at the current limit", file=sys.stderr)
        return 1
    if record["hidden_from_proc"] < args.expect_hidden:
        print(f"FAIL: only {record['hidden_from_proc']} of this user's processes are outside this container; "
              f"expected at least {args.expect_hidden}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
