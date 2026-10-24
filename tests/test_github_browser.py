"""The IDE's Git tool window in a real browser, against the in-process GitHub (ADR-0025).

GitHub's own sign-in page is not part of the kit, so the student's connection is made directly
in the database (as the callback would make it); everything after that goes through the page.
"""

from __future__ import annotations

import json
import threading

import pytest
from conftest import make_app
from fake_github import APP_CLIENT, FakeGitHub
from test_auth import STUDENT_PASSWORD, make_student
from test_browser_offline import browser, wait_until  # noqa: F401 - fixtures

from prg32_construction_kit import cloud_storage
from prg32_construction_kit.sample_data import starter_project


@pytest.fixture(scope="module")
def github_kit(tmp_path_factory):
    from werkzeug.serving import make_server

    fake = FakeGitHub(cloud_storage.now_seconds)
    original = cloud_storage.transport
    cloud_storage.transport = fake
    app = make_app(tmp_path_factory.mktemp("github-kit"), CLOUD_GITHUB_CLIENT_ID=APP_CLIENT,
                   CLOUD_GITHUB_CLIENT_SECRET="test-only", CLOUD_GITHUB_APP_SLUG="prg32-kit")
    make_student(app.test_client(), "ada")
    with app.app_context():
        from prg32_construction_kit.auth import User
        from prg32_construction_kit.db import db

        user = db.session.query(User).filter_by(username="ada").one()
        token = "ghu_browser"
        fake.tokens[token] = cloud_storage.now_seconds() + 28800
        db.session.add(cloud_storage.CloudAccount(
            user_id=user.id, provider="github", account_id="4242", account_name="ada-codes",
            tokens=cloud_storage.seal({"access_token": token, "refresh_token": "", "expires_at":
                                       cloud_storage.now_seconds() + 28800, "scope": ""}),
            options=json.dumps({"repository": "ada/games", "branch": "main"})))
        db.session.commit()
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", fake
    server.shutdown()
    cloud_storage.transport = original


def test_commit_and_push_from_the_ide(browser, github_kit):  # noqa: F811
    base, fake = github_kit
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.goto(f"{base}/auth/login")
    page.fill("input[name=username]", "ada")
    page.fill("input[name=password]", STUDENT_PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_url(f"{base}/")
    start = starter_project("c", "Git Game")
    project = page.evaluate("body => Kit.api('/api/projects', {method: 'POST', body}).then(p => p.id)",
                            {"title": "Git Game", **start})
    page.goto(f"{base}/ide/{project}")
    wait_until(page, "document.getElementById('ide').dataset.ready === 'true'", timeout=30)
    page.click("#panelTab-git")
    wait_until(page, "!!document.getElementById('gitMessage')")
    assert "ada/games" in page.inner_text("#ideGit")
    page.fill("#gitMessage", "First version")
    page.click("#gitCommitForm button[type=submit]")
    wait_until(page, "document.querySelectorAll('#gitHistory code').length === 1", timeout=15)
    assert "First version" in page.inner_text("#gitHistory")
    folder = f"git-game-{project}"
    assert fake.folder_files("ada/games", folder)["src/game.c"] == start["game_json"]["source_c"].encode()
    # Changed on GitHub and here: the student is asked, and can keep both.
    fake.commit_files("ada/games", "main", {f"{folder}/README.md": b"notes"}, "from home")
    page.evaluate("PRG32Ide.editors.src.setValue(PRG32Ide.editors.src.getValue() + '\\n/* here */\\n')")
    page.fill("#gitMessage", "Second version")
    page.click("#gitCommitForm button[type=submit]")
    wait_until(page, "!document.getElementById('gitConflict').hidden", timeout=15)
    assert page.is_visible("#gitConflict [data-choice=overwrite]")
    context.close()
