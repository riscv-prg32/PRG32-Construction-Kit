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
    # Store egress policy (docs/adr/0008-store-egress-policy.md). Origins bundles may be
    # sent to; unset = the origins of PRG32_STORE_URL and PRG32_SSO_PEER_URL.
    STORE_ALLOWED_ORIGINS = ([item.strip() for item in os.environ["PRG32_STORE_ALLOWED_ORIGINS"].split(",") if item.strip()]
                             if os.environ.get("PRG32_STORE_ALLOWED_ORIGINS") else None)
    # 1 = the Store may be on a private/loopback address (classroom LAN, laptop); plain http
    # is then also allowed outside production.
    # Optional cloud storage for registered accounts (ADR-0019, docs/cloud_storage.md).
    # Unset = no cloud storage; everything else works the same.
    CLOUD_GOOGLE_CLIENT_ID = os.environ.get("PRG32_CLOUD_GOOGLE_CLIENT_ID") or None
    CLOUD_GOOGLE_CLIENT_SECRET = os.environ.get("PRG32_CLOUD_GOOGLE_CLIENT_SECRET") or None
    CLOUD_ONEDRIVE_CLIENT_ID = os.environ.get("PRG32_CLOUD_ONEDRIVE_CLIENT_ID") or None
    CLOUD_ONEDRIVE_CLIENT_SECRET = os.environ.get("PRG32_CLOUD_ONEDRIVE_CLIENT_SECRET") or None
    CLOUD_ONEDRIVE_TENANT = os.environ.get("PRG32_CLOUD_ONEDRIVE_TENANT") or "common"
    # GitHub as a project remote (ADR-0025, docs/github.md): a GitHub App's client id and secret,
    # and its slug (github.com/apps/<slug>) so students can install it on their repository.
    CLOUD_GITHUB_CLIENT_ID = os.environ.get("PRG32_CLOUD_GITHUB_CLIENT_ID") or None
    CLOUD_GITHUB_CLIENT_SECRET = os.environ.get("PRG32_CLOUD_GITHUB_CLIENT_SECRET") or None
    CLOUD_GITHUB_APP_SLUG = os.environ.get("PRG32_CLOUD_GITHUB_APP_SLUG") or ""
    CLOUD_GITHUB_ENABLED = _flag("PRG32_CLOUD_GITHUB_ENABLED", True)
    # An admin can switch a configured provider off on the Settings page.
    CLOUD_GOOGLE_ENABLED = _flag("PRG32_CLOUD_GOOGLE_ENABLED", True)
    CLOUD_ONEDRIVE_ENABLED = _flag("PRG32_CLOUD_ONEDRIVE_ENABLED", True)
    # Encrypts stored cloud tokens; derived from SECRET_KEY when unset.
    CLOUD_TOKEN_KEY = os.environ.get("PRG32_CLOUD_TOKEN_KEY") or None
    # Store API tokens do not expire in the Cartridge Store (contract tokens.known_store_gap):
    # the kit refuses a publish profile's token older than this many days (0 = never).
    STORE_TOKEN_MAX_DAYS = int(os.environ.get("PRG32_STORE_TOKEN_MAX_DAYS", "180"))
    STORE_TRUSTED_LOCAL = _flag("PRG32_STORE_TRUSTED_LOCAL", False)
    # CA bundle for a Store with a school-issued certificate (default: the public CAs).
    STORE_CA_BUNDLE = os.environ.get("PRG32_STORE_CA_BUNDLE") or None
    # The default runs the PRG32 builder with the same Python that runs the kit,
    # so `pip install -e ../PRG32` inside the kit's virtual environment is enough.
    PRG32_BUILD_COMMAND = os.environ.get("PRG32_BUILD_COMMAND") or f"{shlex.quote(sys.executable)} -m prg32 cartridge build"
    PRG32_CART_RAM_KIB = int(os.environ.get("PRG32_CART_RAM_KIB", "64"))
    # How many cartridge builds may compile at the same time on this server,
    # and how long (seconds) a build waits for a free slot before giving up.
    PRG32_MAX_PARALLEL_BUILDS = int(os.environ.get("PRG32_MAX_PARALLEL_BUILDS", str(os.cpu_count() or 2)))
    PRG32_BUILD_QUEUE_TIMEOUT = float(os.environ.get("PRG32_BUILD_QUEUE_TIMEOUT", "180"))
    # Build sandbox (docs/build_sandbox.md, ADR-0010): bwrap (required), rlimit (limits only,
    # NOT isolation) or auto (bwrap when it works, else rlimit outside production).
    PRG32_BUILD_SANDBOX = os.environ.get("PRG32_BUILD_SANDBOX", "auto")
    PRG32_BUILD_RO_PATHS = os.environ.get("PRG32_BUILD_RO_PATHS", "")
    PRG32_BUILD_MEMORY_MB = int(os.environ.get("PRG32_BUILD_MEMORY_MB", "1536"))
    PRG32_BUILD_MAX_PROCESSES = int(os.environ.get("PRG32_BUILD_MAX_PROCESSES", "128"))
    # Seconds one compiler run (one architecture) may take before it is stopped.
    # Disk: one build folder at most PRG32_BUILD_MAX_MB; all of BUILD_ROOT at most
    # PRG32_BUILD_ROOT_MAX_MB (0 = no total budget). See build_budget.py.
    PRG32_BUILD_MAX_MB = int(os.environ.get("PRG32_BUILD_MAX_MB", "256"))
    PRG32_BUILD_ROOT_MAX_MB = int(os.environ.get("PRG32_BUILD_ROOT_MAX_MB", "4096"))
    PRG32_BUILD_TIMEOUT = float(os.environ.get("PRG32_BUILD_TIMEOUT", "120"))
    # Debug information for the Player's source and block debugger (ADR-0015): "0" turns it off.
    PRG32_DEBUG_INFO = os.environ.get("PRG32_DEBUG_INFO", "1") != "0"
    # How many saved versions (revisions) the History menu keeps per project.
    PRG32_KIT_MAX_REVISIONS = int(os.environ.get("PRG32_KIT_MAX_REVISIONS", "50"))
    # Storage policy (ADR-0017). 0 = no limit.
    PRG32_KIT_QUOTA_PROJECTS = int(os.environ.get("PRG32_KIT_QUOTA_PROJECTS", "200"))
    PRG32_KIT_QUOTA_MB = int(os.environ.get("PRG32_KIT_QUOTA_MB", "200"))
    PRG32_KIT_AUTOSAVE_SNAPSHOT_MINUTES = int(os.environ.get("PRG32_KIT_AUTOSAVE_SNAPSHOT_MINUTES", "10"))
    PRG32_KIT_TRASH_DAYS = int(os.environ.get("PRG32_KIT_TRASH_DAYS", "30"))
    PRG32_KIT_KEEP_BUILDS = int(os.environ.get("PRG32_KIT_KEEP_BUILDS", "10"))
    # ADR-0022: how long the audit log and backups are kept (docs/privacy/retention.md).
    PRG32_KIT_AUDIT_DAYS = int(os.environ.get("PRG32_KIT_AUDIT_DAYS", "365"))
    PRG32_KIT_BACKUP_DAYS = int(os.environ.get("PRG32_KIT_BACKUP_DAYS", "35"))
    # Closed rights requests are removed this many days after they were answered; 0 keeps them.
    # The period is the controller's decision (docs/privacy/decisions.md D-5).
    PRG32_KIT_PRIVACY_REQUEST_DAYS = int(os.environ.get("PRG32_KIT_PRIVACY_REQUEST_DAYS", "0"))
    # Shown on /privacy: who runs this kit (the controller) and where to send privacy requests.
    PRG32_PRIVACY_CONTROLLER = os.environ.get("PRG32_PRIVACY_CONTROLLER", "")
    PRG32_PRIVACY_CONTACT = os.environ.get("PRG32_PRIVACY_CONTACT", "")
    # "local": the sign-in page offers "Try without an account" (this browser only); "off": it does not.
    PRG32_GUEST_MODE = os.environ.get("PRG32_GUEST_MODE", "local")
    # Off (default): anyone may open the kit and make games kept in their own browser; building,
    # publishing and classes still need a sign-in (ADR-0023). On: every page needs a sign-in.
    LOGIN_REQUIRED = _flag("PRG32_KIT_LOGIN_REQUIRED", False)
    # Maintenance mode: only admins can use the kit; everybody else sees the message.
    MAINTENANCE_MODE = _flag("PRG32_KIT_MAINTENANCE", False)
    MAINTENANCE_MESSAGE = os.environ.get("PRG32_KIT_MAINTENANCE_MESSAGE",
                                         "The kit is being updated. Please come back in a few minutes.")
    # Appearance (docs/admin_settings.md). Skins are static/css/themes/<skin>.css.
    SITE_NAME = os.environ.get("PRG32_KIT_SITE_NAME", "PRG32-Construction-Kit")
    WELCOME_TEXT = os.environ.get("PRG32_KIT_WELCOME_TEXT", "")
    COLOR_SCHEME = os.environ.get("PRG32_KIT_COLOR_SCHEME", "light")
    SKIN = os.environ.get("PRG32_KIT_SKIN", "classic")
    MAX_CONTENT_LENGTH = int(os.environ.get("PRG32_KIT_MAX_UPLOAD", str(32 * 1024 * 1024)))
    JSON_SORT_KEYS = False

    # Sign-in cookie. The name differs from Cartridge Store's, so both can run on one host.
    SESSION_COOKIE_NAME = "prg32_kit_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _flag("PRG32_KIT_SECURE_COOKIES", False)
    PERMANENT_SESSION_LIFETIME = int(os.environ.get("PRG32_KIT_SESSION_HOURS", "12")) * 3600
    # Send the session cookie only when the session changed. Otherwise every response re-sends
    # it, and a slow request that started earlier (a page's API calls) can overwrite a newer
    # cookie, such as the one holding a school sign-in or cloud connection flow. Sessions still
    # end PERMANENT_SESSION_LIFETIME after sign-in: auth checks the signed-in time.
    SESSION_REFRESH_EACH_REQUEST = False

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
    # The kit's public address (https://kit.school.example), used for school sign-in redirect
    # addresses so they never depend on the Host header a request arrives with (ADR-0016).
    PUBLIC_URL = os.environ.get("PRG32_KIT_PUBLIC_URL", "")
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
