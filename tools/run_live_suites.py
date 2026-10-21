"""Run every live integration suite this computer can run, in one step (docs/live_testing.md).

    python3 tools/run_live_suites.py --out live-evidence

Each suite talks to a real service. The suites run only against throwaway or test services:

    store          a throwaway Cartridge Store on 127.0.0.1 (the CartridgeStore checkout next to
                   the kit): publishing and shared accounts      needs ../CartridgeStore
    oidc-keycloak  a disposable Keycloak in Docker: school sign-in    needs Docker
    oidc-external  an institution's TEST tenant                       needs PRG32_LIVE_OIDC_ISSUER, ...
    cloud          Google Drive or OneDrive with a TEST account       needs PRG32_LIVE_CLOUD=google|onedrive, ...
    qemu           the PRG32 firmware in Espressif QEMU: whole audio recordings
                                                                      needs ESP-IDF (idf.py on PATH)

A suite whose service is not available is "not run", with the reason: never a pass. Settings
come from the environment only. The summary records which setting NAMES were present, never
their values, and every log has the values of secret-looking settings (SECRET, TOKEN,
PASSWORD) replaced by "<redacted>", the computer's name removed and the home folder shown
as ~, before it is written.

Into --out: <suite>.log, <suite>.xml (junit) and summary.json. Exit code 0 when every suite
that ran passed (1 if one failed).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRET_WORDS = ("SECRET", "TOKEN", "PASSWORD")


def store_ready() -> str | None:
    store = Path(os.environ.get("PRG32_STORE_SOURCE") or ROOT.parent / "CartridgeStore")
    return None if (store / "cartridge_store" / "app.py").is_file() else f"no CartridgeStore checkout at {store}"


def docker_ready() -> str | None:
    if shutil.which("docker") is None:
        return "Docker is not installed"
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        return "Docker is not running"
    return None


def external_oidc_ready() -> str | None:
    return None if os.environ.get("PRG32_LIVE_OIDC_ISSUER") else "PRG32_LIVE_OIDC_ISSUER is not set (no test tenant)"


def cloud_ready() -> str | None:
    if os.environ.get("PRG32_LIVE_CLOUD") not in ("google", "onedrive"):
        return "PRG32_LIVE_CLOUD is not set to google or onedrive (no test account)"
    return None


def qemu_ready() -> str | None:
    return None if shutil.which("idf.py") else "ESP-IDF is not set up (run . $HOME/esp-idf/export.sh first)"


# name: (tests, environment the tests need, check that says why it cannot run)
SUITES = {
    "store": (["tests/test_store_live.py", "tests/test_sso_live.py"], {"PRG32_LIVE_STORE": "local"}, store_ready),
    "oidc-keycloak": (["tests/test_identity_live.py"], {"PRG32_LIVE_OIDC": "keycloak"}, docker_ready),
    "oidc-external": (["tests/test_identity_live.py"], {"PRG32_LIVE_OIDC": "external"}, external_oidc_ready),
    "cloud": (["tests/test_cloud_live.py"], {}, cloud_ready),
    "qemu": (["tests/test_audio_conformance.py::test_live_qemu_audio_does_not_drift"], {"PRG32_LIVE_QEMU": "1"},
             qemu_ready),
}


def secrets_in(environment: dict[str, str]) -> list[str]:
    """The values to keep out of every log: settings whose names say they are secret."""
    return [value for name, value in environment.items()
            if name.startswith("PRG32_") and any(word in name for word in SECRET_WORDS) and len(value) >= 4]


def redact(text: str, secrets: list[str]) -> str:
    """Secret values out, and nothing about this computer: its name and the home folder."""
    for value in sorted(secrets, key=len, reverse=True):
        text = text.replace(value, "<redacted>")
    text = re.sub(r'hostname="[^"]*"', 'hostname="redacted-host"', text)
    return text.replace(str(Path.home()), "~")


def counts(junit: Path) -> dict[str, int]:
    if not junit.is_file():
        return {}
    root = ElementTree.parse(junit).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    total, failed = int(suite.get("tests", 0)), int(suite.get("failures", 0)) + int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))
    return {"passed": total - failed - skipped, "failed": failed, "skipped": skipped}


def run_suite(name: str, out: Path, secrets: list[str]) -> dict:
    tests, environment, check = SUITES[name]
    why_not = check()
    if why_not:
        return {"outcome": "not run", "reason": why_not}
    junit = out / f"{name}.xml"
    command = [sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", f"--junitxml={junit}", *tests]
    result = subprocess.run(command, cwd=ROOT, env={**os.environ, **environment}, capture_output=True, text=True)
    (out / f"{name}.log").write_text(redact(result.stdout + result.stderr, secrets))
    if junit.is_file():
        junit.write_text(redact(junit.read_text(), secrets))
    found = counts(junit)
    if result.returncode == 0 and found.get("passed", 0) > 0 and not found.get("skipped"):
        outcome = "passed"
    elif result.returncode == 0:
        outcome = "not run"          # everything skipped: the service was not really there
    else:
        outcome = "failed"
    return {"outcome": outcome, "tests": tests, **found}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only", help="comma-separated suites, e.g. store,oidc-keycloak (default: all)")
    args = parser.parse_args(argv)
    names = args.only.split(",") if args.only else list(SUITES)
    unknown = [name for name in names if name not in SUITES]
    if unknown:
        parser.error("unknown suite: " + ", ".join(unknown))
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    secrets = secrets_in(dict(os.environ))
    revision = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    summary = {"started": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "kit_revision": revision,
               "settings_present": sorted(name for name in os.environ if name.startswith("PRG32_LIVE")),
               "suites": {}}
    for name in names:
        summary["suites"][name] = run_suite(name, out, secrets)
        item = summary["suites"][name]
        detail = item.get("reason") or f"{item.get('passed', 0)} passed, {item.get('failed', 0)} failed"
        print(f"  {item['outcome']:8} {name}: {detail}")
    summary["finished"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return 1 if any(item["outcome"] == "failed" for item in summary["suites"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
