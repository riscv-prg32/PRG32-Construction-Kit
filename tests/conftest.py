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
