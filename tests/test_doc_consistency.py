"""The status documents agree with docs/capabilities.json.

docs/capabilities.json is the one machine-checked record of what is implemented
(tests/test_capabilities.py checks its evidence). Other documents cite it with
tags such as ``[IDE-01]``. These tests fail when a document contradicts it:

- docs/architecture/current-state.md lists every capability exactly once, under
  "Implemented", "Partly implemented" or "Not implemented", matching its status;
- any other ``[ID]`` tag in docs/ names a real capability, and the words just
  before it do not call an implemented capability missing, or a missing one done;
- the commit that current-state.md describes exists, and it is the latest audit's revision with that
  audit's score;
- its claims about the product are derived from the product: the real builds name every authoring
  mode, and the quality gates it names (or says are missing) match the CI workflow;
- no status page says work is "being refreshed" (a status is a state, not a plan);
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
TAG = re.compile(r"\[([A-Z][A-Z0-9]{1,4}-\d{2})\]")
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


WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
NAMES = {"blocks": "Blocks", "c": "C", "assembly": "assembly", "python": "Python"}


def implemented_lines(tag: str) -> str:
    """The bullet of current-state.md that carries ``[tag]`` (joined across its wrapped lines)."""
    bullets = re.split(r"\n(?=- )", CURRENT_STATE.read_text())
    found = [re.sub(r"\s+", " ", bullet) for bullet in bullets if f"[{tag}]" in bullet]
    assert found, f"current-state.md has no bullet for [{tag}]"
    return found[0]


def test_real_builds_name_every_authoring_mode():
    """The audit of 7a700ba found 'real builds from Blocks, C and assembly' after Python was added."""
    from prg32_construction_kit.project_format import AUTHORING_MODES

    bullet = implemented_lines("BLD-01")
    for mode in AUTHORING_MODES:
        assert re.search(rf"\b{re.escape(NAMES[mode])}\b", bullet), f"[BLD-01] bullet does not name {mode}: {bullet}"


def test_quality_gates_match_the_ci_workflow():
    """What current-state.md says about lint, coverage and performance budgets is what CI runs."""
    workflow = WORKFLOW.read_text()
    pyproject = (ROOT / "pyproject.toml").read_text()
    gates = {
        "lint": "ruff check" in workflow,
        "coverage": bool(re.search(r"^fail_under\s*=\s*\d+", pyproject, re.MULTILINE)) and "coverage" in workflow,
        "performance": "tests/test_performance_browser.py" in workflow,
    }
    bullet = implemented_lines("QLT-01")
    denied = re.search(r"\bwithout ([^.;]*)", bullet)
    for gate, in_ci in gates.items():
        if in_ci:
            assert not (denied and gate in denied.group(1)), f"current-state.md says CI has no {gate}: {bullet}"
            assert gate in bullet.lower(), f"CI runs a {gate} gate but [QLT-01] does not name it: {bullet}"
    floor = re.search(r"^fail_under\s*=\s*(\d+)", pyproject, re.MULTILINE)
    if floor:
        assert f"{floor.group(1)}%" in bullet, f"the coverage floor is {floor.group(1)}%: {bullet}"


def test_current_state_names_the_latest_audit_and_its_score():
    """The newest audit is the one whose audited revision is the newest commit (file times mean nothing
    in a fresh checkout)."""
    audits = []
    for path in (ROOT / "audit").glob("AUDIT_*.md"):
        text = path.read_text()
        revision = re.search(r"revision `([0-9a-f]{7,40})`", text).group(1)
        when = subprocess.run(["git", "show", "-s", "--format=%ct", revision], cwd=ROOT, capture_output=True, text=True)
        if when.returncode != 0:
            pytest.skip(f"the audited revision {revision[:7]} is not in this history (shallow clone?)")
        audits.append((int(when.stdout.strip()), revision, text))
    if not audits:
        pytest.skip("no audit report in this checkout")
    _, revision, latest = max(audits)
    score = re.search(r"\*\*(?:NO-GO|GO)[^*]*?(\d+/\d+)", latest).group(1)
    head = CURRENT_STATE.read_text().split("## Repositories", 1)[0]
    assert f"`{revision[:7]}`" in head, f"current-state.md does not name the audited revision {revision[:7]}"
    assert score in head, f"current-state.md does not give the audit's score {score}"


def test_no_status_page_describes_a_plan_as_a_state():
    stale = re.compile(r"\bbeing (?:refreshed|updated|rewritten|reworked)\b", re.IGNORECASE)
    for path in [CURRENT_STATE, DOCS / "capabilities.md"]:
        text = re.sub(r"\s+", " ", path.read_text())
        found = stale.search(text)
        assert not found, f"{path.name}: '{found.group(0)}' is a plan, not a state"
