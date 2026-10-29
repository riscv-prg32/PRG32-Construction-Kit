"""Publishing to a real Cartridge Store (opt-in; contracts/prg32-store-contract-1.json).

Off unless ``PRG32_LIVE_STORE=local``. It then starts the CartridgeStore from the checkout
next to the kit (or PRG32_CARTRIDGE_STORE_SOURCE) as a separate process on
127.0.0.1:5160, with a temporary data folder and a test admin password: a throwaway
Store, never a production one. Nothing here can reach any other Store: the kit's egress
allow-list contains only that address.

What it proves, with real HTTP between the kit and the Store:
- a publish arrives as a pending submission, invisible in the catalogue until an editor
  verifies it (visibility);
- a new version is an update; the same id/version is recorded as the Store behaves today
  (contract versioning.duplicate_identity_version);
- a manifest the contract refuses is never uploaded, and the Store refuses it too;
- a revoked Store token is refused (401 -> unauthorized, not retryable), with no submission;
- the Store going away mid-way is a retryable failure with no submission, and the retry
  after it comes back publishes exactly once (partial-failure recovery).
"""

from __future__ import annotations

import io
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest
import requests

from prg32_construction_kit import store_contract

pytestmark = pytest.mark.skipif(os.environ.get("PRG32_LIVE_STORE") != "local",
                                reason="live Store tests are opt-in: set PRG32_LIVE_STORE=local")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from pinned_store import store_source  # noqa: E402  (tools/pinned_store.py)

STORE_SOURCE = store_source()
PORT = 5160
STORE = f"http://127.0.0.1:{PORT}"
STORE_ADMIN = ("admin", "store-admin-test-only")      # the throwaway Store's first admin
FIXTURES = ROOT / "tests" / "fixtures" / "contract"


class LiveStore:
    """A CartridgeStore process with its own temporary data; stop() and start() keep the data."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.process = None
        self.secret_key = secrets.token_hex(16)      # same across restarts, new every run
        self.log = data_dir / "store.log"

    def start(self):
        env = {**os.environ, "PRG32_STORE_DATA": str(self.data_dir), "PRG32_STORE_DB": str(self.data_dir / "store.sqlite"),
               "PRG32_ADMIN_PASSWORD": STORE_ADMIN[1], "SECRET_KEY": self.secret_key, "PYTHONPATH": str(STORE_SOURCE)}
        code = ("from cartridge_store import create_app; "
                f"create_app().run(host='127.0.0.1', port={PORT}, debug=False, use_reloader=False)")
        self.process = subprocess.Popen([sys.executable, "-c", code], env=env, cwd=STORE_SOURCE,
                                        stdout=subprocess.DEVNULL, stderr=self.log.open("a"))
        for _ in range(100):
            try:
                if requests.get(STORE + "/api/games", timeout=1).status_code < 500:
                    return
            except requests.RequestException:
                time.sleep(0.2)
        raise AssertionError("the Cartridge Store did not start: " + self.log.read_text()[-800:])

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=10)
            self.process = None
        for _ in range(50):
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", PORT)) != 0:
                    return
            time.sleep(0.1)


def form_token(page: str) -> dict[str, str]:
    """The Store's CSRF token, from the page's <meta name="csrf-token"> (its forms add it the same way).
    Stores before 4a3138b have none, and need none."""
    found = re.search(r'<meta name="csrf-token" content="([^"]+)"', page)
    return {"csrf_token": found.group(1)} if found else {}


def acknowledge_notice(session: requests.Session, base: str, answer: requests.Response) -> None:
    """An account seeing the Store's privacy notice for the first time acknowledges it, as a person would."""
    if "/auth/privacy-acknowledge" not in answer.headers.get("Location", ""):
        return
    page = session.get(base + "/auth/privacy-acknowledge", timeout=10).text
    version = re.search(r'name="privacy_notice_version" value="([^"]+)"', page)
    assert version, page[:400]
    done = session.post(base + "/auth/privacy-acknowledge", data={"privacy_notice_version": version.group(1),
                        "next": "/", **form_token(page)}, allow_redirects=False, timeout=10)
    assert done.status_code == 302, done.text[:300]


