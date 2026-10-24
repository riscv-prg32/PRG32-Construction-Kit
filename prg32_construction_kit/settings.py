"""Settings an admin can change on the Settings page, without restarting the kit.

Every setting has a default in ``config.Config``, usually read from an environment
variable. An admin can store a different value in the database (table ``site_settings``).
Which value counts, in this order:

1. the environment variable, when the server sets it: the setting is then *locked* and the
   Settings page shows it read-only ("set by PRG32_... on the server"), so a deployment
   (Docker, examples/deploy/) always gets what its files say;
2. otherwise the value saved on the Settings page;
3. otherwise the default (``app.config``, which also holds a test's own configuration).

Every value is read when it is needed, never copied at start-up. Each process keeps a small
copy of the table and re-reads it when it changed (checked at most every two seconds), so
all the server's worker processes follow a change without a restart.

Secrets (the SMTP password, the Store single sign-on secret) are stored encrypted
(``secrets_at_rest``) and never sent back to the browser: the page only learns whether one
is set. Settings that decide how the server itself runs (secret key, data folders, the build
sandbox, proxies) are not here: they stay in the environment (docs/admin_settings.md).
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.orm import Mapped, mapped_column

from .db import db, utcnow


class SiteSetting(db.Model):
    """One value saved on the Settings page (the key is the Config name, e.g. ALLOW_REGISTRATION).

    Who changed it is in the audit log (settings_update), not here: the table holds no person.
    """
    __tablename__ = "site_settings"
    key: Mapped[str] = mapped_column(db.Text, primary_key=True)
    value: Mapped[str] = mapped_column(db.Text, nullable=False)          # JSON; a secret is a sealed string
    updated_at: Mapped[str] = mapped_column(db.Text, nullable=False)
    # Grows with every save across the table: other processes notice a change by it.
    revision: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)


@dataclass(frozen=True)
class Setting:
    key: str                 # the name in config.Config and in app.config
    env: str                 # the environment variable that locks it
    group: str               # the tab on the Settings page
    kind: str                # bool, int, float, str, text, choice, secret, url, list
    label: str
    help: str = ""
    choices: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    # Shown with its effect: a change applies on the next request unless this says otherwise.
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


GROUPS = (
    ("access", "Access"),
    ("maintenance", "Maintenance"),
    ("signin", "Sign-in"),
    ("email", "Email"),
    ("appearance", "Appearance"),
    ("classroom", "Classroom"),
    ("privacy", "Privacy"),
    ("store", "Store & cloud"),
    ("build", "Build limits"),
)

SKINS = ("prg32", "classic", "ocean", "forest", "contrast")
COLOR_SCHEMES = ("light", "dark", "auto")

REGISTRY: tuple[Setting, ...] = (
    # --- access -------------------------------------------------------------------------
    Setting("LOGIN_REQUIRED", "PRG32_KIT_LOGIN_REQUIRED", "access", "bool", "Sign-in required for every page",
            "Off: anyone can open the kit and make games kept in their own browser; building a cartridge, "
            "publishing and classes still need a sign-in. On: every page asks for a sign-in first."),
    Setting("PRG32_GUEST_MODE", "PRG32_GUEST_MODE", "access", "choice", "Games without an account",
            "local: visitors without an account can make games kept only in their browser. off: they cannot.",
            choices=("local", "off")),
    Setting("ALLOW_REGISTRATION", "PRG32_KIT_ALLOW_REGISTRATION", "access", "bool", "New users can create an account",
            "Off: only an admin creates accounts (Users page), or school sign-in does."),
    Setting("REQUIRE_EMAIL_DOMAIN", "PRG32_KIT_REQUIRE_EMAIL_DOMAIN", "access", "str", "Required email domain",
            "Only addresses ending in this domain may register, e.g. school.example. Empty: any."),
    Setting("DEFAULT_ROLE", "PRG32_KIT_DEFAULT_ROLE", "access", "choice", "Role of a new account",
            choices=("reader", "user", "publisher")),
    # --- maintenance --------------------------------------------------------------------
    Setting("MAINTENANCE_MODE", "PRG32_KIT_MAINTENANCE", "maintenance", "bool", "Maintenance mode",
            "On: only admins can use the kit; everybody else sees the message below. Sign-in, the privacy "
            "page and the docs stay open."),
    Setting("MAINTENANCE_MESSAGE", "PRG32_KIT_MAINTENANCE_MESSAGE", "maintenance", "text", "Maintenance message"),
    # --- sign-in ------------------------------------------------------------------------
    Setting("PUBLIC_URL", "PRG32_KIT_PUBLIC_URL", "signin", "url", "Public address of the kit",
            "e.g. https://kit.school.example: used for school sign-in and cloud return addresses."),
    Setting("SSO_PEER_URL", "PRG32_SSO_PEER_URL", "signin", "url", "Cartridge Store for single sign-on",
            "The Store whose accounts are shared with this kit. Empty: no single sign-on."),
    Setting("SSO_SECRET", "PRG32_SSO_SECRET", "signin", "secret", "Single sign-on shared secret",
            "The same long secret as PRG32_SSO_SECRET in the Cartridge Store (at least 32 characters)."),
    Setting("SSO_TIMEOUT", "PRG32_SSO_TIMEOUT", "signin", "float", "Single sign-on timeout (seconds)",
            minimum=1, maximum=60),
    # --- email --------------------------------------------------------------------------
    Setting("SMTP_HOST", "PRG32_SMTP_HOST", "email", "str", "SMTP server",
            "Empty: no mail is sent; sign-up links are written to the server log instead."),
    Setting("SMTP_PORT", "PRG32_SMTP_PORT", "email", "int", "SMTP port", minimum=1, maximum=65535),
    Setting("SMTP_FROM", "PRG32_SMTP_FROM", "email", "str", "Sender address"),
    Setting("SMTP_USER", "PRG32_SMTP_USER", "email", "str", "SMTP user name", "Empty: no login."),
    Setting("SMTP_PASSWORD", "PRG32_SMTP_PASSWORD", "email", "secret", "SMTP password"),
    Setting("SMTP_TLS", "PRG32_SMTP_TLS", "email", "bool", "Use STARTTLS"),
    # --- appearance ---------------------------------------------------------------------
    Setting("SITE_NAME", "PRG32_KIT_SITE_NAME", "appearance", "str", "Site name",
            "Shown in the menu bar and the browser tab."),
    Setting("WELCOME_TEXT", "PRG32_KIT_WELCOME_TEXT", "appearance", "text", "Welcome text",
            "Shown on the Projects page under the title. Empty: the kit's own text."),
    Setting("COLOR_SCHEME", "PRG32_KIT_COLOR_SCHEME", "appearance", "choice", "Colour scheme",
            "auto follows each computer's light or dark setting.", choices=COLOR_SCHEMES),
    Setting("SKIN", "PRG32_KIT_SKIN", "appearance", "choice", "Skin",
            "prg32: the PRG32 logo's colours; classic: navy and gold; ocean: blue and teal; forest: green; "
            "contrast: high contrast.",
            choices=SKINS),
    # --- classroom ----------------------------------------------------------------------
    Setting("PRG32_KIT_QUOTA_PROJECTS", "PRG32_KIT_QUOTA_PROJECTS", "classroom", "int", "Projects per user",
            "0: no limit.", minimum=0, maximum=100000),
    Setting("PRG32_KIT_QUOTA_MB", "PRG32_KIT_QUOTA_MB", "classroom", "int", "Storage per user (MB)",
            "0: no limit.", minimum=0, maximum=1000000),
    Setting("PRG32_KIT_MAX_REVISIONS", "PRG32_KIT_MAX_REVISIONS", "classroom", "int", "Saved versions per project",
            minimum=1, maximum=1000),
    Setting("PRG32_KIT_AUTOSAVE_SNAPSHOT_MINUTES", "PRG32_KIT_AUTOSAVE_SNAPSHOT_MINUTES", "classroom", "int",
            "Minutes between autosave versions", minimum=1, maximum=1440),
    Setting("PRG32_KIT_TRASH_DAYS", "PRG32_KIT_TRASH_DAYS", "classroom", "int", "Days in Recently deleted",
            minimum=1, maximum=3650),
    Setting("PRG32_KIT_KEEP_BUILDS", "PRG32_KIT_KEEP_BUILDS", "classroom", "int", "Builds kept per project",
            minimum=1, maximum=1000),
    # --- privacy ------------------------------------------------------------------------
    Setting("PRG32_PRIVACY_CONTROLLER", "PRG32_PRIVACY_CONTROLLER", "privacy", "str", "Who runs this kit",
            "The school or organisation responsible for the personal data (shown on /privacy)."),
    Setting("PRG32_PRIVACY_CONTACT", "PRG32_PRIVACY_CONTACT", "privacy", "str", "Privacy contact email"),
    Setting("PRG32_KIT_AUDIT_DAYS", "PRG32_KIT_AUDIT_DAYS", "privacy", "int", "Days the audit log is kept",
            minimum=1, maximum=3650),
    Setting("PRG32_KIT_BACKUP_DAYS", "PRG32_KIT_BACKUP_DAYS", "privacy", "int", "Days backups are kept",
            minimum=1, maximum=3650),
    Setting("PRG32_KIT_PRIVACY_REQUEST_DAYS", "PRG32_KIT_PRIVACY_REQUEST_DAYS", "privacy", "int",
            "Days answered privacy requests are kept", "0: keep them.", minimum=0, maximum=3650),
    # --- store & cloud ------------------------------------------------------------------
    Setting("DEFAULT_STORE_URL", "PRG32_STORE_URL", "store", "url", "Cartridge Store address",
            "Allowed for publishing. Existing publish profiles keep their own address."),
    Setting("STORE_ALLOWED_ORIGINS", "PRG32_STORE_ALLOWED_ORIGINS", "store", "list", "Other allowed Stores",
            "Comma-separated https://host addresses publishing may also use."),
    Setting("STORE_TRUSTED_LOCAL", "PRG32_STORE_TRUSTED_LOCAL", "store", "bool", "Store on the school network",
            "On: the Store may be on a private or loopback address."),
    Setting("STORE_TOKEN_MAX_DAYS", "PRG32_STORE_TOKEN_MAX_DAYS", "store", "int", "Maximum age of a Store token (days)",
            "0: no limit.", minimum=0, maximum=3650),
    Setting("CLOUD_GOOGLE_ENABLED", "PRG32_CLOUD_GOOGLE_ENABLED", "store", "bool", "Google Drive copies",
            "Needs PRG32_CLOUD_GOOGLE_CLIENT_ID and _SECRET on the server."),
    Setting("CLOUD_ONEDRIVE_ENABLED", "PRG32_CLOUD_ONEDRIVE_ENABLED", "store", "bool", "OneDrive copies",
            "Needs PRG32_CLOUD_ONEDRIVE_CLIENT_ID and _SECRET on the server."),
    Setting("CLOUD_GITHUB_ENABLED", "PRG32_CLOUD_GITHUB_ENABLED", "store", "bool", "GitHub repositories",
            "Projects committed to a student's GitHub repository. Needs PRG32_CLOUD_GITHUB_CLIENT_ID, _SECRET and "
            "_APP_SLUG on the server (docs/github.md)."),
    # --- build limits -------------------------------------------------------------------
    Setting("PRG32_MAX_PARALLEL_BUILDS", "PRG32_MAX_PARALLEL_BUILDS", "build", "int", "Builds at the same time",
            minimum=1, maximum=256),
    Setting("PRG32_BUILD_QUEUE_TIMEOUT", "PRG32_BUILD_QUEUE_TIMEOUT", "build", "float",
            "Seconds a build waits for a free slot", minimum=1, maximum=3600),
    Setting("PRG32_BUILD_TIMEOUT", "PRG32_BUILD_TIMEOUT", "build", "float", "Seconds one compile may take",
            minimum=5, maximum=3600),
    Setting("PRG32_BUILD_MEMORY_MB", "PRG32_BUILD_MEMORY_MB", "build", "int", "Memory per build (MB)",
            minimum=256, maximum=65536),
    Setting("PRG32_BUILD_MAX_PROCESSES", "PRG32_BUILD_MAX_PROCESSES", "build", "int", "Processes per build",
            minimum=16, maximum=4096),
    Setting("PRG32_BUILD_MAX_MB", "PRG32_BUILD_MAX_MB", "build", "int", "Disk per build (MB)",
            minimum=16, maximum=65536),
    Setting("PRG32_BUILD_ROOT_MAX_MB", "PRG32_BUILD_ROOT_MAX_MB", "build", "int", "Disk for all builds (MB)",
            "0: no total limit.", minimum=0, maximum=10485760),
    Setting("PRG32_CART_RAM_KIB", "PRG32_CART_RAM_KIB", "build", "int", "Cartridge RAM (KiB)", minimum=16, maximum=512),
    Setting("PRG32_DEBUG_INFO", "PRG32_DEBUG_INFO", "build", "bool", "Debug information for the Player's debugger"),
)

BY_KEY = {setting.key: setting for setting in REGISTRY}

# Shown read-only on the Settings page: they decide how the server itself runs.
ENVIRONMENT_ONLY = (
    ("SECRET_KEY", "signs sign-in cookies and encrypts stored secrets"),
    ("PRG32_KIT_DATA", "where projects, builds and the database are kept"),
    ("PRG32_KIT_ENV", "production or development safety checks"),
    ("PRG32_BUILD_SANDBOX", "how builds are isolated (bubblewrap)"),
    ("PRG32_BUILD_COMMAND", "the PRG32 toolchain command"),
    ("PRG32_KIT_PROXY_COUNT", "trusted reverse proxies"),
    ("PRG32_KIT_THROTTLE_*", "sign-in attempt limits"),
    ("PRG32_SAML_*", "SAML sign-in (its routes are made at start-up)"),
    ("PRG32_CLOUD_*_CLIENT_ID / _SECRET", "cloud storage and GitHub app credentials"),
)

_SECRET_PURPOSE = b"site-settings"
_REFRESH_SECONDS = 2.0


class SettingRefused(ValueError):
    """A value the Settings page refuses (wrong type, out of range, locked)."""


# --- reading ------------------------------------------------------------------------------

def locked(key: str) -> bool:
    """True when the server's environment sets this setting (it cannot be changed on the page)."""
    value = os.environ.get(BY_KEY[key].env)
    return value is not None and value.strip() != ""


