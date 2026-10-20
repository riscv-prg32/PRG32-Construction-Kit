"""Cloud storage in a real browser (ADR-0019), with a fake Google Drive behind the kit.

- The Account page shows Cloud storage only when the kit offers it; Connect stays
  disabled until the consent box is ticked; the provider's page is stood in for by a
  redirect back to the kit with a code.
- The dashboard's cloud button saves a project; when the cloud copy and the project
  both changed, the dialog offers the choices instead of overwriting, and each choice
  does what it says. No CSP violations.
"""

from __future__ import annotations

import threading
import time
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import make_app
from fake_cloud import FakeCloud
from test_browser_offline import Recorder, browser, sign_in, wait_until  # noqa: F401 - fixtures

from prg32_construction_kit import cloud_storage


@pytest.fixture(scope="module")
def cloud_kit(tmp_path_factory):
    from werkzeug.serving import make_server

    patch = pytest.MonkeyPatch()
    fake = FakeCloud("google", time.time)
    patch.setattr(cloud_storage, "transport", fake)
    patch.setattr(cloud_storage, "sleep", lambda _seconds: None)
    app = make_app(tmp_path_factory.mktemp("cloud-kit"), CLOUD_GOOGLE_CLIENT_ID="kit-google-client")
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield {"url": f"http://127.0.0.1:{server.server_port}", "fake": fake, "app": app}
    server.shutdown()
    patch.undo()


def stand_in_for_google(context, kit_url):
    """Google's consent page: the student agrees, Google sends the browser back with a code."""
    def agree(route):
        query = parse_qs(urlsplit(route.request.url).query)
        assert query["code_challenge_method"] == ["S256"]
        route.fulfill(status=302, headers={"Location": f"{kit_url}/cloud/google/callback?state={query['state'][0]}"
                                                       "&code=good-code"})
    context.route("https://accounts.google.com/**", agree)


def kit_api(page, path, method="GET", body=None):
    return page.evaluate("([path, method, body]) => Kit.api(path, body ? {method, body} : {method})", [path, method, body])


def test_connect_save_and_resolve_a_conflict(browser, cloud_kit):  # noqa: F811
    url, fake = cloud_kit["url"], cloud_kit["fake"]
    context = browser.new_context()
    record = Recorder(context, url)
    stand_in_for_google(context, url)
    page = record.watch(context.new_page())
    sign_in(page, url)
    page.goto(f"{url}/account")
    page.wait_for_selector("#cloud:not(.d-none) .cloud-connect")
    assert page.is_disabled(".cloud-connect")
    page.check(".cloud-consent")
    page.click(".cloud-connect")
    page.wait_for_url(f"{url}/account#cloud")
    page.wait_for_selector(".cloud-disconnect")
    assert "ada@school.test" in page.inner_text("#cloud")

    project = kit_api(page, "/api/projects", "POST", {"title": "Cloud Racer", "blocks_json": {"n": 1}})
    page.goto(url + "/")
    wait_until(page, "document.body.classList.contains('cloud-ready')")
    page.click(f".cloud-project[data-id='{project['id']}']")
    page.wait_for_selector("#cloudModal.show")
    page.click("#cloudPush")
    wait_until(page, "document.getElementById('cloudStatus').textContent.includes('new cloud file')")
    assert len(fake.live_files()) == 1

    # Somebody changes the cloud copy; the student changes the project here too.
    remote = fake.live_files()[0]
    other = kit_api(page, "/api/projects", "POST", {"title": "From home", "blocks_json": {"n": 9}})
    fake.edit_elsewhere(remote["id"], cloud_kit["app"].test_client().get(f"/api/projects/{other['id']}/archive").data)
    current = kit_api(page, f"/api/projects/{project['id']}")
    kit_api(page, f"/api/projects/{project['id']}", "PUT", {"title": "Cloud Racer 2", "expected_version": current["version"]})
    before = bytes(remote["data"])
    page.click("#cloudPush")
    page.wait_for_selector("#cloudConflict:not(.d-none)")
    assert remote["data"] == before                       # nothing overwritten
    assert page.is_visible("#cloudConflict [data-choice=overwrite]")

    # "Take the cloud version" asks first; "no" changes nothing.
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.click("#cloudConflict [data-choice=take_remote]")
    page.wait_for_timeout(200)
    assert kit_api(page, f"/api/projects/{project['id']}")["title"] == "Cloud Racer 2"
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("#cloudConflict [data-choice=take_remote]")
    wait_until(page, "document.getElementById('cloudStatus').textContent.includes('cloud version')")
    assert kit_api(page, f"/api/projects/{project['id']}")["title"] == "From home"
    history = kit_api(page, f"/api/projects/{project['id']}/revisions")["revisions"]
    assert any(item["title"] == "Cloud Racer 2" for item in history)
    assert record.csp_violations() == []
    context.close()


def test_without_cloud_settings_nothing_cloud_is_shown(browser, cloud_kit, tmp_path_factory):  # noqa: F811
    from werkzeug.serving import make_server

    app = make_app(tmp_path_factory.mktemp("no-cloud-kit"))
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        page = browser.new_page()
        sign_in(page, url)
        page.goto(f"{url}/account")
        page.wait_for_load_state("networkidle")
        assert page.is_hidden("#cloud")
        page.goto(url + "/")
        page.wait_for_load_state("networkidle")
        assert not page.evaluate("document.body.classList.contains('cloud-ready')")
        page.close()
    finally:
        server.shutdown()
