from __future__ import annotations

from types import SimpleNamespace
import io
import json
import zipfile

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
    assert len(examples) == 22
    assert {example["slug"] for example in examples} >= {"pong", "raycaster", "audio_synth"}

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

    download = client.get(f"/api/artifacts/{cartridges[0]['id']}/download")
    assert download.status_code == 200
    assert download.data == b"PRG32-test"


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
