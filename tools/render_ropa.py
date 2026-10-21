"""Render docs/privacy/ropa.json as docs/privacy/ropa.md (the readable record of processing).

    python3 tools/render_ropa.py           # write ropa.md
    python3 tools/render_ropa.py --check   # exit 1 if ropa.md is not what ropa.json says

ropa.json is the source: tests/test_privacy_records.py checks that it names every
column of every table exactly once, and that ropa.md is rendered from it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "privacy" / "ropa.json"
TARGET = ROOT / "docs" / "privacy" / "ropa.md"
ROWS = (("Data", "data"), ("People", "subjects"), ("Purpose", "purpose"), ("Legal basis", "legal_basis"),
        ("Special categories", "special_categories"), ("Who can see it", "access"), ("Recipients", "recipients"),
        ("Where", "location"), ("Kept for", "retention"), ("Deleted by", "deletion"), ("Transfers", "transfers"),
        ("Review owner", "review_owner"), ("Next review", "next_review"))


def cell(value) -> str:
    if isinstance(value, list):
        value = ", ".join(value) or "none"
    return str(value).replace("|", "\\|").replace("\n", " ")


def render(document: dict) -> str:
    lines = [f"# {document['title']}", "",
             "<!-- Generated from ropa.json by tools/render_ropa.py: edit the JSON, then run the tool. -->", "",
             f"Version {document['version']}, reviewed {document['reviewed']}. Owner: {document['owner']}.", "",
             f"**Status:** {document['status']}.", "", f"**Controller:** {document['controller']}.", "",
             "Each item lists the database columns it covers (field level). Legal bases marked PROPOSED are",
             "not decisions: see [decisions.md](decisions.md).", ""]
    for item in document["items"]:
        lines += [f"## {item['id']}", "", "| | |", "|---|---|"]
        for label, key in ROWS:
            lines.append(f"| {label} | {cell(item[key])} |")
        fields = "; ".join(f"`{table}`: {', '.join(columns)}" for table, columns in item["fields"].items())
        lines += [f"| Fields | {cell(fields)} |", ""]
    lines += ["## Outside the database", "", "| Store | Data | Where | Kept for | Deleted by | Personal |",
              "|---|---|---|---|---|---|"]
    for store in document["other_stores"]:
        lines.append(f"| {store['id']} | {cell(store['data'])} | {cell(store['where'])} | {cell(store['retention'])} | "
                     f"{cell(store['deletion'])} | {'yes' if store['personal'] else 'no'} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    text = render(json.loads(SOURCE.read_text(encoding="utf-8")))
    if "--check" in sys.argv[1:]:
        if TARGET.read_text(encoding="utf-8") != text:
            print("docs/privacy/ropa.md is out of date: run python3 tools/render_ropa.py", file=sys.stderr)
            return 1
        print("ropa.md is up to date")
        return 0
    TARGET.write_text(text, encoding="utf-8")
    print(f"Wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