def _cache() -> dict[str, Any]:
    return current_app.extensions.setdefault("prg32_settings", {"stamp": None, "checked": 0.0, "rows": {}})


def _stored() -> dict[str, Any]:
    """The values saved on the Settings page (decoded JSON), re-read when the table changed."""
    cache = _cache()
    now = time.monotonic()
    if current_app.config.get("TESTING") or now - cache["checked"] >= _REFRESH_SECONDS:
        cache["checked"] = now
        stamp = tuple(db.session.execute(select(func.max(SiteSetting.revision), func.count(SiteSetting.key))).one())
        if stamp != cache["stamp"]:
            rows = db.session.scalars(select(SiteSetting)).all()
            cache["rows"] = {row.key: json.loads(row.value) for row in rows}
            cache["stamp"] = stamp
    return cache["rows"]


def get(key: str) -> Any:
    """The value of a setting now: environment, else the Settings page, else the default."""
    setting = BY_KEY[key]
    if not locked(key):
        stored = _stored()
        if key in stored:
            value = stored[key]
            if setting.kind == "secret":
                from .secrets_at_rest import unseal

                return unseal(value, purpose=_SECRET_PURPOSE) or ""
            return value
    return current_app.config.get(key)


class SettingsView(Mapping):
    """``app.config`` as it is now: the settings of this page through ``get``, the rest as they are.

    For code that takes a whole configuration (store_policy, build_sandbox, retention, ...).
    """

    def __getitem__(self, key: str) -> Any:
        if key in BY_KEY:
            return get(key)
        return current_app.config[key]

    def __iter__(self) -> Iterator[str]:
        return iter(current_app.config)

    def __len__(self) -> int:
        return len(current_app.config)


