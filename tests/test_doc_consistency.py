"""The status documents agree with docs/capabilities.json.

docs/capabilities.json is the one machine-checked record of what is implemented
(tests/test_capabilities.py checks its evidence). Other documents cite it with
tags such as ``[IDE-01]``. These tests fail when a document contradicts it:

- docs/architecture/current-state.md lists every capability exactly once, under
  "Implemented", "Partly implemented" or "Not implemented", matching its status;
- any other ``[ID]`` tag in docs/ names a real capability, and the words just
  before it do not call an implemented capability missing, or a missing one done;
- the commit that current-state.md describes exists;
- no document says the pages still load from a CDN (they have not since ADR-0012).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
CURRENT_STATE = DOCS / "architecture" / "current-state.md"
STATUS = {row["id"]: row["status"] for row in json.loads((DOCS / "capabilities.json").read_text())["capabilities"]}
CLAIMED = {"implemented", "reference-verified"}
SECTIONS = {"Implemented": CLAIMED, "Partly implemented": {"partial", "prototype"}, "Not implemented": {"missing"}}
TAG = re.compile(r"\[([A-Z]{2,5}-\d{2})\]")
SAYS_MISSING = re.compile(r"\b(not implemented|missing|absent|not started|not yet|open)\b", re.IGNORECASE)
SAYS_DONE = re.compile(r"(?<!not )\b(done|implemented|complete)\b", re.IGNORECASE)


def status_documents():
    """Every doc that may describe the status: not the briefs (inputs) or the generated table."""
    skip = {DOCS / "capabilities.md"}
    return [path for path in sorted(DOCS.rglob("*.md")) if path not in skip and "briefs" not in path.parts]


def current_state_sections() -> dict[str, list[str]]:
    sections, name = {}, None
    for line in CURRENT_STATE.read_text().splitlines():
        if line.startswith("### "):
            name = line[4:].strip()
            sections.setdefault(name, [])
        elif line.startswith("## "):
            name = None
        elif name in SECTIONS:
            sections[name].extend(TAG.findall(line))
    return sections


def test_current_state_lists_every_capability_once_with_its_status():
    sections = current_state_sections()
    assert set(SECTIONS) <= set(sections), "current-state.md lost one of its status sections"
    placed = {}
    for name, ids in sections.items():
        for capability in set(ids):
            assert capability in STATUS, f"current-state.md cites unknown capability {capability}"
            assert capability not in placed, f"{capability} is under both {placed[capability]!r} and {name!r}"
            placed[capability] = name
            assert STATUS[capability] in SECTIONS[name], (
                f"current-state.md lists {capability} under {name!r}, but capabilities.json says {STATUS[capability]}")
    assert sorted(set(STATUS) - set(placed)) == [], "current-state.md does not mention these capabilities"


def clauses_with_tags(text: str):
    """(words before a tag, tag) for every tag: from the previous tag, ';' or line start."""
    for line in text.splitlines():
        start = 0
        for match in TAG.finditer(line):
            before = line[start:match.start()]
            before = before.rsplit(";", 1)[-1]
            yield line, before, match.group(1)
            start = match.end()


@pytest.mark.parametrize("path", status_documents(), ids=lambda path: str(path.relative_to(DOCS)))
def test_capability_tags_do_not_contradict_the_record(path):
    for line, before, capability in clauses_with_tags(path.read_text()):
        assert capability in STATUS, f"{path.name}: unknown capability [{capability}] in: {line}"
        if STATUS[capability] in CLAIMED:
            assert not SAYS_MISSING.search(before), (
                f"{path.name} calls [{capability}] missing, but it is {STATUS[capability]}: {line}")
        elif STATUS[capability] == "missing":
            assert not SAYS_DONE.search(before), f"{path.name} calls [{capability}] done, but it is missing: {line}"


def test_current_state_names_a_real_commit():
    row = next(line for line in CURRENT_STATE.read_text().splitlines() if line.startswith("| PRG32-Construction-Kit |"))
    commit = re.search(r"`([0-9a-f]{7,40})`", row.split("|")[3]).group(1)
    try:
        shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT, capture_output=True,
                                 text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    if shallow == "true":
        pytest.skip("shallow clone: older commits are not available")
    found = subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=ROOT, capture_output=True)
    assert found.returncode == 0, f"current-state.md describes {commit}, which is not a commit here"


def test_no_document_says_the_pages_load_from_a_cdn():
    stale = re.compile(r"\bload\w*\b[^.]*\bfrom (?:a |the )?CDNs?\b", re.IGNORECASE)
    for path in status_documents() + [ROOT / "README.md"]:
        text = re.sub(r"\s+", " ", path.read_text())  # sentences wrap across lines
        found = stale.search(text)
        assert not found, f"{path.name} still says pages load from a CDN: {found.group(0)}"


def test_every_refinement_phase_commit_is_a_listed_milestone():
    """The milestone table names each "Refinement phase" commit by its hash, and no row says "this change"."""
    try:
        shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT, capture_output=True,
                                 text=True, check=True).stdout.strip()
        log = subprocess.run(["git", "log", "--format=%h %H %s"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    if shallow == "true":
        pytest.skip("shallow clone: the history is not available")
    text = CURRENT_STATE.read_text()
    table = text.split("## Milestones", 1)[1].split("\n## ", 1)[0]
    for line in log:
        short, _full, subject = line.split(" ", 2)
        if not subject.startswith("Refinement phase"):
            continue
        listed = re.search(rf"`{short[:7]}[0-9a-f]*`", table)
        assert listed, f"milestone {short} ({subject}) is missing from current-state.md"
    assert not re.search(r"this (?:change|commit)", table, re.IGNORECASE), "a milestone row must name its commit"
