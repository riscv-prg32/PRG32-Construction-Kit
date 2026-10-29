"""Check that the documentation still matches the product (DOC-02).

    python3 tools/check_docs.py          # exit 1 and list every problem

The checks:

- **links:** every relative link and image in README.md and docs/ points at a file that exists;
  kit routes (/privacy, /docs/...) must exist too;
- **alt text:** every image has a description (Markdown alt text or an HTML alt), and every SVG
  diagram in docs/figures/ has a <title> and a <desc>;
- **visual manifest:** every picture in the repository (except vendored libraries) is listed
  in docs/figures/manifest.json, with its purpose, recipe, viewport, browser, theme, locale,
  seed, product commit, capture date, reviewer and review date (not before the capture); no
  entry points at a missing file;
- **orphans:** every picture is used somewhere, except release evidence;
- **freshness:** a picture is stale when the files it shows (its "watch" paths) differ now from
  the commit it shows, unless a person acknowledged that change ("acknowledged": a later commit,
  with a reviewer and a date). Evidence is frozen. Generated diagrams say how their freshness
  is checked instead (tools/build_diagrams.py --check, in CI);
- **obsolete names:** settings (PRG32_...) and API routes (/api/...) named in the docs exist in
  the code; ABI versions in the docs are the kit's, unless the line is about a proposal;
- **ID drift:** ADR-00NN names an existing ADR; capability IDs exist in docs/capabilities.json;
  README.md tags agree with the capability record (as tests/test_doc_consistency.py does for docs/).

The briefs (docs/briefs/) and the auditor's files (audit/) are inputs from others and are
not checked. Release records (evidence, handoff, upstream, release notes) describe the past
and are not checked for obsolete names.
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DOCS = ROOT / "docs"
MANIFEST = DOCS / "figures" / "manifest.json"
VISUAL = (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".bmp")
REQUIRED = ("purpose", "kind", "recipe", "viewport", "browser", "theme", "locale", "seed", "product_commit",
            "captured", "reviewed", "reviewer")
HISTORY = ("evidence", "handoff", "upstream", "briefs")      # records of the past, not current instructions
LINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_IMG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
SETTING = re.compile(r"\bPRG32_[A-Z0-9_]*[A-Z0-9]\b")
ROUTE = re.compile(r"`(?:(?:GET|POST|PUT|PATCH|DELETE) )?(/api/[A-Za-z0-9_./<>{}:-]*)")
ABI = re.compile(r"\bABI (\d+)\.(\d+)\b")
CAPABILITY = re.compile(r"\b(?:IDE|PRJ|BLD|WASM|AUD|DBG|ACC|SSO|CLD|STR|DEP|SEC|GDPR|OPS|DOC|QLT|I18N|PY|EVAL)-\d{2}\b")
ADR = re.compile(r"\bADR-(\d{4})\b")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout.strip()


def documents() -> list[Path]:
    paths = [ROOT / "README.md"] + sorted(DOCS.rglob("*.md"))
    return [path for path in paths if "briefs" not in path.relative_to(ROOT).parts]


def current_documents() -> list[Path]:
    return [path for path in documents() if not set(path.relative_to(ROOT).parts) & set(HISTORY)
            and path.name != "release-notes.md"]


def tracked_visuals() -> list[str]:
    return [path for path in git("ls-files").splitlines()
            if path.lower().endswith(VISUAL) and not path.startswith(("static/vendor/", ".claude/"))]


def check_links() -> list[str]:
    problems = []
    for path in documents():
        text = path.read_text(encoding="utf-8")
        for bang, alt, target in LINK.findall(text):
            target = target.split("#", 1)[0]
            if not target or re.match(r"^[a-z]+:", target):
                continue                                   # an anchor, a URL or mailto:
            if target.startswith("/"):
                ok = (ROOT / target.lstrip("/")).exists() if target.startswith(("/docs/", "/static/")) else \
                    target.rstrip("/") in KIT_PAGES
            else:
                ok = (path.parent / target).exists()
            if not ok:
                problems.append(f"{path.relative_to(ROOT)}: broken link {target}")
            if bang and not alt.strip():
                problems.append(f"{path.relative_to(ROOT)}: image {target} has no alt text")
        for tag in HTML_IMG.findall(text):
            if not re.search(r'\balt="[^"]+"', tag):
                problems.append(f"{path.relative_to(ROOT)}: <img> without alt text: {tag[:80]}")
    return problems


KIT_PAGES = {"/privacy", "/account", "/documentation", "/ide", "/player", "/publish", "/classes", "/sprites",
             "/artifacts", "/auth/login", "/auth/register", "/admin/users", "/admin/identity"}


def check_svgs() -> list[str]:
    problems = []
    for path in sorted((DOCS / "figures").rglob("*.svg")):
        text = path.read_text(encoding="utf-8")
        if "<title" not in text:
            problems.append(f"{path.relative_to(ROOT)}: no <title> (the accessible name)")
        if path.parent == DOCS / "figures" and "<desc" not in text:
            problems.append(f"{path.relative_to(ROOT)}: no <desc> (the text equivalent of the diagram)")
    return problems


def used_somewhere(visual: str) -> bool:
    name = Path(visual).name
    for folder in ("README.md", "docs", "templates", "static", "prg32_construction_kit", "tools"):
        hits = git("grep", "-l", "-F", name, "--", folder)
        if any(hit != visual for hit in hits.splitlines()):
            return True
    return False


def ancestor(commit: str) -> bool:
    return subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", commit, "HEAD"]).returncode == 0


def check_manifest() -> list[str]:
    problems = []
    manifest = json.loads(MANIFEST.read_text())["visuals"]
    visuals = tracked_visuals()
    for visual in visuals:
        if visual not in manifest:
            problems.append(f"{visual}: not in docs/figures/manifest.json")
    for visual, entry in manifest.items():
        if not (ROOT / visual).is_file():
            problems.append(f"manifest: {visual} does not exist")
            continue
        for key in REQUIRED:
            if not entry.get(key):
                problems.append(f"manifest: {visual} has no {key}")
        try:
            if entry.get("reviewed") and entry["reviewed"] < entry["captured"]:
                problems.append(f"manifest: {visual} was reviewed ({entry['reviewed']}) before it was captured "
                                f"({entry['captured']})")
            datetime.date.fromisoformat(entry.get("captured") or "")
        except (TypeError, ValueError):
            problems.append(f"manifest: {visual} has no valid capture date")
        commit = entry.get("product_commit") or ""
        if commit and not ancestor(commit):
            problems.append(f"manifest: {visual} names commit {commit[:12]}, which is not in this history")
            continue
        if entry.get("kind") != "evidence" and visual in visuals and not used_somewhere(visual):
            problems.append(f"{visual}: not used by any document or page (an orphan)")
        if entry.get("kind") == "diagram" and "build_diagrams.py" in entry.get("recipe", "") and not entry.get("freshness"):
            problems.append(f"manifest: {visual} is generated: say how its freshness is checked (freshness)")
        if entry.get("frozen") or not entry.get("watch") or not commit:
            continue
        acknowledged = entry.get("acknowledged") or {}
        base = acknowledged.get("commit") if acknowledged.get("commit") and ancestor(acknowledged["commit"]) else commit
        # Against the working tree, so a change not yet committed counts too.
        changed = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", base, "--", *entry["watch"]]).returncode
        if changed:
            problems.append(f"{visual}: stale: {', '.join(entry['watch'])} changed since {base[:12]}; capture it again "
                            f"({entry['recipe']}) or acknowledge the change in the manifest")
    return problems


def code_text() -> str:
    parts = []
    for folder in ("prg32_construction_kit", "tools", "docker", "examples", "wasm", ".github", "static/js", "tests"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and path.suffix in (".py", ".js", ".mjs", ".sh", ".yml", ".yaml", ".env", ".cmake",
                                                  ".txt", ".cpp", ".c", ".h", ".json", ".service", ".conf"):
                parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    for name in ("app.py", "Dockerfile", "docker-compose.yml"):
        if (ROOT / name).is_file():
            parts.append((ROOT / name).read_text(encoding="utf-8"))
    return "\n".join(parts)


def app_routes() -> list[re.Pattern]:
    import tempfile

    from prg32_construction_kit import create_app

    with tempfile.TemporaryDirectory() as folder:
        data = Path(folder)
        app = create_app({"TESTING": True, "DATA_DIR": data, "DB_PATH": data / "kit.sqlite", "BUILD_ROOT": data / "b",
                          "ARTIFACT_ROOT": data / "a", "ADMIN_PASSWORD": "check-docs-admin-1", "SSO_SECRET": "",
                          "SSO_PEER_URL": ""})
        rules = [rule.rule for rule in app.url_map.iter_rules()]
    patterns = []
    for rule in rules:
        regex = re.sub(r"<[^>]+>", "[^/]+", re.escape(rule).replace(r"\<", "<").replace(r"\>", ">"))
        patterns.append(re.compile("^" + regex + "/?$"))
    return patterns


# Named in the docs but not read by the kit, on purpose.
DOC_ONLY_SETTINGS = {"PRG32_DB_PASSWORD": "a variable of the operator's own compose file (docs/docker.md)"}


def throttle_setting(name: str) -> bool:
    """PRG32_KIT_THROTTLE_<limit> is read through its prefix (config._throttle_overrides)."""
    from prg32_construction_kit.security import LIMITS

    return name.startswith("PRG32_KIT_THROTTLE_") and name.removeprefix("PRG32_KIT_THROTTLE_").lower() in LIMITS


def check_names() -> list[str]:
    from prg32_construction_kit.project_format import SDK_ABI

    problems = []
    code = code_text()
    routes = app_routes()
    for path in current_documents():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            where = f"{path.relative_to(ROOT)}:{number}"
            for setting in set(SETTING.findall(line)):
                if setting in DOC_ONLY_SETTINGS or throttle_setting(setting):
                    continue
                if setting not in code:
                    problems.append(f"{where}: setting {setting} is not used anywhere in the code")
            for route in ROUTE.findall(line):
                route = route.rstrip(".,:;")
                route = re.sub(r"\{[^}]+\}|<[^>]+>|\.\.\.", "x", route.split("?", 1)[0])
                if route.endswith("/") or "*" in route:
                    continue
                if not any(pattern.match(route) for pattern in routes):
                    problems.append(f"{where}: route {route} does not exist")
            for major, minor in ABI.findall(line):
                if (int(major), int(minor)) != (SDK_ABI["major"], SDK_ABI["minor"]) and not re.search(
                        r"patch|propos|upstream|retire|old|legacy|compatib|before", line, re.IGNORECASE):
                    problems.append(f"{where}: ABI {major}.{minor} is not the kit's ABI "
                                    f"{SDK_ABI['major']}.{SDK_ABI['minor']}")
    return problems


def check_ids() -> list[str]:
    problems = []
    capabilities = {item["id"]: item["status"] for item in
                    json.loads((DOCS / "capabilities.json").read_text())["capabilities"]}
    adrs = {path.name[:4] for path in (DOCS / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")}
    for path in documents():
        text = path.read_text(encoding="utf-8")
        for number in set(ADR.findall(text)):
            if number not in adrs:
                problems.append(f"{path.relative_to(ROOT)}: ADR-{number} does not exist")
        if path.name in ("capabilities.md",) or "audit" in path.parts:
            continue
        for capability in set(CAPABILITY.findall(text)):
            if capability not in capabilities:
                problems.append(f"{path.relative_to(ROOT)}: unknown capability {capability}")
    readme = (ROOT / "README.md").read_text()
    for line in readme.splitlines():
        for capability in re.findall(r"\[([A-Z]{2,5}-\d{2})\]", line):
            status = capabilities.get(capability)
            if status in ("implemented", "reference-verified") and re.search(r"\b(not yet|missing|not implemented)\b", line, re.I):
                problems.append(f"README.md calls [{capability}] missing, but it is {status}")
            if status in ("partial", "prototype", "missing") and re.search(r"\b(complete|fully|done)\b", line, re.I):
                problems.append(f"README.md calls [{capability}] complete, but it is {status}")
    return problems


CHECKS = {"links": check_links, "svg": check_svgs, "manifest": check_manifest, "names": check_names, "ids": check_ids}


def main() -> int:
    problems = []
    for name, check in CHECKS.items():
        found = check()
        print(f"{'ok  ' if not found else 'FAIL'}  {name}: {len(found)} problem(s)")
        problems += found
    for problem in problems:
        print("  " + problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
