"""Run every check that needs the PRG32 toolchain, in the kit's own Docker image (docs/reproducing.md).

    python3 tools/reproduce_toolchain_checks.py --out toolchain-evidence

For anyone without the RISC-V toolchain on their computer (an auditor, a reviewer): Docker
is enough. The image is built from this checkout with the PRG32 SDK at the revision the
committed fixtures record (static/wasm/BUILD.json "audio"), so the rebuilds compare byte for
byte. Inside it, with the production container's security settings, it runs:

- tools/check_build.py: a class compiling at once, and one game written each way
  (Blocks as C and as assembly, Advanced C, handwritten assembly), with their SHA-256;
- the fixture rebuilds: audio fixtures, debugger fixtures, the console audio check;
- the tests that use the real toolchain (build sandbox, provenance, handwritten assembly,
  source debugging, concurrency, the console check).

Everything goes into --out: each command's log, the check_build evidence, junit results, and
summary.json (image, SDK revision, compiler, each step's outcome). The exit code is 0 only
when every step passed. Nothing is pushed or published; the image stays local.
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE = "prg32-construction-kit:toolchain-checks"
SECURITY = ["--security-opt", f"seccomp={ROOT / 'docker' / 'seccomp-kit.json'}", "--security-opt", "apparmor=unconfined",
            "--security-opt", "no-new-privileges:true", "--cap-drop", "ALL"]
STEPS = [
    ("check_build", "python tools/check_build.py --students 2 --windows 2 --evidence /evidence/check_build.json"),
    ("audio_fixtures", "python tools/build_audio_fixtures.py --check"),
    ("debug_fixtures", "python tools/build_debug_fixtures.py --check"),
    ("hardware_audio_check", "python tools/build_hardware_audio_check.py --check"),
    ("toolchain_tests", "pip install -q --user pytest && python -m pytest -q -rs -p no:cacheprovider "
                        "--junitxml=/evidence/toolchain-tests.xml tests/test_build_sandbox.py tests/test_build_provenance.py "
                        "tests/test_handwritten_assembly.py tests/test_source_debugger.py tests/test_concurrency.py "
                        "tests/test_hardware_audio_check.py"),
]


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="folder for logs and summary.json")
    parser.add_argument("--keep-image", action="store_true", help="keep the image afterwards (it is removed by default)")
    args = parser.parse_args()
    if shutil.which("docker") is None:
        print("Docker is not installed: see docs/reproducing.md", file=sys.stderr)
        return 2
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    out.chmod(0o777)        # the container runs as an unprivileged user
    sdk = json.loads((ROOT / "static" / "wasm" / "BUILD.json").read_text())["audio"]["revision"]
    kit = git("rev-parse", "HEAD")
    summary = {"started": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "kit_revision": kit, "kit_dirty": bool(git("status", "--porcelain", "--untracked-files=no")),
               "prg32_sdk_revision": sdk, "image": IMAGE, "steps": {}}
    print(f"Building {IMAGE} (PRG32 SDK {sdk[:7]}) ...")
    with (out / "docker-build.log").open("w") as log:
        built = subprocess.run(["docker", "build", "--build-arg", "PRG32_TOOLCHAIN=1", "--build-arg", f"PRG32_REF={sdk}",
                                "--build-arg", f"PRG32_KIT_REVISION={kit}", "-t", IMAGE, str(ROOT)],
                               stdout=log, stderr=subprocess.STDOUT)
    if built.returncode != 0:
        summary["steps"]["docker_build"] = "failed"
        (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
        print(f"the image did not build: see {out / 'docker-build.log'}", file=sys.stderr)
        return 1
    compiler = subprocess.run(["docker", "run", "--rm", "--entrypoint", "riscv32-esp-elf-gcc", IMAGE, "--version"],
                              capture_output=True, text=True).stdout.splitlines()[:1]
    summary["compiler"] = compiler[0] if compiler else "unknown"
    failed = False
    for name, command in STEPS:
        with (out / f"{name}.log").open("w") as log:
            result = subprocess.run(["docker", "run", "--rm", *SECURITY, "-v", f"{out}:/evidence", "--entrypoint", "sh",
                                     IMAGE, "-c", command], stdout=log, stderr=subprocess.STDOUT)
        summary["steps"][name] = "passed" if result.returncode == 0 else "failed"
        failed |= result.returncode != 0
        print(f"  {'OK  ' if result.returncode == 0 else 'FAIL'}  {name}")
    summary["finished"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    summary["outcome"] = "failed" if failed else "passed"
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    if not args.keep_image:
        subprocess.run(["docker", "image", "rm", "-f", IMAGE], capture_output=True)
    print(f"\n{summary['outcome'].upper()}: evidence in {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
