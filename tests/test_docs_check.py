"""tools/check_docs.py (DOC-02): the documentation passes, and each check catches what it is for."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import check_docs  # noqa: E402


@pytest.mark.parametrize("name", sorted(check_docs.CHECKS))
def test_the_documentation_passes(name):
    assert check_docs.CHECKS[name]() == []


def test_the_diagrams_and_the_record_of_processing_are_regenerated():
    for tool in ("build_diagrams.py", "render_ropa.py"):
        result = subprocess.run([sys.executable, str(ROOT / "tools" / tool), "--check"], capture_output=True, text=True)
        assert result.returncode == 0, (tool, result.stderr)


def planted(tmp_path, monkeypatch, text: str) -> Path:
    page = tmp_path / "planted.md"
    page.write_text(text)
    (tmp_path / "README.md").write_text("# planted\n")
    monkeypatch.setattr(check_docs, "documents", lambda: [page])
    monkeypatch.setattr(check_docs, "current_documents", lambda: [page])
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    return page


def test_broken_links_and_missing_alt_text_are_found(tmp_path, monkeypatch):
    planted(tmp_path, monkeypatch, "[gone](nowhere.md) ![](figures/x.png) <img src=\"y.png\"> [page](/no-such-page)")
    found = "\n".join(check_docs.check_links())
    assert "broken link nowhere.md" in found and "no alt text" in found and "<img> without alt" in found
    assert "broken link /no-such-page" in found


def test_obsolete_settings_routes_and_abi_versions_are_found(tmp_path, monkeypatch):
    planted(tmp_path, monkeypatch, "Set `PRG32_NO_SUCH_SETTING`, call `POST /api/no/such/route`, ABI 1.2 here.\n"
                                   "`PRG32_KIT_THROTTLE_LOGIN_USER` and `GET /api/projects/<id>` exist; ABI 1.7 is a proposal.")
    found = "\n".join(check_docs.check_names())
    assert "PRG32_NO_SUCH_SETTING" in found and "/api/no/such/route" in found and "ABI 1.2" in found
    assert "THROTTLE" not in found and "/api/projects/" not in found and "1.7" not in found


def test_unknown_adr_and_capability_ids_are_found(tmp_path, monkeypatch):
    planted(tmp_path, monkeypatch, "See ADR-0999 and capability IDE-99.")
    found = "\n".join(check_docs.check_ids())
    assert "ADR-0999" in found and "IDE-99" in found


def test_a_stale_or_unreviewed_picture_is_found(tmp_path, monkeypatch):
    real = json.loads(check_docs.MANIFEST.read_text())
    first = subprocess.run(["git", "-C", str(ROOT), "rev-list", "--max-parents=0", "HEAD"], capture_output=True,
                           text=True).stdout.split()[0]
    visual = "docs/figures/PRG32-Construction-Kit_01.png"
    entry = dict(real["visuals"][visual], product_commit=first, watch=["README.md"], reviewer=None)
    entry.pop("acknowledged", None)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"visuals": {**real["visuals"], visual: entry,
                                                "docs/figures/missing.png": real["visuals"][visual]}}))
    monkeypatch.setattr(check_docs, "MANIFEST", manifest)
    found = "\n".join(check_docs.check_manifest())
    assert f"{visual}: stale" in found and f"{visual} has no reviewer" in found
    assert "docs/figures/missing.png does not exist" in found
    # A person acknowledging the change (a later commit) makes it current again.
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    entry["acknowledged"] = {"commit": head, "date": "2026-10-21", "reviewer": "test", "note": "README text only"}
    entry["reviewer"] = "test"
    manifest.write_text(json.dumps({"visuals": {**real["visuals"], visual: entry}}))
    assert not [problem for problem in check_docs.check_manifest() if visual in problem]


def test_every_picture_has_an_entry_and_an_svg_without_a_title_is_found(tmp_path, monkeypatch):
    real = json.loads(check_docs.MANIFEST.read_text())["visuals"]
    assert set(check_docs.tracked_visuals()) <= set(real)
    figures = tmp_path / "docs" / "figures"
    figures.mkdir(parents=True)
    (figures / "untitled.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>")
    monkeypatch.setattr(check_docs, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    found = "\n".join(check_docs.check_svgs())
    assert "no <title>" in found and "no <desc>" in found
