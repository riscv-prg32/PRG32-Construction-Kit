"""docs/capabilities.json: every claimed capability points at real code and real tests."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "docs" / "capabilities.json").read_text())
CLAIMED = ("implemented", "reference-verified")
sys.path.insert(0, str(ROOT / "tools"))


def symbol_exists(reference: str) -> bool:
    """``path`` (the file exists) or ``path::name`` (name is defined in that file)."""
    path_text, _, name = reference.partition("::")
    path = ROOT / path_text
    if not path.is_file():
        return False
    if not name:
        return True
    text = path.read_text(encoding="utf-8", errors="replace")
    patterns = {
        ".py": [rf"^\s*(?:async\s+)?def {re.escape(name)}\b", rf"^\s*class {re.escape(name)}\b",
                rf"^{re.escape(name)}\s*[:=]"],
        ".js": [rf"\bfunction {re.escape(name)}\b", rf"\bclass {re.escape(name)}\b", rf"^\s+{re.escape(name)}\([^)]*\)\s*\{{",
                rf"\b{re.escape(name)}\s*="],
        ".cpp": [rf"\b{re.escape(name)}\s*\("],
        ".c": [rf"\b{re.escape(name)}\s*\("],
    }
    return any(re.search(pattern, text, re.MULTILINE) for pattern in patterns.get(path.suffix, []))


def _test_is_defined(reference: str) -> bool:
    path_text, _, name = reference.partition("::")
    path = ROOT / path_text
    return path.is_file() and bool(re.search(rf"^def {re.escape(name)}\(", path.read_text(), re.MULTILINE))


def test_statuses_and_ids_are_valid():
    ids = [row["id"] for row in DATA["capabilities"]]
    assert len(ids) == len(set(ids))
    assert all(row["status"] in DATA["statuses"] for row in DATA["capabilities"])


@pytest.mark.parametrize("row", [row for row in DATA["capabilities"] if row["status"] in CLAIMED],
                         ids=lambda row: row["id"])
def test_implemented_rows_name_existing_source_and_tests(row):
    assert row["tests"], f"{row['id']} claims {row['status']} without a test"
    if row["id"] != "DBG-06":  # a pure comparison requirement: its evidence is the differential tests
        assert row["source"], f"{row['id']} claims {row['status']} without a source symbol"
    for reference in row["source"]:
        assert symbol_exists(reference), f"{row['id']}: {reference} not found"
    for reference in row["tests"]:
        assert _test_is_defined(reference), f"{row['id']}: {reference} not found"


@pytest.mark.parametrize("row", DATA["capabilities"], ids=lambda row: row["id"])
def test_every_listed_reference_exists(row):
    for reference in row["source"]:
        assert symbol_exists(reference), reference
    for reference in row["tests"]:
        assert _test_is_defined(reference), reference


def test_audit_scores_are_the_auditors():
    matrix = (ROOT / "audit" / "REQUIREMENTS_MATRIX.md").read_text()
    for row in DATA["capabilities"]:
        found = re.search(rf"^\| {re.escape(row['id'])} \| (\d) \|", matrix, re.MULTILINE)
        assert found and int(found.group(1)) == row["audit_score"], row["id"]


def test_reference_verified_needs_a_reference_comparison_test():
    for row in DATA["capabilities"]:
        if row["status"] == "reference-verified":
            assert any("native" in test or "prg32qt" in test for test in row["tests"]), row["id"]


def test_rendered_table_is_up_to_date():
    from render_capabilities import TARGET, render

    assert TARGET.read_text() == render(DATA), "run python3 tools/render_capabilities.py"