def view() -> SettingsView:
    return SettingsView()


def describe() -> list[dict[str, Any]]:
    """Every setting for the Settings page: value, default, locked or not. Secrets say only if set."""
    stored = _stored()
    result = []
    for setting in REGISTRY:
        is_locked = locked(setting.key)
        default = current_app.config.get(setting.key)
        value = get(setting.key)
        item = {"key": setting.key, "env": setting.env, "group": setting.group, "kind": setting.kind,
                "label": setting.label, "help": setting.help, "choices": list(setting.choices),
                "minimum": setting.minimum, "maximum": setting.maximum, "locked": is_locked,
                "changed": setting.key in stored and not is_locked}
        if setting.kind == "secret":
            item["set"] = bool(value)
        else:
            item["value"] = value
            item["default"] = default
        result.append(item)
    return result


# --- changing -----------------------------------------------------------------------------

def _clean(setting: Setting, value: Any) -> Any:
    """Check one value from the Settings page and turn it into its stored form."""
    kind = setting.kind
    if kind == "bool":
        if not isinstance(value, bool):
            raise SettingRefused(f"{setting.label}: must be on or off")
        return value
    if kind in ("int", "float"):
        try:
            number = int(value) if kind == "int" else float(value)
        except (TypeError, ValueError):
            raise SettingRefused(f"{setting.label}: must be a number") from None
        if isinstance(value, bool):
            raise SettingRefused(f"{setting.label}: must be a number")
        if setting.minimum is not None and number < setting.minimum:
            raise SettingRefused(f"{setting.label}: at least {setting.minimum:g}")
        if setting.maximum is not None and number > setting.maximum:
            raise SettingRefused(f"{setting.label}: at most {setting.maximum:g}")
        return number
    if kind == "choice":
        if value not in setting.choices:
            raise SettingRefused(f"{setting.label}: one of {', '.join(setting.choices)}")
        return value
    if kind == "list":
        items = value if isinstance(value, list) else str(value or "").split(",")
        cleaned = [str(item).strip() for item in items if str(item).strip()]
        for item in cleaned:
            if not item.startswith(("https://", "http://")) or any(ch.isspace() for ch in item):
                raise SettingRefused(f"{setting.label}: {item!r} is not a web address")
        return cleaned or None
    if not isinstance(value, str):
        raise SettingRefused(f"{setting.label}: must be text")
    limit = 2000 if kind == "text" else 300
    if len(value) > limit:
        raise SettingRefused(f"{setting.label}: at most {limit} characters")
    if kind != "text" and any(ch in value for ch in "\r\n"):
        raise SettingRefused(f"{setting.label}: one line only")
    value = value.strip()
    if kind == "url" and value and (not value.startswith(("https://", "http://")) or " " in value):
        raise SettingRefused(f"{setting.label}: must start with https:// or http://")
    if kind == "secret":
        if setting.key == "SSO_SECRET" and value and len(value) < 32:
            raise SettingRefused(f"{setting.label}: at least 32 characters")
        from .secrets_at_rest import seal

        return seal(value, purpose=_SECRET_PURPOSE)
    return value


