"""Cloud storage against a real Google Drive or OneDrive test account (opt-in; ADR-0019).

Off unless ``PRG32_LIVE_CLOUD=google`` or ``onedrive``. Then, from the environment only
(never from files in the repository):

    PRG32_LIVE_CLOUD_CLIENT_ID       the test app registration
    PRG32_LIVE_CLOUD_CLIENT_SECRET   (if the registration has one)
    PRG32_LIVE_CLOUD_TENANT          OneDrive only (default: common)
    PRG32_LIVE_CLOUD_REFRESH_TOKEN   from connecting a TEST account once by hand
    PRG32_LIVE_CLOUD_REVOKE=1        also revoke the token at the end (Google; the
                                     refresh token stops working)

It only touches files it creates (``prg32-live-test-<random>...``) and moves them to the
trash at the end. Outages cannot be caused on purpose against a real provider: they are
covered by tests/test_cloud_storage.py. docs/cloud_storage.md says how to get the refresh
token.
"""

from __future__ import annotations

import hashlib
import os
import secrets

import pytest
from conftest import make_app

from prg32_construction_kit import cloud_storage
from prg32_construction_kit.cloud_storage import Api, CloudAccount, CloudError, RemoteChanged

PROVIDER = os.environ.get("PRG32_LIVE_CLOUD", "")
pytestmark = pytest.mark.skipif(PROVIDER not in ("google", "onedrive"),
                                reason="live cloud tests are opt-in: set PRG32_LIVE_CLOUD=google|onedrive")


@pytest.fixture(scope="module")
def live(tmp_path_factory):
    needed = ["PRG32_LIVE_CLOUD_CLIENT_ID", "PRG32_LIVE_CLOUD_REFRESH_TOKEN"]
    missing = [name for name in needed if not os.environ.get(name)]
    if missing:
        pytest.fail("PRG32_LIVE_CLOUD is set but these are missing: " + ", ".join(missing), pytrace=False)
    prefix = "GOOGLE" if PROVIDER == "google" else "ONEDRIVE"
    app = make_app(tmp_path_factory.mktemp("cloud-live"), **{
        f"CLOUD_{prefix}_CLIENT_ID": os.environ["PRG32_LIVE_CLOUD_CLIENT_ID"],
        f"CLOUD_{prefix}_CLIENT_SECRET": os.environ.get("PRG32_LIVE_CLOUD_CLIENT_SECRET", ""),
        "CLOUD_ONEDRIVE_TENANT": os.environ.get("PRG32_LIVE_CLOUD_TENANT", "common")})
    with app.app_context(), app.test_request_context():
        item = cloud_storage.configured()[PROVIDER]
        # expires_at 0: the first call must refresh, which is itself a test of expiry.
        account = CloudAccount(user_id=1, provider=PROVIDER, account_id="", tokens=cloud_storage.seal(
            {"access_token": "expired", "refresh_token": os.environ["PRG32_LIVE_CLOUD_REFRESH_TOKEN"], "expires_at": 0}))
        api = Api(item, account)
        api._refresh = _refresh_without_saving(api)
        made: list[str] = []
        yield {"item": item, "api": api, "made": made, "name": f"prg32-live-test-{secrets.token_hex(4)}"}
        for file_id in made:
            remote = item.metadata(api, file_id)
            if remote is not None:
                item.delete(api, file_id, remote.revision)
        if os.environ.get("PRG32_LIVE_CLOUD_REVOKE") == "1":
            assert item.revoke(api.tokens) is item.revokes_at_provider


def _refresh_without_saving(api):
    """Refresh as the kit does, but keep the tokens in memory only (there is no account row)."""
    def refresh():
        fresh = cloud_storage._token_request(api.item, {"grant_type": "refresh_token",
                                                        "refresh_token": api.tokens["refresh_token"]})
        fresh["refresh_token"] = fresh["refresh_token"] or api.tokens["refresh_token"]
        api.tokens = fresh
    return refresh


