"""The top menu works on the open project (base.html): in the IDE and in /player?project=<id> the
PRG32 logo closes the project, and Editor, Sprite Lab, AudioStudio and Player open that project.
The menu bar always shows the kit's name. On the Projects page no project is open, and each card has the same
four tools for its project (dashboard.js)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def new_project(client, title="Menu Game"):
    response = client.post("/api/projects", json={"title": title})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def brand(html: str) -> str:
    return re.search(r'<a class="navbar-brand.*?</a>', html, re.S).group(0)


def project_menu_links(html: str, project_id: str) -> None:
    assert f'href="/ide/{project_id}" data-ide-tool="editor"' in html
    assert f'href="/ide/{project_id}#sprites" data-ide-tool="sprites"' in html
    assert f'href="/ide/{project_id}#sound" data-ide-tool="sound"' in html
    assert f'href="/player?project={project_id}" data-ide-tool="player"' in html
    # The pickers and the empty player are not offered while a project is open.
    assert 'href="/sprites"' not in html and 'href="/audio-studio"' not in html and 'href="/player"' not in html


def test_the_projects_page_has_no_open_project(client):
    html = client.get("/").get_data(as_text=True)
    assert "navCloseProject" not in html and "data-ide-tool" not in html
    assert "PRG32 Construction Kit" in brand(html) and "img/prg32-logo.png" in brand(html)
    assert 'href="/sprites"' in html and 'href="/audio-studio"' in html and 'href="/player"' in html
    # The same tools, not tied to a project, beside New Project in the welcome banner.
    hero = re.search(r'<div class="d-flex flex-wrap gap-2 mt-2" id="heroTools">.*?</div>', html, re.S).group(0)
    assert re.findall(r'href="([^"]+)"', hero) == ["/sprites", "/audio-studio", "/backgrounds", "/player"]


def test_the_ide_menu_works_on_its_project(client):
    project = new_project(client)
    html = client.get(f"/ide/{project['id']}").get_data(as_text=True)
    top = brand(html)
    assert 'href="/"' in top and 'id="navCloseProject"' in top          # the logo closes the project
    assert "PRG32 Construction Kit" in top and "Menu Game" not in top     # the kit's name, always
    assert f'data-project-id="{project["id"]}"' in top
    project_menu_links(html, project["id"])


def test_the_player_menu_works_on_its_project(client):
    project = new_project(client, "Player Game")
    html = client.get(f"/player?project={project['id']}").get_data(as_text=True)
    assert 'id="navCloseProject"' in brand(html)
    project_menu_links(html, project["id"])


def test_the_player_without_a_project_keeps_the_kit_menu(client):
    for address in ("/player", "/player?project=", "/player?project=../../etc", "/player?project=" + "x" * 65):
        html = client.get(address).get_data(as_text=True)
        assert "navCloseProject" not in html, address
        assert "PRG32 Construction Kit" in brand(html), address


def test_the_menu_bar_never_shows_a_project_name(app, client, anon):
    """The kit's name, always: the project's name is in the IDE's toolbar, for its owner."""
    project = new_project(client, "Admin Secret Title")
    made = client.post("/api/users", json={"username": "menu-kid", "email": "menu-kid@school.test",
                                           "password": "menu-kid-password-1", "role": "user"})
    assert made.status_code == 201, made.get_json()
    other = app.test_client(login=("menu-kid", "menu-kid-password-1"))
    for browser, address in ((client, f"/ide/{project['id']}"), (other, f"/ide/{project['id']}"),
                             (anon, "/ide/guest-abc")):
        top = brand(browser.get(address).get_data(as_text=True))
        assert "Admin Secret Title" not in top and "PRG32 Construction Kit" in top


def test_the_player_finds_the_projects_newest_cartridge(app, client):
    from prg32_construction_kit.db import Artifact, db

    project = new_project(client)
    old = client.post("/api/artifacts", json={"project_id": project["id"], "kind": "prg32_cartridge",
                                              "name": "old.prg32"}).get_json()
    with app.app_context():   # compiled a while ago (times are kept to the second)
        db.session.get(Artifact, old["id"]).updated_at = "2026-01-01T00:00:00+00:00"
        db.session.commit()
    client.post("/api/artifacts", json={"project_id": project["id"], "kind": "prg32_cartridge", "name": "new.prg32"})
    client.post("/api/artifacts", json={"project_id": project["id"], "kind": "c_source", "name": "game.c"})
    listed = client.get(f"/api/artifacts?project_id={project['id']}&kind=prg32_cartridge").get_json()["artifacts"]
    assert [artifact["name"] for artifact in listed] == ["new.prg32", "old.prg32"]
    script = (ROOT / "static" / "js" / "player.js").read_text()
    assert "'&kind=prg32_cartridge'" in script and "(data.artifacts || [])[0]" in script


def test_each_project_card_opens_the_tools_for_its_project():
    script = (ROOT / "static" / "js" / "dashboard.js").read_text()
    assert "href=\"${ide}#sprites\"" in script and "href=\"${ide}#sound\"" in script
    assert "href=\"/player?project=${encodeURIComponent(project.id)}\"" in script
