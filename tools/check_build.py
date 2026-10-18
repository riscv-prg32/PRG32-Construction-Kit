#!/usr/bin/env python3
"""Check that this computer can build PRG32 cartridges for a whole class.

Run it in the same shell (or container) and with the same environment
variables as the Construction Kit server:

    python tools/check_build.py
    python tools/check_build.py --students 10 --windows 2

It uses a throwaway data folder, so your real projects are never touched.

1. It checks that the build command (PRG32_BUILD_COMMAND) runs and that the
   RISC-V compiler is on PATH.
2. It signs in several students, opens several "browser windows" for each,
   and lets them all compile at the same moment for ESP32-C6 and QEMU.
3. It checks every student got a real cartridge of their own game and that
   nobody can download a classmate's cartridge.

The exit code is 0 when everything works. ``--quick`` runs only step 1; the
Docker image runs it every time the container starts.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flask.testing import FlaskClient  # noqa: E402

from prg32_construction_kit import create_app  # noqa: E402
from prg32_construction_kit.build_check import check_command, classroom_check  # noqa: E402
from prg32_construction_kit.config import Config  # noqa: E402

ADMIN_PASSWORD = "check-build-admin-password"


class Browser(FlaskClient):
    """A pretend browser window that signs in first (as the admin unless told otherwise)."""

    def __init__(self, *args, login=("admin", ADMIN_PASSWORD), **kwargs):
        super().__init__(*args, **kwargs)
        self.environ_base["HTTP_X_PRG32_KIT"] = "1"
        if login:
            response = self.post("/auth/login", data={"username": login[0], "password": login[1]})
            if response.status_code != 302:
                raise SystemExit(f"could not sign in as {login[0]}")


def sandbox_check() -> tuple[bool, str]:
    """Can builds run in the configured sandbox (docs/build_sandbox.md)?"""
    from prg32_construction_kit.build_sandbox import SandboxSettings, SandboxUnavailable, effective_mode

    settings = SandboxSettings(mode=Config.PRG32_BUILD_SANDBOX.lower(), production=Config.KIT_ENV == "production")
    try:
        mode = effective_mode(settings)
    except SandboxUnavailable as exc:
        return False, f"build sandbox: {exc}"
    if mode == "bwrap":
        return True, "build sandbox: bubblewrap (no network, read-only SDK, private build folder)"
    return True, "build sandbox: limits only (rlimit) - NOT isolated; use only on a trusted single-user machine"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--students", type=int, default=3, help="students building at once (default 3)")
    parser.add_argument("--windows", type=int, default=2, help="browser windows per student (default 2)")
    parser.add_argument("--architecture", action="append", choices=["esp32c6", "qemu"],
                        help="only this target (repeat for both; default both)")
    parser.add_argument("--tool-prefix", default="riscv32-esp-elf-", help="RISC-V compiler prefix")
    parser.add_argument("--quick", action="store_true", help="only check the build command and the compiler")
    args = parser.parse_args()

    print("PRG32-Construction-Kit cartridge build check\n")
    failed = False
    for ok, message in check_command(Config.PRG32_BUILD_COMMAND, args.tool_prefix):
        print(("  OK    " if ok else "  FAIL  ") + message)
        failed |= not ok
    ok, message = sandbox_check()
    print(("  OK    " if ok else "  FAIL  ") + message)
    failed |= not ok
    if failed:
        print("\nFix the lines marked FAIL first. See docs/install_cartridge_build.md.")
        return 1
    if args.quick:
        print("\nThe build tools are installed. Run without --quick to test a whole class.")
        return 0

    with tempfile.TemporaryDirectory(prefix="prg32-kit-check-") as data:
        data_dir = Path(data)
        app = create_app({
            "DATA_DIR": data_dir,
            "DB_PATH": data_dir / "check.sqlite",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{data_dir / 'check.sqlite'}",
            "BUILD_ROOT": data_dir / "builds",
            "ARTIFACT_ROOT": data_dir / "artifacts",
            "ADMIN_PASSWORD": ADMIN_PASSWORD,
            "SSO_SECRET": "",
            "SSO_PEER_URL": "",
        })
        app.test_client_class = Browser
        jobs = args.students * args.windows * len(args.architecture or [1, 2])
        print(f"\n  ...  {args.students} students x {args.windows} windows compiling at the same time "
              f"({jobs} builds, {app.config['PRG32_MAX_PARALLEL_BUILDS']} at once)")
        report = classroom_check(app, args.students, args.windows, architectures=args.architecture)

    if report["problems"]:
        for problem in report["problems"]:
            print("  FAIL  " + problem)
        first_log = next((item["log"] for item in report["results"] if item.get("log")), "")
        if first_log:
            print("\nBuild log of the first build:\n" + first_log)
        return 1
    print(f"  OK    {report['cartridges']} cartridges built, each with the right game, none shared")
    print("  OK    students cannot download each other's cartridges")
    print("\nCartridge builds are ready for your class.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
