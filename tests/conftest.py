from __future__ import annotations

from pathlib import Path

import pytest

from prg32_construction_kit import create_app


@pytest.fixture()
def app(tmp_path: Path):
    app = create_app(
        {
            "TESTING": True,
            "DATA_DIR": tmp_path,
            "DB_PATH": tmp_path / "test.sqlite",
            "BUILD_ROOT": tmp_path / "builds",
            "ARTIFACT_ROOT": tmp_path / "artifacts",
            "PRG32_BUILD_COMMAND": "python3 -m prg32 build",
        }
    )
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()
