#!/usr/bin/env python3
"""Write docker/seccomp-kit.json: Docker's default seccomp profile plus what bubblewrap needs.

    python3 tools/make_seccomp_profile.py

Input: docker/moby-seccomp-default-v0.2.4.json, Docker's own default profile
(github.com/moby/profiles, tag seccomp/v0.2.4, Apache-2.0), kept unchanged.
The kit runs each compiler inside bubblewrap (docs/build_sandbox.md), which
creates user, mount, PID and network namespaces. Docker's default profile only
allows that with CAP_SYS_ADMIN, which the kit container must not have. This
script adds one rule that allows exactly the namespace and mount system calls
bubblewrap uses; everything else stays as Docker ships it. The compilers
themselves then run under the kit's own, much stricter filter
(build_sandbox.seccomp_filter).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docker" / "moby-seccomp-default-v0.2.4.json"
TARGET = ROOT / "docker" / "seccomp-kit.json"
BUBBLEWRAP_SYSCALLS = ["clone", "unshare", "mount", "umount2", "pivot_root", "setns"]


def main() -> int:
    profile = json.loads(SOURCE.read_text(encoding="utf-8"))
    profile["syscalls"].append({"names": BUBBLEWRAP_SYSCALLS, "action": "SCMP_ACT_ALLOW"})
    TARGET.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
