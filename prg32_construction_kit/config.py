from __future__ import annotations

import os
from pathlib import Path


class Config:
    """Runtime configuration for PRG32-Construction-Kit.

    All paths default to the repository-local data directory so a classroom can
    run the project with a simple `python app.py`. Containers should mount
    `/data` and set PRG32_KIT_DATA=/data.
    """

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-prg32-construction-kit-change-me")
    DATA_DIR = Path(os.environ.get("PRG32_KIT_DATA", "data")).resolve()
    DB_PATH = Path(os.environ.get("PRG32_KIT_DB", DATA_DIR / "construction_kit.sqlite")).resolve()
    BUILD_ROOT = Path(os.environ.get("PRG32_KIT_BUILD_ROOT", DATA_DIR / "builds")).resolve()
    ARTIFACT_ROOT = Path(os.environ.get("PRG32_KIT_ARTIFACT_ROOT", DATA_DIR / "artifacts")).resolve()
    DEFAULT_STORE_URL = os.environ.get("PRG32_STORE_URL", "http://127.0.0.1:5080")
    PRG32_BUILD_COMMAND = os.environ.get("PRG32_BUILD_COMMAND", "python3 -m prg32 build")
    MAX_CONTENT_LENGTH = int(os.environ.get("PRG32_KIT_MAX_UPLOAD", str(32 * 1024 * 1024)))
    JSON_SORT_KEYS = False
