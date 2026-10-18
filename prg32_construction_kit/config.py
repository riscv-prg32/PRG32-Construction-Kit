from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path


def _throttle_overrides() -> dict[str, tuple[int, int]]:
    """PRG32_KIT_THROTTLE_LOGIN_USER=5/900 means: 5 attempts per 900 seconds (see security.LIMITS)."""
    limits: dict[str, tuple[int, int]] = {}
    for key, value in os.environ.items():
        if key.startswith("PRG32_KIT_THROTTLE_") and "/" in value:
            attempts, window = value.split("/", 1)
            limits[key.removeprefix("PRG32_KIT_THROTTLE_").lower()] = (int(attempts), int(window))
    return limits


def _flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


class Config:
    """Runtime configuration for PRG32-Construction-Kit.

    All paths default to the repository-local data directory so a classroom can
    run the project with a simple `python app.py`. Containers should mount
    `/data` and set PRG32_KIT_DATA=/data.
    """

    # Signs the sign-in cookie. When unset, a random key is created once and
    # kept in DATA_DIR/secret_key so restarts do not sign everybody out.
    SECRET_KEY = os.environ.get("SECRET_KEY") or None
    DATA_DIR = Path(os.environ.get("PRG32_KIT_DATA", "data")).resolve()
    DB_PATH = Path(os.environ.get("PRG32_KIT_DB", DATA_DIR / "construction_kit.sqlite")).resolve()
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    BUILD_ROOT = Path(os.environ.get("PRG32_KIT_BUILD_ROOT", DATA_DIR / "builds")).resolve()
    ARTIFACT_ROOT = Path(os.environ.get("PRG32_KIT_ARTIFACT_ROOT", DATA_DIR / "artifacts")).resolve()
    DEFAULT_STORE_URL = os.environ.get("PRG32_STORE_URL", "http://127.0.0.1:5080")
    # The default runs the PRG32 builder with the same Python that runs the kit,
    # so `pip install -e ../PRG32` inside the kit's virtual environment is enough.
    PRG32_BUILD_COMMAND = os.environ.get("PRG32_BUILD_COMMAND") or f"{shlex.quote(sys.executable)} -m prg32 cartridge build"
    PRG32_CART_RAM_KIB = int(os.environ.get("PRG32_CART_RAM_KIB", "64"))
    # How many cartridge builds may compile at the same time on this server,
    # and how long (seconds) a build waits for a free slot before giving up.
    PRG32_MAX_PARALLEL_BUILDS = int(os.environ.get("PRG32_MAX_PARALLEL_BUILDS", str(os.cpu_count() or 2)))
    PRG32_BUILD_QUEUE_TIMEOUT = float(os.environ.get("PRG32_BUILD_QUEUE_TIMEOUT", "180"))
    # Seconds one compiler run (one architecture) may take before it is stopped.
    PRG32_BUILD_TIMEOUT = float(os.environ.get("PRG32_BUILD_TIMEOUT", "120"))
    # How many saved versions (revisions) the History menu keeps per project.
    PRG32_KIT_MAX_REVISIONS = int(os.environ.get("PRG32_KIT_MAX_REVISIONS", "50"))
    MAX_CONTENT_LENGTH = int(os.environ.get("PRG32_KIT_MAX_UPLOAD", str(32 * 1024 * 1024)))
    JSON_SORT_KEYS = False

    # Sign-in cookie. The name differs from Cartridge Store's, so both can run on one host.
    SESSION_COOKIE_NAME = "prg32_kit_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _flag("PRG32_KIT_SECURE_COOKIES", False)
    PERMANENT_SESSION_LIFETIME = int(os.environ.get("PRG32_KIT_SESSION_HOURS", "12")) * 3600

    # "production" (set by the Docker image) refuses weak first-admin passwords;
    # "development" (plain `python app.py`) allows them with a loud warning.
    KIT_ENV = (os.environ.get("PRG32_KIT_ENV") or "development").strip().lower()

    # Accounts (same model as PRG32 Cartridge Store).
    # Password of the first admin. Unset: a random one is written to
    # DATA_DIR/initial_admin_password on the first start (auth.bootstrap_admin).
    ADMIN_PASSWORD = os.environ.get("PRG32_ADMIN_PASSWORD") or None
    ALLOW_REGISTRATION = _flag("PRG32_KIT_ALLOW_REGISTRATION", True)
    REQUIRE_EMAIL_DOMAIN = os.environ.get("PRG32_KIT_REQUIRE_EMAIL_DOMAIN", "")
    DEFAULT_ROLE = os.environ.get("PRG32_KIT_DEFAULT_ROLE", "user")
    SMTP_HOST = os.environ.get("PRG32_SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("PRG32_SMTP_PORT", "587"))
    SMTP_FROM = os.environ.get("PRG32_SMTP_FROM", "noreply@localhost")
    SMTP_USER = os.environ.get("PRG32_SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("PRG32_SMTP_PASSWORD", "")
    SMTP_TLS = _flag("PRG32_SMTP_TLS", True)

    # Single sign-on and user sync with one Cartridge Store (see docs/accounts_and_sso.md).
    SSO_SECRET = os.environ.get("PRG32_SSO_SECRET", "")
    SSO_PEER_URL = os.environ.get("PRG32_SSO_PEER_URL", "")
    SSO_TIMEOUT = float(os.environ.get("PRG32_SSO_TIMEOUT", "5"))

    # Number of trusted reverse proxies in front of the kit. 0 (default): the
    # X-Forwarded-For header is ignored and the connecting address is used.
    PROXY_COUNT = int(os.environ.get("PRG32_KIT_PROXY_COUNT", "0"))
    # Overrides of the sign-in limits in security.LIMITS.
    THROTTLE_LIMITS = _throttle_overrides()