def store_sign_in(session: requests.Session, base: str, username: str, password: str) -> None:
    """Sign in on the Store's own form, as a browser does: CSRF token, then the notice if it is new."""
    token = form_token(session.get(base + "/auth/login", timeout=10).text)
    signed_in = session.post(base + "/auth/login", data={"username": username, "password": password, **token},
                             allow_redirects=False, timeout=10)
    assert signed_in.status_code in (200, 302), signed_in.text[:300]
    acknowledge_notice(session, base, signed_in)


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    if not (STORE_SOURCE / "cartridge_store" / "app.py").is_file():
        pytest.fail(f"PRG32_LIVE_STORE=local needs a CartridgeStore checkout at {STORE_SOURCE}", pytrace=False)
    live = LiveStore(tmp_path_factory.mktemp("live-store"))
    live.start()
    editor = requests.Session()
    try:
        store_sign_in(editor, STORE, *STORE_ADMIN)
    except BaseException:
        live.stop()                      # never leave a throwaway Store on the port
        raise
    live.editor = editor
    yield live
    live.stop()


def store_token(store) -> dict:
    answer = store.editor.post(STORE + "/auth/tokens", json={"label": "kit live test"}, timeout=10).json()
    return {"id": answer.get("id"), "token": answer.get("token")}


def submissions(store, status="all") -> list[dict]:
    return store.editor.get(STORE + "/api/submissions", params={"status": status}, timeout=10).json()["submissions"]


def catalogue(store) -> list[dict]:
    answer = requests.get(STORE + "/api/games", timeout=10).json()
    return answer.get("games", answer if isinstance(answer, list) else [])


@pytest.fixture()
def kit(app, client, store):
    app.config["STORE_ALLOWED_ORIGINS"] = [STORE]      # nothing else can be reached
    app.config["STORE_TRUSTED_LOCAL"] = True
    token = store_token(store)
    profile = client.post("/api/publish_profiles", json={"name": "Throwaway Store", "store_url": STORE,
                                                         "bearer_token": token["token"]}).get_json()
    return {"app": app, "client": client, "profile": profile, "token": token}


def bundle_artifact(kit, data: bytes, name: str) -> dict:
    from prg32_construction_kit.db import create_resource

    path = Path(kit["app"].config["BUILD_ROOT"]) / "live" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    with kit["app"].app_context():
        return create_resource("artifacts", {"kind": "store_bundle", "name": name, "path": str(path), "owner_id": 1,
                                             "metadata": {"publishable": True}})


def with_version(version: str) -> bytes:
    """The valid fixture bundle with another manifest version."""
    source = zipfile.ZipFile(io.BytesIO((FIXTURES / "valid.zip").read_bytes()))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "manifest.json":
                manifest = json.loads(data)
                manifest["version"] = version
                data = json.dumps(manifest, indent=2, sort_keys=True).encode()
            target.writestr(info, data)
    return out.getvalue()


def publish(kit, artifact) -> tuple[int, dict]:
    client = kit["client"]
    review = client.post("/api/publish/review", json={"profile_id": kit["profile"]["id"],
                                                      "bundle_artifact_id": artifact["id"]})
    if review.status_code != 200:
        return review.status_code, review.get_json()
    body = review.get_json()
    answer = client.post("/api/publish", json={"profile_id": kit["profile"]["id"], "bundle_artifact_id": artifact["id"],
                                               "review_token": body["review_token"], "confirm": True})
    return answer.status_code, answer.get_json()


def test_a_publish_is_pending_until_verified_and_a_new_version_updates(kit, store):
    before = len(submissions(store))
    status, answer = publish(kit, bundle_artifact(kit, with_version("0.1.10"), "v10.zip"))
    assert status == 200 and answer["result"]["ok"] is True, answer
    pending = [item for item in submissions(store, "pending") if item["version"] == "0.1.10"]
    assert len(submissions(store)) == before + 1 and len(pending) == 1
    assert not [game for game in catalogue(store) if game.get("version") == "0.1.10"]     # not public yet
    verified = store.editor.post(f"{STORE}/api/submissions/{pending[0]['id']}/verify", json={}, timeout=10)
    assert verified.status_code == 200, verified.text[:300]
    listed = [game for game in catalogue(store) if game.get("id") == "org.prg32kit.pong"]
    assert listed, catalogue(store)
    status, answer = publish(kit, bundle_artifact(kit, with_version("0.1.11"), "v11.zip"))
    assert status == 200 and answer["result"]["ok"] is True
    assert [item["version"] for item in submissions(store, "pending")][-1:] == ["0.1.11"]


