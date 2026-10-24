"""What every page carries: the footer with the privacy links, the storage note, and the
AudioStudio menu item with its project picker."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTICES = json.loads((ROOT / "prg32_construction_kit" / "privacy_notices.json").read_text())["notices"]
STORAGE = next(item for item in NOTICES if item["id"] == "storage")


def test_every_page_links_to_privacy_and_the_storage_list(client):
    html = client.get("/").get_data(as_text=True)
    assert 'href="/privacy"' in html and 'href="/privacy#storage"' in html
    assert 'href="/audio-studio"' in html


def test_the_storage_note_shows_the_current_notice_and_needs_no_consent(client):
    html = client.get("/").get_data(as_text=True)
    assert f'data-version="{STORAGE["version"]}"' in html
    assert STORAGE["summary"] in html
    # Informational only: needed storage, no tracking, so nothing to accept or reject.
    assert "storageNoticeOk" in html and "Reject" not in html
    script = (ROOT / "static" / "js" / "storage_notice.js").read_text()
    assert "fetch(" not in script and "Kit.api" not in script


def test_the_offline_page_note_matches_the_notice(anon):
    html = anon.get("/static/offline.html").get_data(as_text=True)
    assert f'data-version="{STORAGE["version"]}"' in html and STORAGE["summary"] in html


def test_the_privacy_page_lists_every_storage_key_the_scripts_use(anon):
    html = anon.get("/privacy").get_data(as_text=True)
    assert 'id="storage"' in html
    # Lines that touch browser storage, or name a storage key constant.
    lines = [line for path in (ROOT / "static" / "js").rglob("*.js") for line in path.read_text().splitlines()
             if re.search(r"localStorage|indexedDB|key\b|Key\b|KEY|DB_NAME", line)]
    keys = set(re.findall(r"""['"](prg32-[a-z-]+?)-?[:'"]""", "\n".join(lines)))
    keys.discard("prg32-offline-scratchpad")   # legacy key: read once, then removed
    assert keys, "no storage keys found"
    for key in keys:
        assert key in html, f"{key} is used by a script but not listed on /privacy#storage"


def test_audio_studio_menu_opens_a_project_picker(client):
    page = client.get("/audio-studio")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'id="audioProjects"' in html and "audio_studio_pick.js" in html


def test_no_page_shows_html_tags_as_text(client, anon):
    """HTML (a privacy note, a link) goes beside a translated message, never into its values,
    which are escaped: the guest banner once showed  <p class=...>  as text."""
    for browser, path in ((anon, "/"), (anon, "/ide/guest-abc"), (anon, "/player"), (anon, "/privacy"),
                          (client, "/"), (client, "/privacy"), (client, "/account")):
        html = browser.get(path).get_data(as_text=True)
        assert not re.search(r"&lt;/?(p|a|i|span|strong|div)\b", html), path
    guest = anon.get("/").get_data(as_text=True)
    assert 'data-privacy-notice="guest"' in guest and '<a href="/privacy#guest">' in guest
