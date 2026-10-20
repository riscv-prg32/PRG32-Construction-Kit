"""Store lifecycle rules the kit keeps while the Cartridge Store has gaps (contract tokens/versioning).

- One bundle per cartridge id and version per Store: the same files again answer with the
  first result and upload nothing; other files are refused until the project is saved.
- A publish profile's Store token is refused after PRG32_STORE_TOKEN_MAX_DAYS; the age is
  set by the server, shown as an expiry date, and reset when a new token is put in.
- The contract only grew: every key of version 1 is still there.
"""

from __future__ import annotations

import json

from test_publish_authorization import confirm, review, setup  # noqa: F401 - fixture

from prg32_construction_kit import store_contract
from prg32_construction_kit.db import PublishProfile, db


def publish(s, bundle_id=None):
    payload = {"profile_id": s.profile["id"], "bundle_artifact_id": bundle_id or s.bundle["id"]}
    answer = s.pia.post("/api/publish/review", json=payload)
    if answer.status_code != 200:
        return answer
    return s.pia.post("/api/publish", json={**payload, "review_token": answer.get_json()["review_token"], "confirm": True})


def rebuild(s, change=False):
    project_id = s.built["build"]["project_id"]
    if change:
        current = s.pia.get(f"/api/projects/{project_id}").get_json()
        s.pia.put(f"/api/projects/{project_id}", json={"description": "changed", "expected_version": current["version"]})
    return s.pia.post(f"/api/projects/{project_id}/package", json={}).get_json()["bundle_artifact"]


def test_one_id_and_version_goes_to_a_store_once(setup):  # noqa: F811
    s = setup
    assert publish(s).get_json()["state"] == "submitted" and len(s.sent) == 1
    again = publish(s, rebuild(s)["id"])        # compiled again, project not saved: same version
    body = again.get_json()
    if again.status_code == 409:                # other files: refused, with what to do
        assert body["reason"] == "version_already_published" and "Save the project" in body["error"]
    else:                                       # the same files: the first answer, nothing sent
        assert body["duplicate"] is True
    assert len(s.sent) == 1
    saved = publish(s, rebuild(s, change=True)["id"])   # saved: a new version
    assert saved.status_code == 200 and saved.get_json()["state"] == "submitted" and len(s.sent) == 2


def test_a_different_bundle_with_the_same_version_is_refused_at_review(setup, monkeypatch):  # noqa: F811
    s = setup
    publish(s)
    from prg32_construction_kit import publishing

    real = publishing.build_summary

    def other_files(**kwargs):
        summary = real(**kwargs)
        summary["bundle"]["sha256"] = "0" * 64
        return summary

    monkeypatch.setattr(publishing, "build_summary", other_files)
    refused = s.pia.post("/api/publish/review", json={"profile_id": s.profile["id"], "bundle_artifact_id": s.bundle["id"]})
    assert refused.status_code == 409 and refused.get_json()["reason"] == "version_already_published"
    assert len(s.sent) == 1


def age_token(s, days):
    with s.app.app_context():
        row = db.session.get(PublishProfile, s.profile["id"])
        row.token_set_at = "2020-01-01T00:00:00+00:00" if days else row.token_set_at
        db.session.commit()


def test_an_old_store_token_is_refused_and_a_new_one_works(setup):  # noqa: F811
    s = setup
    s.app.config["STORE_TOKEN_MAX_DAYS"] = 30
    shown = s.pia.get(f"/api/publish_profiles/{s.profile['id']}").get_json()
    assert shown["token_expires_on"] and "bearer_token" not in shown and "prg32_token" not in json.dumps(shown)
    age_token(s, 400)
    refused = publish(s)
    assert refused.status_code == 400 and refused.get_json()["reason"] == "token_too_old" and s.sent == []
    # A student cannot make a token look new; putting in a new token does.
    s.pia.put(f"/api/publish_profiles/{s.profile['id']}", json={"token_set_at": "2099-01-01T00:00:00+00:00"})
    assert publish(s).status_code == 400
    s.pia.put(f"/api/publish_profiles/{s.profile['id']}", json={"bearer_token": "prg32_token_secret_2"})
    assert publish(s).get_json()["state"] == "submitted" and s.sent[0]["token"] == "prg32_token_secret_2"


def test_token_age_can_be_switched_off(setup):  # noqa: F811
    s = setup
    s.app.config["STORE_TOKEN_MAX_DAYS"] = 0
    age_token(s, 4000)
    assert publish(s).get_json()["state"] == "submitted"
    assert s.pia.get(f"/api/publish_profiles/{s.profile['id']}").get_json()["token_expires_on"] == ""


def test_old_databases_get_the_columns_and_tokens_start_counting_now(tmp_path):
    import sqlite3

    from conftest import make_app

    database = tmp_path / "test.sqlite"
    connection = sqlite3.connect(database)
    connection.executescript("""
        CREATE TABLE publish_profiles (id TEXT PRIMARY KEY, name TEXT NOT NULL, store_url TEXT NOT NULL,
            bearer_token TEXT NOT NULL DEFAULT '', owner_id INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        INSERT INTO publish_profiles VALUES ('profile_old', 'Old', 'https://store.school.test', 'prg32_old', NULL,
            '2020-01-01T00:00:00+00:00', '2020-01-01T00:00:00+00:00');
        CREATE TABLE publish_attempts (id TEXT PRIMARY KEY, digest TEXT NOT NULL UNIQUE, user_id INTEGER NOT NULL,
            profile_id TEXT NOT NULL, artifact_id TEXT NOT NULL, state TEXT NOT NULL, result TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    """)
    connection.commit()
    connection.close()
    make_app(tmp_path)
    make_app(tmp_path)                         # twice: idempotent
    connection = sqlite3.connect(database)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(publish_attempts)")}
    assert {"store_host", "cartridge_id", "cartridge_version", "bundle_sha256"} <= columns
    set_at = connection.execute("SELECT token_set_at FROM publish_profiles WHERE id = 'profile_old'").fetchone()[0]
    assert set_at.startswith("20") and not set_at.startswith("2020")


V1_KEYS = {"contract", "description", "store_reference", "bundle", "manifest_schema", "architectures", "versioning",
           "publish", "errors", "tokens", "publish_profile", "cartridge_artifact_metadata"}
V1_ERROR_CODES = {"unauthorized", "forbidden", "too_large", "not_a_zip", "manifest_missing", "unsafe_path",
                  "manifest_invalid", "unsafe_id_or_version", "file_missing", "bad_image", "bad_architecture",
                  "bad_cartridge", "server_error", "unavailable", "network"}


def test_the_contract_only_grew():
    contract = store_contract.contract()
    assert contract["contract"] == "prg32-store-contract-1"
    assert V1_KEYS <= set(contract)
    assert V1_ERROR_CODES <= {rule["code"] for rule in contract["errors"]}
    assert contract["versioning"]["duplicate_identity_version"] == "store_accepts_duplicate_pending"
    assert contract["tokens"]["expiry"] == "none"
    # Proposed codes are classified when a newer Store sends them; old answers keep their codes.
    assert store_contract.classify(401, "token_expired")["code"] == "token_expired"
    assert store_contract.classify(401, "bad token")["code"] == "unauthorized"
    assert store_contract.classify(409)["code"] == "duplicate_version"
