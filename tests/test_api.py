from __future__ import annotations

from types import SimpleNamespace

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
