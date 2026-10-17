from __future__ import annotations

from types import SimpleNamespace
import io
import json
import zipfile

import pytest

from prg32_construction_kit.db import get_resource
from prg32_construction_kit.sample_data import default_blocks


def test_project_crud(client):
    response = client.post(
        "/api/projects",
        json={"title": "CRUD Game", "author": "Tester", "description": "CRUD", "tags": ["test"], "blocks_json": default_blocks()},
    )
    assert response.status_code == 201
    project = response.get_json()
    assert project["title"] == "CRUD Game"

    response = client.put(f"/api/projects/{project['id']}", json={"description": "Updated"})
    assert response.status_code == 200
    assert response.get_json()["description"] == "Updated"

    response = client.get(f"/api/projects/{project['id']}")
    assert response.status_code == 200

    response = client.delete(f"/api/projects/{project['id']}")
    assert response.status_code == 200
    assert response.get_json()["deleted"] is True


def test_convert_project_creates_artifact(client):
    response = client.post(
        "/api/projects",
        json={"title": "Convert Me", "author": "Tester", "description": "", "tags": [], "blocks_json": default_blocks()},
    )
    project = response.get_json()
    response = client.post(f"/api/projects/{project['id']}/convert", json={})
    assert response.status_code == 200
    data = response.get_json()
    assert "prg32_gfx_rect" in data["c_source"]
    assert data["artifact"]["kind"] == "c_source"


def test_sprite_crud_and_convert(client):
    pixels = [["#ffffff", "transparent"], ["#000000", "#ff0000"]]
    response = client.post("/api/sprites", json={"name": "tiny", "width": 2, "height": 2, "pixels": pixels})
    assert response.status_code == 201
    sprite = response.get_json()
    response = client.post(f"/api/sprites/{sprite['id']}/convert", json={})
    assert response.status_code == 200
    assert "tiny_pixels" in response.get_json()["c_source"]


def test_discovery(client):
    response = client.get("/.well-known/prg32-construction-kit.json")
    assert response.status_code == 200
    assert response.get_json()["abi"] == "prg32-construction-kit-discovery-1.0"


def test_upstream_blocks_examples_can_be_listed_and_imported(client):
    response = client.get("/api/examples")
    assert response.status_code == 200
    examples = response.get_json()["examples"]
    # Five complete games replace four of the 22 upstream sketches: 22 - 4 + 5.
    assert len(examples) == 23
    assert {example["slug"] for example in examples} >= {"pong", "raycaster", "audio_synth", "snake"}
    kinds = {example["slug"]: example["kind"] for example in examples}
    assert [slug for slug, kind in kinds.items() if kind == "game"] == [
        "pong", "breakout", "space_invaders", "asteroids", "snake"]
    assert kinds["raycaster"] == "sketch"

    response = client.post("/api/examples/pong/import", json={})
    assert response.status_code == 201
    project = response.get_json()
    assert project["title"] == "Pong"
    assert project["blocks_json"]["blocks"]["blocks"]


def test_package_exposes_downloadable_prg32_cartridges(client, monkeypatch):
    commands = []
    def fake_run(command, **_kwargs):
        commands.append(command)
        out_path = command[command.index("--out") + 1]
        with open(out_path, "wb") as cartridge:
            cartridge.write(b"PRG32-test")
        return SimpleNamespace(returncode=0, stdout="built\n", stderr="")

    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_run)
    project = client.post(
        "/api/projects",
        json={"title": "Download Me", "author": "Tester", "blocks_json": default_blocks()},
    ).get_json()

    response = client.post(f"/api/projects/{project['id']}/package", json={})
    assert response.status_code == 200
    cartridges = response.get_json()["cartridge_artifacts"]
    assert {item["metadata"]["architecture"] for item in cartridges} == {"esp32c6", "qemu"}
    assert all(item["kind"] == "prg32_cartridge" for item in cartridges)
    assert {command[command.index("--architecture") + 1] for command in commands} == {"esp32c6", "qemu"}
    assert all(command[command.index("--cart-ram-kib") + 1] == "64" for command in commands)
    assert response.get_json()["result"]["cart_ram_kib"] == 64
    assert response.get_json()["build"]["metadata"]["cart_ram_kib"] == 64
    assert all(item["metadata"]["cart_ram_kib"] == 64 for item in cartridges)

    download = client.get(f"/api/artifacts/{cartridges[0]['id']}/download")
    assert download.status_code == 200
    assert download.data == b"PRG32-test"


