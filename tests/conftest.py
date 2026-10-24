from __future__ import annotations

from pathlib import Path

import pytest
from flask.testing import FlaskClient

from prg32_construction_kit import create_app

ADMIN_PASSWORD = "teacher-password-123"


class SignedInClient(FlaskClient):
    """A test browser that signs in first (as the admin unless told otherwise).

    ``app.test_client(login=None)`` gives a browser that is not signed in.
    """

    def __init__(self, *args, login: tuple[str, str] | None = ("admin", ADMIN_PASSWORD), **kwargs):
        super().__init__(*args, **kwargs)
        self.environ_base["HTTP_X_PRG32_KIT"] = "1"  # sent by static/js/app.js on every request
        if login:
            response = self.post("/auth/login", data={"username": login[0], "password": login[1]})
            assert response.status_code == 302, response.get_data(as_text=True)


def make_app(tmp_path: Path, **extra):
    config = {
        "TESTING": True,
        "DATA_DIR": tmp_path,
        "DB_PATH": tmp_path / "test.sqlite",
        "BUILD_ROOT": tmp_path / "builds",
        "ARTIFACT_ROOT": tmp_path / "artifacts",
        "PRG32_BUILD_COMMAND": "python3 -m prg32 cartridge build",
        "PRG32_CART_RAM_KIB": 64,
        "ADMIN_PASSWORD": ADMIN_PASSWORD,
        "SSO_SECRET": "",
        "SSO_PEER_URL": "",
    }
    config.update(extra)
    app = create_app(config)
    app.test_client_class = SignedInClient
    return app


@pytest.fixture()
def app(tmp_path: Path):
    yield make_app(tmp_path)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def anon(app):
    return app.test_client(login=None)


# --- publishing helpers (ADR-0009: publisher role, publishable bundle, review then confirm) ---

def make_store_bundle(client, monkeypatch, title="Publish Me"):
    """A real Store bundle (with fake-compiled PRG2 cartridges) made through the package API."""
    from types import SimpleNamespace

    from prg32_construction_kit.sample_data import default_blocks

    def fake_builder(command, **_kwargs):
        with open(command[command.index("--out") + 1], "wb") as cartridge:
            cartridge.write(b"PRG2" + b"\x00" * 60)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder)
    monkeypatch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: True)
    project = client.post("/api/projects", json={"title": title, "blocks_json": default_blocks()}).get_json()
    bundle = client.post(f"/api/projects/{project['id']}/package", json={}).get_json()["bundle_artifact"]
    assert bundle["kind"] == "store_bundle"
    return bundle


def review_and_publish(client, profile_id, bundle_id):
    """Review a bundle, then confirm it. Returns the confirm response."""
    request = {"profile_id": profile_id, "bundle_artifact_id": bundle_id}
    review = client.post("/api/publish/review", json=request)
    assert review.status_code == 200, review.get_data(as_text=True)
    return client.post("/api/publish", json={**request, "review_token": review.get_json()["review_token"],
                                             "confirm": True})
