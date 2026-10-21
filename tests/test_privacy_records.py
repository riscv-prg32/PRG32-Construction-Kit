"""The privacy records stay true to the code (docs/privacy/, ADR-0022).

- the record of processing (ropa.json) names every column of every table exactly once, and
  every item has purpose, legal basis, access, recipients, location, retention, deletion,
  transfers and a review owner; ropa.md is rendered from it;
- the privacy folder's documents exist and link where they say;
- while a release-blocking decision is open, nothing claims the GDPR gate passes;
- the breach rehearsal record is complete and its evidence matches its hash.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIVACY = ROOT / "docs" / "privacy"
REQUIRED = ("data", "subjects", "purpose", "legal_basis", "special_categories", "access", "recipients", "location",
            "retention", "deletion", "transfers", "review_owner", "next_review")


def test_the_record_of_processing_names_every_column_once(app):
    from prg32_construction_kit.db import db

    ropa = json.loads((PRIVACY / "ropa.json").read_text())
    named: list[tuple[str, str]] = []
    for item in ropa["items"]:
        for key in REQUIRED:
            assert key in item and (item[key] or key == "subjects"), (item["id"], key)
        for table, columns in item["fields"].items():
            named += [(table, column) for column in columns]
    with app.app_context():
        actual = {(table, column.name) for table, model in db.metadata.tables.items() for column in model.columns}
    assert len(named) == len(set(named)), "a column is named twice"
    assert set(named) == actual, {"missing": sorted(actual - set(named)), "unknown": sorted(set(named) - actual)}
    for store in ("session_cookie", "browser_storage", "build_folders", "artifact_files", "backups", "server_logs"):
        assert store in {item["id"] for item in ropa["other_stores"]}


def test_the_readable_record_is_rendered_from_the_json():
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "render_ropa.py"), "--check"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_the_privacy_folder_is_complete_and_its_links_work():
    readme = (PRIVACY / "README.md").read_text()
    for name in ("ropa.md", "roles_and_legal_bases.md", "retention.md", "processors_and_transfers.md",
                 "children_dpia_dpo.md", "rights_requests.md", "notices.md", "security_article32.md",
                 "breach_playbook.md", "decisions.md", "CHANGELOG.md"):
        assert (PRIVACY / name).is_file() and f"({name})" in readme, name
    for path in PRIVACY.rglob("*.md"):
        for target in re.findall(r"\]\(([^)#:]+)(?:#[^)]*)?\)", path.read_text()):
            if target.startswith("/"):
                continue                                   # a kit route such as /privacy
            assert (path.parent / target).exists(), f"{path.relative_to(ROOT)} -> {target}"


def open_blockers() -> list[str]:
    rows = [line for line in (PRIVACY / "decisions.md").read_text().splitlines() if line.startswith("| D-")]
    open_rows = []
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        decision_id, blocker, status = cells[0], cells[4], cells[5]
        if blocker.startswith("yes") and status.startswith("open"):
            open_rows.append(decision_id)
    return open_rows


def test_nothing_claims_the_gdpr_gate_while_a_blocker_is_open():
    blockers = open_blockers()
    capability = {item["id"]: item for item in json.loads((ROOT / "docs" / "capabilities.json").read_text())["capabilities"]}
    gdpr = capability["GDPR-01"]
    if blockers:
        assert gdpr["status"] != "implemented", f"GDPR-01 cannot be implemented while {blockers} are open"
        assert "NO-GO" in (PRIVACY / "README.md").read_text() and "NO-GO" in (PRIVACY / "decisions.md").read_text()
        for line in (ROOT / "docs" / "release-notes.md").read_text().lower().splitlines():
            assert "gdpr compliant" not in line and "gdpr-compliant" not in line, line


def test_the_breach_rehearsal_record_is_complete():
    folder = PRIVACY / "exercises" / "2026-10-21-breach-rehearsal"
    record = json.loads((folder / "timeline.json").read_text())
    steps = [item["step"] for item in record["timeline"]]
    assert steps == ["setup", "incident", "T0 detection", "containment", "evidence", "assessment"]
    assert record["deadline_72h"] > record["t0"] and "not a staffed exercise" in record["exercise"]
    evidence = next(item for item in record["timeline"] if item["step"] == "evidence")
    assert hashlib.sha256((folder / evidence["file"]).read_bytes()).hexdigest() == evidence["sha256"]
    containment = next(item for item in record["timeline"] if item["step"] == "containment")
    assert containment["token_after"] == 401 and containment["attacker_session_after"] == 401
    incident = next(item for item in record["timeline"] if item["step"] == "incident")
    assert incident["other_pupils_reachable"] is False
    for field in ("people", "children", "data", "risk", "notify_authority", "tell_the_person"):
        assert record["assessment"][field] not in (None, ""), field
    text = (folder / "audit-extract.json").read_text()
    assert "@rehearsal.test" in text or "s03" in text            # synthetic people only
    assert not re.search(r"@(?!rehearsal\.test)[a-z0-9-]+\.[a-z]{2,}", text)