def test_package_can_build_a_single_cartridge_for_direct_download(client, monkeypatch):
    commands = []
    def fake_run(command, **_kwargs):
        commands.append(command)
        with open(command[command.index("--out") + 1], "wb") as cartridge:
            cartridge.write(b"PRG32-qemu")
        return SimpleNamespace(returncode=0, stdout="built\n", stderr="")

    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_run)
    project = client.post("/api/projects", json={"title": "Direct", "blocks_json": default_blocks()}).get_json()

    response = client.post(f"/api/projects/{project['id']}/package", json={"architectures": ["qemu"]})
    assert response.status_code == 200
    cartridges = response.get_json()["cartridge_artifacts"]
    assert [item["metadata"]["architecture"] for item in cartridges] == ["qemu"]
    assert [command[command.index("--architecture") + 1] for command in commands] == ["qemu"]
    assert cartridges[0]["name"] == "direct-qemu.prg32"
    download = client.get(f"/api/artifacts/{cartridges[0]['id']}/download")
    assert download.data == b"PRG32-qemu"
    assert "direct-qemu.prg32" in download.headers["Content-Disposition"]


@pytest.mark.parametrize("architectures", [[], ["x86"], "qemu", ["qemu", "../evil"]])
def test_package_rejects_unknown_architectures(client, monkeypatch, architectures):
    def fail_run(*_args, **_kwargs):
        raise AssertionError("the toolchain must not run")

    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fail_run)
    project = client.post("/api/projects", json={"title": "Bad", "blocks_json": default_blocks()}).get_json()
    response = client.post(f"/api/projects/{project['id']}/package", json={"architectures": architectures})
    assert response.status_code == 400
    assert client.get("/api/builds").get_json()["builds"] == []


def test_advanced_c_project_is_saved_built_and_exported(client, monkeypatch):
    source = ('#include "prg32.h"\n'
              'void advanced_game_init(void) {}\n'
              'void advanced_game_update(void) { (void)prg32_random_number(0, 9); }\n'
              'void advanced_game_draw(void) { prg32_gfx_clear_indexed(0); }\n')
    project = client.post('/api/projects', json={
        'title': 'Advanced Game', 'game_json': {'source_mode': 'c', 'source_c': source,
                                              'required_features': ['tilemap', 'sprites']}
    }).get_json()

    commands = []
    def fake_run(command, **_kwargs):
        commands.append(command)
        with open(command[command.index('--out') + 1], 'wb') as cartridge:
            cartridge.write(b'PRG32-test')
        return SimpleNamespace(returncode=0, stdout='built\n', stderr='')

    monkeypatch.setattr('prg32_construction_kit.packager.subprocess.run', fake_run)
    response = client.post(f"/api/projects/{project['id']}/package", json={})
    assert response.status_code == 200
    result = response.get_json()
    assert result['c_artifact']['text_content'] == source
    assert result['result']['publishable'] is True
    assert all('--required-feature' in command for command in commands)
    assert all('tilemap' in command and 'sprites' in command for command in commands)
    with zipfile.ZipFile(io.BytesIO(client.get(
        f"/api/artifacts/{result['bundle_artifact']['id']}/download"
    ).data)) as bundle:
        assert bundle.read('source/game.c').decode() == source
    exported = json.loads(client.get(f"/api/projects/{project['id']}/export").data)
    assert exported['project']['game_json']['source_c'] == source


