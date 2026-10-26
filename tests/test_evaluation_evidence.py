"""The recorded evaluations (docs/evidence/evaluate/, tools/evaluation_evidence.py) are what they say.

Each record passed, names a kit commit in this history and the SDK revision, and lists the
SHA-256 of every file next to it. Its charts and CSV are made again from its dataset, byte for
byte, with today's code. The comparison holds only datasets with the same cartridge. Emulator
records say they are emulator records.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from prg32_construction_kit import evaluation

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "docs" / "evidence" / "evaluate"
RECORDS = sorted(FOLDER.glob("*/record.json"))


@pytest.mark.parametrize("record_path", RECORDS, ids=[path.parent.name for path in RECORDS])
def test_the_recorded_evaluations_passed_and_their_files_are_the_listed_ones(record_path):
    record = json.loads(record_path.read_text())
    assert record["tool"] == "tools/evaluation_evidence.py" and record["passed"] is True
    assert all(check["ok"] for check in record["checks"])
    for name, digest in record["files"].items():
        assert hashlib.sha256((record_path.parent / name).read_bytes()).hexdigest() == digest, name
    assert record["physical_device"] is (record["target_kind"] == "prg32")
    if record["target_kind"] != "prg32":
        assert record["evidence"].startswith("emulator") and record["host"]
    if (ROOT / ".git").exists():
        found = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", record["kit_commit"], "HEAD"])
        assert found.returncode == 0, record["kit_commit"]


@pytest.mark.parametrize("record_path", RECORDS, ids=[path.parent.name for path in RECORDS])
def test_the_charts_and_csv_are_made_again_from_the_dataset(record_path):
    folder = record_path.parent
    dataset = json.loads((folder / "dataset.json").read_text())
    record = json.loads(record_path.read_text())
    assert dataset["about"]["cartridge_sha256"] == record["cartridge_sha256"]
    assert dataset["about"]["evidence"] == record["evidence"]
    measured = [row for row in dataset["rows"] if row["role"] == "measured"]
    assert len(measured) == record["repetitions"] * 5 * len(evaluation.protocol()["metrics"])
    assert (folder / "dataset.csv").read_bytes() == evaluation.csv_of([dataset])
    for metric in evaluation.protocol()["metrics"]:
        for kind in ("svg", "pdf"):
            assert (folder / f"{metric['name']}.{kind}").read_bytes() == evaluation.chart_bytes([dataset], metric["name"], kind), \
                (metric["name"], kind)


def test_the_comparison_holds_one_cartridge_on_several_targets():
    comparisons = sorted(FOLDER.glob("*-comparison/comparison.json"))
    assert comparisons
    for path in comparisons:
        document = json.loads(path.read_text())
        assert document["left_out"] == [] and len(document["compared"]) >= 2
        assert len({item["cartridge_sha256"] for item in document["compared"]}) == 1
        assert len({item["target_kind"] for item in document["compared"]}) == len(document["compared"])
        datasets = [json.loads((ROOT / source / "dataset.json").read_text()) for source in document["sources"]]
        assert (path.parent / "frame_us_mean.svg").read_bytes() == evaluation.chart_bytes(datasets, "frame_us_mean", "svg")