def update(changes: dict[str, Any]) -> list[str]:
    """Save values from the Settings page. ``None`` means "back to the default".

    All or nothing: one refused value refuses the whole change. Returns the changed keys.
    """
    cleaned: dict[str, Any] = {}
    for key, value in changes.items():
        setting = BY_KEY.get(key)
        if setting is None:
            raise SettingRefused(f"unknown setting {key!r}")
        if locked(key):
            raise SettingRefused(f"{setting.label} is set by {setting.env} on the server")
        cleaned[key] = None if value is None else _clean(setting, value)
    now = utcnow()
    revision = (db.session.scalar(select(func.max(SiteSetting.revision))) or 0) + 1
    for key, value in cleaned.items():
        row = db.session.get(SiteSetting, key)
        if value is None:
            if row is not None:
                db.session.delete(row)
            continue
        if row is None:
            row = SiteSetting(key=key, value="", updated_at=now)
            db.session.add(row)
        row.value = json.dumps(value)
        row.updated_at = now
        row.revision = revision
    db.session.commit()
    _cache()["checked"] = 0.0     # this process sees the change at once
    _cache()["stamp"] = None
    return sorted(cleaned)


# --- the Settings page and its API (admins only) -------------------------------------------

from email.message import EmailMessage  # noqa: E402 - the page's own imports, after the model