def test_advanced_c_rejects_host_includes_and_wrong_entry_names(client):
    for source in (
        '#include "/etc/passwd"\nvoid bad_init(void) {}\nvoid bad_update(void) {}\nvoid bad_draw(void) {}',
        '#include "prg32.h"\nvoid wrong_init(void) {}\nvoid wrong_update(void) {}\nvoid wrong_draw(void) {}',
    ):
        project = client.post('/api/projects', json={
            'title': 'Bad', 'game_json': {'source_mode': 'c', 'source_c': source}
        }).get_json()
        response = client.post(f"/api/projects/{project['id']}/package", json={})
        assert response.status_code == 400

    source = ('#include "prg32.h"\nvoid bad_init(void) {}\n'
              'void bad_update(void) {}\nvoid bad_draw(void) {}\n')
    project = client.post('/api/projects', json={
        'title': 'Bad', 'game_json': {'source_mode': 'c', 'source_c': source,
                                    'required_features': ['not_a_feature']}
    }).get_json()
    assert client.post(f"/api/projects/{project['id']}/package", json={}).status_code == 400


def test_publish_profile_tokens_are_write_only(client, monkeypatch, tmp_path):
    response = client.post("/api/publish_profiles", json={"name": "Store", "store_url": "http://store.test", "bearer_token": "secret-123"})
    assert response.status_code == 201
    profile = response.get_json()
    assert "bearer_token" not in profile and profile["has_token"] is True
    assert "secret-123" not in client.get("/api/publish_profiles").get_data(as_text=True)
    assert "secret-123" not in client.get(f"/api/publish_profiles/{profile['id']}").get_data(as_text=True)
    assert "secret-123" not in client.put(f"/api/publish_profiles/{profile['id']}", json={"name": "Renamed"}).get_data(as_text=True)

    sent = {}
    def fake_publish(store_url, token, path):
        sent.update(store_url=store_url, token=token, path=path)
        return {"ok": True, "status_code": 200, "endpoint": store_url, "response": {}}
    monkeypatch.setattr("prg32_construction_kit.routes.publish_bundle", fake_publish)
    bundle = tmp_path / "builds" / "bundle.zip"
    bundle.parent.mkdir(parents=True, exist_ok=True)
    bundle.write_bytes(b"zip")
    artifact = client.post("/api/artifacts", json={"kind": "store_bundle", "name": "b.zip", "path": str(bundle)}).get_json()
    response = client.post("/api/publish", json={"profile_id": profile["id"], "bundle_artifact_id": artifact["id"]})
    assert response.status_code == 200
    assert sent["token"] == "secret-123"
    assert "secret-123" not in response.get_data(as_text=True)


def test_artifacts_cannot_point_outside_the_data_folder(client):
    artifact = client.post("/api/artifacts", json={"kind": "store_bundle", "name": "passwd", "path": "/etc/passwd"}).get_json()
    assert client.get(f"/api/artifacts/{artifact['id']}/download").status_code == 404
    profile = client.get("/api/publish_profiles").get_json()["publish_profiles"][0]
    response = client.post("/api/publish", json={"profile_id": profile["id"], "bundle_artifact_id": artifact["id"]})
    assert response.status_code == 404


def test_artifacts_cannot_serve_the_database(client, app):
    # The database holds publish bearer tokens; an artifact row must never expose it.
    client.post("/api/publish_profiles", json={"name": "Store", "store_url": "http://store.test", "bearer_token": "secret-123"})
    database = str(app.config["DB_PATH"])
    for path in (database, database + "-wal"):
        artifact = client.post("/api/artifacts", json={"kind": "store_bundle", "name": "db", "path": path}).get_json()
        response = client.get(f"/api/artifacts/{artifact['id']}/download")
        assert response.status_code == 404
        assert b"secret-123" not in response.data
        profile = client.get("/api/publish_profiles").get_json()["publish_profiles"][0]
        assert client.post("/api/publish", json={"profile_id": profile["id"], "bundle_artifact_id": artifact["id"]}).status_code == 404


