"""Publishing needs the publisher role and a confirmed, unchanged review (ADR-0009, audit H-02).

No test publishes to a real Store: the upload function is replaced, or the
Store is a local test server.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from types import SimpleNamespace

import pytest

from prg32_construction_kit import publishing
from prg32_construction_kit.auth import create_user
from prg32_construction_kit.sample_data import default_blocks

PASSWORD = "student-password-1"
STORE = "https://store.school.test"
CARTRIDGE = b"PRG2" + b"\x01\x00" * 40


def fake_builder(command, **_kwargs):
    with open(command[command.index("--out") + 1], "wb") as cartridge:
        cartridge.write(CARTRIDGE)
    return SimpleNamespace(returncode=0, stdout="", stderr="")


@pytest.fixture()
def setup(app, client, monkeypatch):
    """An approved Store, a publisher account and a real (fake-compiled) Store bundle."""
    app.config["STORE_ALLOWED_ORIGINS"] = [STORE]
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder)
    monkeypatch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: True)
    sent = []

    def upload(store_url, token, path):
        sent.append({"store_url": store_url, "token": token, "bytes": path.read_bytes()})
        return {"ok": True, "status_code": 200, "store_host": "store.school.test", "message": "received",
                "response": {"ok": True, "status": "pending", "submission_id": len(sent)}}

    monkeypatch.setattr("prg32_construction_kit.routes.publish_bundle", upload)
    with app.app_context():
        create_user("pia", "pia@school.test", PASSWORD, role="publisher")
        create_user("ugo", "ugo@school.test", PASSWORD, role="user")
    pia = app.test_client(login=("pia", PASSWORD))
    project = pia.post("/api/projects", json={"title": "Pub Game", "blocks_json": default_blocks()}).get_json()
    built = pia.post(f"/api/projects/{project['id']}/package", json={}).get_json()
    profile = pia.post("/api/publish_profiles", json={"name": "School", "store_url": STORE,
                                                      "bearer_token": "prg32_token_secret_1"}).get_json()
    return SimpleNamespace(app=app, admin=client, pia=pia, sent=sent, built=built, profile=profile,
                           bundle=built["bundle_artifact"], monkeypatch=monkeypatch)


def body(s, **extra):
    return {"profile_id": s.profile["id"], "bundle_artifact_id": s.bundle["id"], **extra}


def review(client, s, **extra):
    return client.post("/api/publish/review", json=body(s, **extra))


def confirm(client, s, token, **extra):
    return client.post("/api/publish", json=body(s, review_token=token, confirm=True, **extra))


def audit(s, action):
    return s.admin.get("/api/admin/audit", query_string={"action": action}).get_json()["events"]


# --- who may publish -----------------------------------------------------------------

@pytest.mark.parametrize("role", ["reader", "user", "player"])
def test_students_without_the_publisher_role_get_403(setup, role):
    s = setup
    with s.app.app_context():
        create_user(f"x{role}", f"x{role}@school.test", PASSWORD, role=role)
    student = s.app.test_client(login=(f"x{role}", PASSWORD))
    mine = student.post("/api/publish_profiles", json={"name": "Mine", "store_url": STORE}).get_json()
    assert student.post("/api/publish/review", json={"profile_id": mine["id"],
                                                     "bundle_artifact_id": s.bundle["id"]}).status_code == 403
    assert student.post("/api/publish", json={"profile_id": mine["id"], "bundle_artifact_id": s.bundle["id"],
                                              "review_token": "x", "confirm": True}).status_code == 403
    assert s.sent == []
    assert audit(s, "publish_review")[0]["outcome"] == "denied"


def test_publisher_reviews_then_confirms(setup):
    s = setup
    response = review(s.pia, s)
    assert response.status_code == 200, response.get_data(as_text=True)
    data = response.get_json()
    summary = data["summary"]
    assert summary["store"] == {"origin": STORE, "host": "store.school.test", "authentication": "token"}
    assert summary["cartridge"]["id"].endswith("pub-game") and summary["cartridge"]["version"]
    digest = hashlib.sha256(CARTRIDGE).hexdigest()
    assert {(a["id"], a["sha256"], a["bytes"]) for a in summary["architectures"]} == {
        ("esp32c6", digest, len(CARTRIDGE)), ("qemu", digest, len(CARTRIDGE))}
    assert len(summary["bundle"]["sha256"]) == 64 and summary["bundle"]["bytes"] > 0
    assert "review" in summary["after_upload"].lower()
    assert "prg32_token_secret_1" not in response.get_data(as_text=True)
    assert s.sent == []  # reviewing sends nothing
    published = confirm(s.pia, s, data["review_token"])
    assert published.status_code == 200, published.get_data(as_text=True)
    result = published.get_json()
    assert result["state"] == "submitted" and result["result"]["ok"] is True
    assert len(s.sent) == 1 and s.sent[0]["token"] == "prg32_token_secret_1"
    assert "prg32_token_secret_1" not in published.get_data(as_text=True)


def test_admins_may_publish_too(setup):
    s = setup
    admin_profile = s.admin.post("/api/publish_profiles", json={"name": "A", "store_url": STORE}).get_json()
    payload = {"profile_id": admin_profile["id"], "bundle_artifact_id": s.bundle["id"]}
    token = s.admin.post("/api/publish/review", json=payload).get_json()["review_token"]
    assert s.admin.post("/api/publish", json={**payload, "review_token": token, "confirm": True}).status_code == 200


def test_the_ui_hides_publishing_from_students_but_the_backend_decides(setup):
    s = setup
    student = s.app.test_client(login=("ugo", PASSWORD))
    assert b"needs the publisher role" in student.get("/publish").data
    assert b"needs the publisher role" not in s.pia.get("/publish").data


# --- confirmation is explicit and tied to the review -------------------------------------

def test_publish_without_a_review_or_confirmation_is_refused(setup):
    s = setup
    assert s.pia.post("/api/publish", json=body(s)).status_code == 428
    token = review(s.pia, s).get_json()["review_token"]
    assert s.pia.post("/api/publish", json=body(s, review_token=token)).status_code == 428  # no confirm
    assert s.pia.post("/api/publish", json=body(s, review_token=token, confirm="yes")).status_code == 428
    assert s.sent == []


def test_a_token_cannot_be_used_for_another_bundle_or_profile(setup):
    s = setup
    token = review(s.pia, s).get_json()["review_token"]
    other_project = s.pia.post("/api/projects", json={"title": "Other", "blocks_json": default_blocks()}).get_json()
    other_bundle = s.pia.post(f"/api/projects/{other_project['id']}/package", json={}).get_json()["bundle_artifact"]
    swapped = s.pia.post("/api/publish", json={"profile_id": s.profile["id"], "bundle_artifact_id": other_bundle["id"],
                                               "review_token": token, "confirm": True})
    assert swapped.status_code == 409
    other_profile = s.pia.post("/api/publish_profiles", json={"name": "Other", "store_url": STORE}).get_json()
    swapped = s.pia.post("/api/publish", json={"profile_id": other_profile["id"], "bundle_artifact_id": s.bundle["id"],
                                               "review_token": token, "confirm": True})
    assert swapped.status_code == 409
    assert s.sent == []


def test_a_token_belongs_to_the_user_who_reviewed(setup):
    s = setup
    token = review(s.pia, s).get_json()["review_token"]
    with s.app.app_context():
        create_user("pat", "pat@school.test", PASSWORD, role="publisher")
    pat = s.app.test_client(login=("pat", PASSWORD))
    # Pat cannot even see Pia's profile and bundle; with an admin's shared ones the token still fails.
    assert confirm(pat, s, token).status_code in (404, 409)
    assert s.sent == []


def test_a_changed_bundle_after_review_is_refused(setup):
    s = setup
    token = review(s.pia, s).get_json()["review_token"]
    with s.app.app_context():
        from prg32_construction_kit.db import get_resource
        path = get_resource("artifacts", s.bundle["id"])["path"]
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("extra.txt", "changed after review")
    response = confirm(s.pia, s, token)
    assert response.status_code == 409 and "changed" in response.get_json()["error"]
    assert s.sent == []


def test_a_changed_store_address_after_review_is_refused(setup):
    s = setup
    token = review(s.pia, s).get_json()["review_token"]
    s.app.config["STORE_ALLOWED_ORIGINS"] = [STORE, "https://other.school.test"]
    s.pia.put(f"/api/publish_profiles/{s.profile['id']}", json={"store_url": "https://other.school.test"})
    assert confirm(s.pia, s, token).status_code == 409
    assert s.sent == []


def test_stale_or_forged_tokens_are_refused(setup, monkeypatch):
    s = setup
    token = review(s.pia, s).get_json()["review_token"]
    assert confirm(s.pia, s, token[:-2] + "xx").status_code == 409
    assert confirm(s.pia, s, "not-a-token").status_code == 409
    monkeypatch.setattr(publishing, "REVIEW_SECONDS", -1)  # every token is now too old
    response = confirm(s.pia, s, token)
    assert response.status_code == 409 and "review again" in response.get_json()["error"].lower()
    assert s.sent == []


# --- only real cartridges ------------------------------------------------------------------

def test_source_only_bundles_are_refused(setup, monkeypatch):
    s = setup
    monkeypatch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: False)
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run",
                        lambda command, **_kw: SimpleNamespace(returncode=1, stdout="", stderr="no compiler"))
    project = s.pia.post("/api/projects", json={"title": "Src", "blocks_json": default_blocks()}).get_json()
    source = s.pia.post(f"/api/projects/{project['id']}/package", json={}).get_json()["bundle_artifact"]
    assert source["kind"] == "source_bundle"
    response = s.pia.post("/api/publish/review", json={"profile_id": s.profile["id"], "bundle_artifact_id": source["id"]})
    assert response.status_code == 400 and response.get_json()["reason"] == "not_publishable"
    # A client cannot force it through the confirm step either.
    response = s.pia.post("/api/publish", json={"profile_id": s.profile["id"], "bundle_artifact_id": source["id"],
                                                "review_token": "x", "confirm": True})
    assert response.status_code == 400
    assert s.sent == []


def _replace_in_bundle(s, name, data=None, drop=None):
    with s.app.app_context():
        from prg32_construction_kit.db import get_resource
        path = get_resource("artifacts", s.bundle["id"])["path"]
    with zipfile.ZipFile(path) as archive:
        files = {info.filename: archive.read(info) for info in archive.infolist()}
    if drop:
        files.pop(drop)
    if data is not None:
        files[name] = data
    with zipfile.ZipFile(path, "w") as archive:
        for entry, content in files.items():
            archive.writestr(entry, content)


def test_missing_cartridges_are_refused(setup):
    s = setup
    _replace_in_bundle(s, None, drop="pub-game-qemu.prg32")
    response = review(s.pia, s)
    assert response.status_code == 400 and response.get_json()["reason"] == "missing_cartridge"


def test_files_that_are_not_cartridges_are_refused(setup):
    s = setup
    _replace_in_bundle(s, "pub-game-qemu.prg32", b"#!/bin/sh\necho not a cartridge\n")
    response = review(s.pia, s)
    assert response.status_code == 400 and response.get_json()["reason"] == "not_a_cartridge"


def test_cartridges_that_differ_from_the_build_are_refused(setup):
    s = setup
    _replace_in_bundle(s, "pub-game-qemu.prg32", b"PRG2" + b"\x02" * 64)
    response = review(s.pia, s)
    assert response.status_code == 400 and response.get_json()["reason"] == "hash_mismatch"


def test_bad_manifests_are_refused(setup):
    s = setup
    _replace_in_bundle(s, "manifest.json", json.dumps({"abi": "something-else"}).encode())
    response = review(s.pia, s)
    assert response.status_code == 400 and response.get_json()["reason"] == "bad_manifest"


def test_uploaded_bundles_without_a_kit_build_are_refused(setup):
    s = setup
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("manifest.json", "{}")
    uploaded = s.pia.post("/api/artifacts/upload", data={"file": (io.BytesIO(data.getvalue()), "b.zip"),
                                                         "kind": "store_bundle"},
                          content_type="multipart/form-data").get_json()
    response = s.pia.post("/api/publish/review", json={"profile_id": s.profile["id"], "bundle_artifact_id": uploaded["id"]})
    assert response.status_code == 400 and response.get_json()["reason"] == "not_publishable"


# --- states, retries and idempotency ------------------------------------------------------

def test_confirming_twice_does_not_upload_twice(setup):
    s = setup
    token = review(s.pia, s).get_json()["review_token"]
    first = confirm(s.pia, s, token).get_json()
    again = confirm(s.pia, s, token)
    assert again.status_code == 200
    assert again.get_json()["duplicate"] is True and again.get_json()["result"] == first["result"]
    assert len(s.sent) == 1
    assert [e["metadata"]["stage"] for e in audit(s, "publish")][:2] == ["duplicate", "submitted"]


def test_a_failed_upload_can_be_retried(setup):
    s = setup
    calls = []

    def flaky(store_url, token, path):
        calls.append(1)
        if len(calls) == 1:
            from prg32_construction_kit.publisher import StorePublishFailed
            raise StorePublishFailed("timeout")
        return {"ok": True, "status_code": 200, "store_host": "store.school.test", "message": "received",
                "response": {"ok": True, "status": "pending", "submission_id": 9}}

    s.monkeypatch.setattr("prg32_construction_kit.routes.publish_bundle", flaky)
    token = review(s.pia, s).get_json()["review_token"]
    failed = confirm(s.pia, s, token)
    assert failed.status_code == 502 and failed.get_json()["state"] == "failed"
    assert failed.get_json()["reason"] == "timeout"
    retried = confirm(s.pia, s, token)
    assert retried.status_code == 200 and retried.get_json()["state"] == "submitted"
    assert len(calls) == 2


def test_store_refusals_are_recoverable_failures(setup):
    s = setup

    def duplicate(store_url, token, path):
        return {"ok": False, "status_code": 400, "store_host": "store.school.test",
                "message": "version 1.0.0 already exists", "response": {"ok": False, "error": "version already exists"}}

    s.monkeypatch.setattr("prg32_construction_kit.routes.publish_bundle", duplicate)
    token = review(s.pia, s).get_json()["review_token"]
    response = confirm(s.pia, s, token)
    assert response.status_code == 200
    data = response.get_json()
    assert data["state"] == "failed" and data["result"]["ok"] is False
    assert "already exists" in data["result"]["message"]
    assert audit(s, "publish")[0]["metadata"]["stage"] == "failed"


def test_audit_distinguishes_review_refusal_upload_success_and_failure(setup):
    s = setup
    review(s.app.test_client(login=("ugo", PASSWORD)), s)            # refused: no role
    token = review(s.pia, s).get_json()["review_token"]               # allowed review
    confirm(s.pia, s, token)                                          # upload + submitted
    reviews = [(e["outcome"]) for e in audit(s, "publish_review")]
    assert reviews[:2] == ["success", "denied"]
    stages = [e["metadata"]["stage"] for e in audit(s, "publish")]
    assert stages[:2] == ["submitted", "upload"]
    stored = json.dumps(s.admin.get("/api/admin/audit").get_json())
    assert "prg32_token_secret_1" not in stored and token not in stored
