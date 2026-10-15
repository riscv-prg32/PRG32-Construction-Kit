"""The game tutorials and their slide decks stay in step with the example games."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

pytest.importorskip("markdown")

ROOT = Path(__file__).resolve().parent.parent
TUTORIALS = ROOT / "docs" / "tutorials" / "games"
GAMES = ["pong", "breakout", "space_invaders", "asteroids", "snake"]


def load_builder():
    spec = importlib.util.spec_from_file_location("build_presentations", ROOT / "tools" / "build_presentations.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tutorials_and_decks_are_up_to_date():
    assert load_builder().main(check=True) == 0, "run python3 tools/build_presentations.py"


@pytest.mark.parametrize("game", GAMES)
def test_each_game_has_a_complete_tutorial(game):
    text = (TUTORIALS / f"{game}.md").read_text(encoding="utf-8")
    slides = [part for part in re.split(r"\n---\n", text) if part.strip()]
    assert len(slides) >= 15
    assert text.count("<!-- blocks:") >= 6, "step-by-step block excerpts"
    assert "<!-- c:" in text
    for image in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text):
        assert (TUTORIALS / image).resolve().is_file(), image
    for runtime in ("qemu", "prg32qt"):
        assert f"{game}-{runtime}.png" in text
    deck = (ROOT / "docs" / "presentations" / f"{game}.html").read_text(encoding="utf-8")
    assert deck.count('<section class="slide') == len(slides) - 1  # front matter is not a slide
    assert 'class="blk-label"' in deck


def test_readme_links_every_deck():
    readme = (TUTORIALS / "README.md").read_text(encoding="utf-8")
    for game in GAMES:
        assert f"({game}.md)" in readme and f"presentations/{game}.html" in readme