from flask import Blueprint, jsonify, render_template, request  # noqa: E402

bp = Blueprint("site_settings", __name__)


def _admin_or_refusal():
    from .auth import auth_failure, current_principal

    principal = current_principal()
    if not principal.authenticated:
        return principal, auth_failure("Please sign in first", 401)
    if not principal.is_admin:
        return principal, auth_failure("Only an admin can change the kit's settings", 403)
    return principal, None


@bp.get("/admin/settings")
def settings_page():
    _principal, refused = _admin_or_refusal()
    if refused:
        return refused
    return render_template("admin_settings.html", groups=GROUPS, environment_only=ENVIRONMENT_ONLY)


@bp.get("/api/admin/settings")
def api_settings():
    _principal, refused = _admin_or_refusal()
    if refused:
        return refused
    return jsonify({"groups": [{"id": key, "label": label} for key, label in GROUPS], "settings": describe(),
                    "environment_only": [{"name": name, "why": why} for name, why in ENVIRONMENT_ONLY]})


@bp.put("/api/admin/settings")
def api_update_settings():
    from . import security

    _principal, refused = _admin_or_refusal()
    if refused:
        return refused
    payload = request.get_json(silent=True) or {}
    changes = payload.get("settings")
    if not isinstance(changes, dict) or not changes:
        return jsonify({"error": "send {\"settings\": {NAME: value, ...}}"}), 400
    try:
        keys = update(changes)
    except SettingRefused as error:
        return jsonify({"error": str(error)}), 400
    # Names only: values may be secrets or personal (a contact address).
    security.record("settings_update", target_type="settings", metadata={"keys": ",".join(keys)})
    return jsonify({"changed": keys, "settings": describe()})


