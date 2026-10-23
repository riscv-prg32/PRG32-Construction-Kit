#!/usr/bin/env python3
"""Write docs/capabilities.md from docs/capabilities.json (the machine-checkable status table).

    python3 tools/render_capabilities.py          # rewrite the Markdown table
    python3 tools/render_capabilities.py --check  # exit 1 if it is out of date

tests/test_capabilities.py checks that every "implemented" or
"reference-verified" row names source symbols and tests that really exist.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "capabilities.json"
TARGET = ROOT / "docs" / "capabilities.md"


def _refs(items: list[str]) -> str:
    return "<br>".join(f"`{item}`" for item in items) or "—"


def render(data: dict) -> str:
    lines = [
        "# Capabilities",
        "",
        "Generated from `capabilities.json` by `tools/render_capabilities.py`; do not edit by hand.",
        "**Status** is the project's own assessment and must cite existing source symbols and tests",
        "(`tests/test_capabilities.py`). **Audit** is the independent auditor's score (0-4) copied from",
        "`audit/REQUIREMENTS_MATRIX.md`; only the auditor changes it (— : not scored yet).",
        "",
        "| ID | Capability | Status | Audit | Source | Tests | Note |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in data["capabilities"]:
        score = "—" if row["audit_score"] is None else row["audit_score"]
        lines.append(f"| {row['id']} | {row['title']} | {row['status']} | {score} | "
                     f"{_refs(row['source'])} | {_refs(row['tests'])} | {row['note'] or ''} |")
    counts = {status: sum(1 for row in data["capabilities"] if row["status"] == status) for status in data["statuses"]}
    lines += ["", "Totals: " + ", ".join(f"{status} {count}" for status, count in counts.items() if count) + ".", ""]
    return "\n".join(lines)


def main() -> int:
    text = render(json.loads(SOURCE.read_text(encoding="utf-8")))
    if "--check" in sys.argv:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        print("docs/capabilities.md is up to date" if current == text else "docs/capabilities.md is out of date")
        return 0 if current == text else 1
    TARGET.write_text(text, encoding="utf-8")
    print(f"Wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