def test_text_artifact_download_uses_a_safe_filename(client):
    artifact = client.post("/api/artifacts", json={"name": "my file; x=1.c", "text_content": "int x;"}).get_json()
    response = client.get(f"/api/artifacts/{artifact['id']}/download")
    assert response.status_code == 200
    assert response.data == b"int x;"
    assert "attachment" in response.headers["Content-Disposition"]


def test_bad_requests_return_clear_errors(client):
    assert client.post("/api/projects", json=["not", "an", "object"]).status_code == 400
    assert client.post("/api/projects", data="{broken", content_type="application/json").status_code == 400
    assert client.post("/api/projects", json={"id": 'x" onclick="alert(1)'}).status_code == 400
    assert client.post("/api/projects", json={"title": {"nested": True}}).status_code == 400
    assert client.post("/api/sprites", json={"width": "wide"}).status_code == 400
    assert client.post("/api/projects", json={"id": "project_same"}).status_code == 201
    assert client.post("/api/projects", json={"id": "project_same"}).status_code == 409
    assert client.post("/api/sprites", json={"project_id": "missing_project"}).status_code == 409
    assert client.post("/api/projects/import", json=["x"]).status_code == 400
    project = client.post("/api/projects", json={"title": "Keep"}).get_json()
    assert client.put(f"/api/projects/{project['id']}", json={"title": "Changed", "tags": [], "author": ["bad"]}).status_code == 400
    assert client.get(f"/api/projects/{project['id']}").get_json()["title"] == "Keep"


def test_uploads_with_the_same_name_do_not_overwrite(client):
    first = client.post("/api/artifacts/upload", data={"file": (io.BytesIO(b"one"), "game.prg32")}, content_type="multipart/form-data").get_json()
    second = client.post("/api/artifacts/upload", data={"file": (io.BytesIO(b"two"), "game.prg32")}, content_type="multipart/form-data").get_json()
    assert "path" not in first and "path" not in second
    assert first["id"] != second["id"]
    assert client.get(f"/api/artifacts/{first['id']}/download").data == b"one"
    dots = client.post("/api/artifacts/upload", data={"file": (io.BytesIO(b"x"), "..")}, content_type="multipart/form-data")
    assert dots.status_code == 201


def test_package_failure_marks_build_failed(client, monkeypatch):
    def broken(**_kwargs):
        raise OSError("disk full")
    monkeypatch.setattr("prg32_construction_kit.routes.prepare_package", broken)
    project = client.post("/api/projects", json={"title": "Broken", "blocks_json": default_blocks()}).get_json()
    response = client.post(f"/api/projects/{project['id']}/package", json={})
    assert response.status_code == 500
    builds = client.get(f"/api/builds?project_id={project['id']}").get_json()["builds"]
    assert builds[0]["status"] == "failed"


def test_package_uses_configured_build_root(client, app, monkeypatch):
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run",
                        lambda command, **_kw: SimpleNamespace(returncode=1, stdout="", stderr="no toolchain"))
    project = client.post("/api/projects", json={"title": "Where", "blocks_json": default_blocks()}).get_json()
    response = client.post(f"/api/projects/{project['id']}/package", json={}).get_json()
    result = response["result"]
    assert "work_dir" not in result and "bundle_path" not in result
    assert "path" not in response["bundle_artifact"]
    assert "work_dir" not in response["bundle_artifact"]["metadata"]
    with app.app_context():
        stored = get_resource("artifacts", response["bundle_artifact"]["id"])
        assert stored["path"].startswith(str(app.config["BUILD_ROOT"]))
    assert result["status"] == "source-only"
