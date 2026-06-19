from __future__ import annotations

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