@bp.post("/api/admin/settings/smtp_test")
def api_smtp_test():
    """Send a test mail to the signed-in admin with the current Email settings."""
    import smtplib

    from . import security
    from .auth import User, _smtp_send

    principal, refused = _admin_or_refusal()
    if refused:
        return refused
    user = db.session.get(User, principal.id)
    address = (user.email if user else "") or ""
    if not address:
        return jsonify({"error": "Your account has no email address to send the test to"}), 400
    if not str(get("SMTP_HOST") or "").strip():
        return jsonify({"error": "No SMTP server is set"}), 400
    message = EmailMessage()
    message["From"] = get("SMTP_FROM")
    message["To"] = address
    message["Subject"] = "PRG32-Construction-Kit test mail"
    message.set_content("This test mail shows that the kit can send email (sign-up links, sign-in notices).\n")
    if current_app.config.get("TESTING"):
        current_app.extensions["prg32_last_smtp_test"] = {"email": address}
    else:
        try:
            _smtp_send(message)
        except (OSError, smtplib.SMTPException) as error:
            security.record("settings_smtp_test", target_type="settings", outcome="failure")
            return jsonify({"error": f"The mail could not be sent: {error}"}), 502
    security.record("settings_smtp_test", target_type="settings")
    return jsonify({"sent_to": address})


# --- maintenance mode and what every page shows ----------------------------------------------

# Open during maintenance: signing in (so an admin can), the privacy page, docs, static files.
MAINTENANCE_OPEN = ("/auth/", "/static/", "/docs/", "/.well-known/", "/privacy", "/documentation",
                    "/service-worker.js", "/favicon.ico", "/api/privacy/notices")


def maintenance_gate():
    """Run after the sign-in guard: during maintenance only admins get past."""
    if not get("MAINTENANCE_MODE") or request.path.startswith(MAINTENANCE_OPEN):
        return None
    from .auth import current_principal, wants_json

    if current_principal().is_admin:
        return None
    message = get("MAINTENANCE_MESSAGE") or "The kit is being updated."
    if wants_json():
        return jsonify({"error": message, "code": "maintenance"}), 503
    return render_template("maintenance.html", message=message), 503


def init_app(app) -> None:
    app.register_blueprint(bp)
    app.before_request(maintenance_gate)

    @app.context_processor
    def inject_site() -> dict[str, Any]:
        scheme = get("COLOR_SCHEME")
        skin = get("SKIN") if get("SKIN") in SKINS else "prg32"
        return {"site": {"name": get("SITE_NAME") or "PRG32 Construction Kit", "welcome": get("WELCOME_TEXT") or "",
                         "color_scheme": scheme if scheme in COLOR_SCHEMES else "light",
                         "skin": skin, "skin_css": f"css/themes/{skin}.css",
                         "maintenance": bool(get("MAINTENANCE_MODE"))}}