def archive(text: str) -> bytes:
    from prg32_construction_kit import project_format

    return project_format.export_archive({"id": "live", "title": text, "description": "", "author": "test",
                                          "tags": [], "blocks_json": {"text": text}, "game_json": {}}, [], [])


def test_an_expired_token_is_refreshed_and_the_account_is_known(live):
    account_id, name = live["item"].account(live["api"])
    assert account_id and live["api"].tokens["access_token"] != "expired"


def test_only_the_least_privilege_scopes_were_granted(live):
    granted = set(str(live["api"].tokens.get("scope", "")).split())
    if PROVIDER == "google":
        assert "https://www.googleapis.com/auth/drive.file" in granted
        assert not granted & {"https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/drive.readonly"}
    else:
        lowered = {scope.lower().rsplit("/", 1)[-1] for scope in granted}
        assert {"files.readwrite.appfolder", "user.read"} <= lowered
        assert not lowered & {"files.readwrite", "files.readwrite.all", "files.read.all", "sites.readwrite.all"}


def test_a_revoked_or_unknown_refresh_token_is_refused_without_changes(live):
    """A refresh token the provider does not know: 'connect again', and no request reaches a file."""
    with pytest.raises(CloudError) as refused:
        cloud_storage._token_request(live["item"], {"grant_type": "refresh_token",
                                                    "refresh_token": "prg32-live-test-not-a-real-token"})
    assert refused.value.code in ("reconnect", "unavailable")


def test_the_onedrive_simple_upload_limit_is_enforced_before_sending(live):
    if PROVIDER != "onedrive":
        pytest.skip("OneDrive only")
    too_big = b"0" * (live["item"].max_upload + 1)
    with pytest.raises(CloudError) as refused:
        live["item"].create(live["api"], live["name"] + "-big.prg32project.zip", too_big, "live-big", "x")
    assert refused.value.code == "too_large"
    assert live["name"] + "-big" not in " ".join(entry.name for entry in live["item"].list(live["api"]))


def test_create_list_load_save_and_trash(live):
    item, api = live["item"], live["api"]
    data = archive("one")
    name = live["name"] + ".prg32project.zip"
    remote = item.create(api, name, data, "live-project", hashlib.sha256(data).hexdigest())
    live["made"].append(remote.file_id)
    listed = item.list(api)
    assert remote.file_id in [entry.file_id for entry in listed]
    assert all(entry.name.endswith(".prg32project.zip") for entry in listed)   # only kit project files
    loaded, content = item.load(api, remote.file_id)
    assert content == data
    newer = archive("two")
    saved = item.save(api, remote.file_id, newer, hashlib.sha256(newer).hexdigest(), loaded.revision)
    assert saved.revision != loaded.revision and item.load(api, remote.file_id)[1] == newer
    assert item.find(api, name, "live-project", hashlib.sha256(newer).hexdigest()).file_id == remote.file_id


def test_a_save_from_an_old_revision_is_refused(live):
    """Concurrent edits: the second writer, still holding the first revision, is refused."""
    item, api = live["item"], live["api"]
    data = archive("base")
    remote = item.create(api, live["name"] + "-race.prg32project.zip", data, "live-race", hashlib.sha256(data).hexdigest())
    live["made"].append(remote.file_id)
    first = archive("first writer")
    item.save(api, remote.file_id, first, hashlib.sha256(first).hexdigest(), remote.revision)
    with pytest.raises(RemoteChanged):
        item.save(api, remote.file_id, archive("second writer"), "x", remote.revision)
    # On Drive this refusal comes from the kit's check before writing (no conditional upload):
    # a change in the moment between that check and the write would still be replaced (ADR-0019).
    assert item.load(api, remote.file_id)[1] == first


def test_the_kit_cannot_reach_files_it_did_not_make(live):
    """Least privilege: an id the kit did not create is not found (drive.file / app folder)."""
    with pytest.raises(CloudError):
        live["item"].load(live["api"], "a-file-the-kit-never-made")