def test_duplicate_identity_and_version_behaves_as_the_contract_records(kit, store):
    artifact = bundle_artifact(kit, with_version("0.1.20"), "v20.zip")
    assert publish(kit, artifact)[1]["result"]["ok"] is True
    # The kit never sends the same bundle twice: a repeat answers with the first result.
    count = len(submissions(store))
    status, answer = publish(kit, artifact)
    assert status == 200 and answer["duplicate"] is True and len(submissions(store)) == count
    # Another bundle with the same id/version: the same files answer with the first result,
    # other files are refused by the kit (contract versioning.kit_duplicate_rule).
    same_files = publish(kit, bundle_artifact(kit, with_version("0.1.20"), "v20-again.zip"))
    assert same_files[1]["duplicate"] is True and len(submissions(store)) == count
    changed = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(with_version("0.1.20"))) as source, zipfile.ZipFile(changed, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            target.writestr(info, data + b"\n" if info.filename.endswith(".json") else data)
    other = changed.getvalue()
    status, answer = publish(kit, bundle_artifact(kit, other, "v20-other.zip"))
    assert status == 409 and answer["reason"] == "version_already_published" and len(submissions(store)) == count
    # Sent straight to the Store, a second bundle with the same id/version is ...
    direct = requests.post(STORE + "/api/publish/bundle", timeout=20,
                           headers={"Authorization": "Bearer " + kit["token"]["token"]},
                           files={"bundle": ("again.zip", with_version("0.1.20"), "application/zip")})
    recorded = store_contract.contract()["versioning"]["duplicate_identity_version"]
    observed = "store_accepts_duplicate_pending" if direct.status_code == 200 else "store_refuses_duplicate"
    assert observed == recorded, "the Store changed: update the contract's versioning section"


def test_a_contract_violation_is_never_uploaded_and_the_store_refuses_it_too(kit, store):
    before = len(submissions(store))
    bad = (FIXTURES / "unsafe-version.zip").read_bytes()
    status, answer = publish(kit, bundle_artifact(kit, bad, "bad.zip"))
    assert status == 400 and answer["reason"] == "contract_unsafe_id_or_version"
    assert len(submissions(store)) == before
    direct = requests.post(STORE + "/api/publish/bundle", timeout=20,
                           headers={"Authorization": "Bearer " + kit["token"]["token"]},
                           files={"bundle": ("bad.zip", bad, "application/zip")})
    assert direct.status_code == 400
    assert store_contract.classify(400, direct.json().get("error", ""))["code"] == "unsafe_id_or_version"


def test_a_revoked_store_token_is_refused_with_nothing_published(kit, store):
    before = len(submissions(store))
    token = form_token(store.editor.get(STORE + "/", timeout=10).text)       # the token manager sends it as a header
    revoked = store.editor.delete(f"{STORE}/auth/tokens/{kit['token']['id']}",
                                  headers={"X-CSRF-Token": token.get("csrf_token", "")}, timeout=10)
    assert revoked.status_code in (200, 204), revoked.text[:200]
    status, answer = publish(kit, bundle_artifact(kit, with_version("0.1.30"), "v30.zip"))
    result = answer.get("result", answer)
    assert result.get("ok") is not True
    assert result.get("error_code") == "unauthorized" and result.get("retryable") is False, answer
    assert len(submissions(store)) == before


def test_the_store_going_away_is_retryable_and_the_retry_publishes_once(kit, store):
    artifact = bundle_artifact(kit, with_version("0.1.40"), "v40.zip")
    before = len(submissions(store))
    store.stop()
    try:
        status, answer = publish(kit, artifact)
    finally:
        store.start()
        store_sign_in(store.editor, STORE, *STORE_ADMIN)
    assert answer.get("result", answer).get("ok") is not True
    assert len(submissions(store)) == before                       # nothing half-published
    status, answer = publish(kit, artifact)                        # the same bundle, once the Store is back
    assert status == 200 and answer["result"]["ok"] is True, answer
    assert [item["version"] for item in submissions(store)].count("0.1.40") == 1


def test_store_tokens_have_no_expiry_today(store):
    """Recorded, not wished for: CartridgeStore 820f74b API tokens do not expire (contract known gap)."""
    answer = store.editor.get(STORE + "/auth/tokens", timeout=10).json()
    tokens = answer.get("tokens", [])
    assert tokens and all("expires_at" not in token for token in tokens)
    assert store_contract.contract()["tokens"]["expiry"] == "none", "the Store changed: update the contract's tokens"
