"""The recorded deployments (docs/evidence/deploy/, tools/deploy_evidence.py) say what they prove.

Each record must have passed every check, name a kit commit in this repository's history and
the SDK revision, keep the screenshot whose SHA-256 it records, and call itself what it is:
only a console is a physical device.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RECORDS = sorted((ROOT / "docs" / "evidence" / "deploy").glob("*/record.json"))
REFUSALS = ("refused: no slot named", "refused: the slot holds something else than what was seen",
            "refused: the cartridge file changed after its build", "refused: a stale build",
            "after the refusals the slot is as it was")


def in_history(commit: str) -> bool:
    found = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", commit, "HEAD"], capture_output=True)
    return found.returncode == 0


@pytest.mark.parametrize("record_path", RECORDS, ids=[path.parent.name for path in RECORDS])
def test_the_recorded_deployments_passed_and_name_what_they_prove(record_path):
    record = json.loads(record_path.read_text())
    assert record["tool"] == "tools/deploy_evidence.py" and record["passed"] is True
    assert all(check["ok"] for check in record["checks"])
    assert set(REFUSALS) <= {check["check"] for check in record["checks"]}
    assert record["deployment"]["status"] == "launched"
    assert record["deployment"]["result"]["cartridge"]["sha256"] == record["cartridge"]["sha256"]
    assert record["physical_device"] is (record["target_kind"] == "prg32")
    assert record["evidence"] == {"prg32": "physical device", "prg32qt": "emulator (PRG32-QT)",
                                  "qemu": "emulator (QEMU)"}[record["target_kind"]]
    picture = (record_path.parent / "screenshot.png").read_bytes()
    assert hashlib.sha256(picture).hexdigest() == record["screenshot_sha256"]
    if (ROOT / ".git").exists():
        assert in_history(record["kit_commit"]), record["kit_commit"]
    assert len(record["prg32_sdk_commit"]) == 40


def test_there_are_records_for_both_emulators_and_none_claims_a_console():
    kinds = {json.loads(path.read_text())["target_kind"] for path in RECORDS}
    assert {"qemu", "prg32qt"} <= kinds
    # A console record would be physical-device evidence (DEP-01): only from a real console.
    for path in RECORDS:
        record = json.loads(path.read_text())
        if record["target_kind"] == "prg32":
            assert "stand-in" not in record["notes"].lower() and record["target"]["identity"]["host"] != "qt"


def test_the_qemu_record_used_the_firmware_folder_it_describes():
    folder = ROOT / "docs" / "evidence" / "deploy" / "2026-10-24-qemu"
    firmware = json.loads((folder / "prg32-firmware.json").read_text())
    record = json.loads((folder / "record.json").read_text())
    assert record["target"]["identity"]["sdk_commit"] == firmware["sdk_commit"] == record["prg32_sdk_commit"]
    assert record["target"]["abi"]["hash"] == firmware["abi"]["hash"]
