"""Accounts, sign-in and permissions for PRG32-Construction-Kit.

This follows the same model as PRG32 Cartridge Store so teachers only have to
learn it once:

- every person has a user account (username, email, password, role);
- roles go from ``reader`` to ``admin``; groups (like ``editors``) are labels;
- browsers sign in with a session cookie, scripts send an API token as
  ``Authorization: Bearer prg32_...`` (each token has scopes: read, write, build,
  publish, admin);
- beside the global role, which CartridgeStore shares, the kit gives every
  account an academic role (student, teacher, facilitator or service) and class
  memberships (classes.py); school sign-in keys accounts by issuer + subject
  (identity.py, ADR-0016);
- a session ends when the account's ``session_epoch`` changes (password, role,
  deactivation, "sign out everywhere") or after PRG32_KIT_SESSION_HOURS;
- the first start creates an ``admin`` account (password from
  ``PRG32_ADMIN_PASSWORD``, or ``password`` -- change it right away).

User sync with a Cartridge Store lives in ``sso.py``.
"""

from __future__ import annotations

import functools
import hashlib
import os
import re
import secrets
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any, Callable, Iterable

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import check_password_hash, generate_password_hash

from . import security
from .db import db, utcnow
from .sso_protocol import timestamp_now
from . import settings as site_settings

ROLE_LEVELS = {
    "reader": 0,
    "user": 1,
    "player": 1,
    "publisher": 2,
    "admin": 3,
}

# Kit-only academic roles (ADR-0016). Not synchronised with CartridgeStore.
KIT_ROLES = ("student", "teacher", "facilitator", "service")
# What an API token may do. A token made before scopes existed (scopes NULL) may do everything.
TOKEN_SCOPES = ("read", "write", "build", "publish", "admin")
DEFAULT_TOKEN_SCOPES = ("read", "write", "build")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 10


# --- tables -------------------------------------------------------------------

class User(db.Model):
    __tablename__ = "users"
    # Never reuse the id of a deleted user: projects remember their owner by id.
    __table_args__ = {"sqlite_autoincrement": True}
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(db.Text, nullable=False, unique=True)
    email: Mapped[str] = mapped_column(db.Text, nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(db.Text)
    role: Mapped[str] = mapped_column(db.Text, nullable=False, default="user")
    external_provider: Mapped[str | None] = mapped_column(db.Text)
    external_id: Mapped[str | None] = mapped_column(db.Text)
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)
    # Changed whenever the account changes; user sync uses it to keep the newest version.
    updated_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=timestamp_now)
    last_login: Mapped[str | None] = mapped_column(db.Text)
    # ADR-0016: academic role, deactivation, and the number that ends older sessions.
    kit_role: Mapped[str] = mapped_column(db.Text, nullable=False, default="student")
    disabled_at: Mapped[str | None] = mapped_column(db.Text)
    session_epoch: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    # ADR-0022: set while a restriction of processing applies (privacy.set_restricted).
    restricted_at: Mapped[str | None] = mapped_column(db.Text)


class ApiToken(db.Model):
    __tablename__ = "api_tokens"
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(db.Text, nullable=False, unique=True)
    label: Mapped[str] = mapped_column(db.Text, nullable=False, default="API token")
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)
    last_used: Mapped[str | None] = mapped_column(db.Text)
    scopes: Mapped[str | None] = mapped_column(db.Text)       # "read write build"; NULL = every scope
    expires_at: Mapped[str | None] = mapped_column(db.Text)


class Group(db.Model):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(db.Text, nullable=False, unique=True)
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)


class UserGroup(db.Model):
    __tablename__ = "user_groups"
    user_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)


class RegistrationToken(db.Model):
    __tablename__ = "registration_tokens"
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(db.Text, nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(db.Text, nullable=False, unique=True)
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)
    expires_at: Mapped[str] = mapped_column(db.Text, nullable=False)
    used_at: Mapped[str | None] = mapped_column(db.Text)


# --- who is asking ------------------------------------------------------------

@dataclass(frozen=True)
class Principal:
    name: str
    role: str
    authenticated: bool = False
    id: int | None = None
    email: str = ""
    groups: tuple[str, ...] = ()
    kit_role: str = "student"
    # None for a browser session; the token's scopes when the request came with an API token.
    token_scopes: tuple[str, ...] | None = None
    # ADR-0022: processing is restricted; the account may read and download, not change.
    restricted: bool = False

    @property
    def username(self) -> str:
        return self.name

    @property
    def is_teacher(self) -> bool:
        return self.authenticated and self.kit_role == "teacher"

    def has_scope(self, scope: str) -> bool:
        return self.token_scopes is None or scope in self.token_scopes

    @property
    def is_admin(self) -> bool:
        return self.authenticated and role_at_least(self.role, "admin")

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "username": self.name,
            "email": self.email,
            "role": self.role,
            "kit_role": self.kit_role,
            "groups": list(self.groups),
            "authenticated": self.authenticated,
        }


ANONYMOUS = Principal(name="anonymous", role="reader", authenticated=False)


def normalize_role(role: str) -> str:
    normalized = str(role or "").strip().lower()
    if normalized not in ROLE_LEVELS:
        raise ValueError(f"unknown role: {role!r}")
    return normalized


def role_at_least(actual: str, required: str) -> bool:
    return ROLE_LEVELS[normalize_role(actual)] >= ROLE_LEVELS[normalize_role(required)]


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def groups_for_user(user_id: int) -> tuple[str, ...]:
    rows = db.session.scalars(
        select(Group.name).join(UserGroup, UserGroup.group_id == Group.id).where(UserGroup.user_id == user_id).order_by(Group.name)
    ).all()
    return tuple(rows)


def principal_from_user(user: User | None, token_scopes: tuple[str, ...] | None = None) -> Principal:
    if user is None or user.disabled_at:
        return ANONYMOUS  # a deactivated account is nobody
    return Principal(
        id=int(user.id),
        name=user.username,
        email=user.email,
        role=normalize_role(user.role or "user"),
        authenticated=True,
        groups=groups_for_user(int(user.id)),
        kit_role=user.kit_role or "student",
        token_scopes=token_scopes,
        restricted=bool(user.restricted_at),
    )


def load_user(user_id: int) -> Principal:
    return principal_from_user(db.session.get(User, user_id))


def find_user_by_email(email: str) -> User | None:
    return db.session.scalar(select(User).where(User.email == normalize_email(email)))


def extract_token() -> str:
    header = str(request.headers.get("Authorization", "")).strip()
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return str(request.headers.get("X-PRG32-Token", "")).strip()


def authenticate_token(token: str) -> Principal:
    if not token:
        return ANONYMOUS
    row = db.session.scalar(select(ApiToken).where(ApiToken.token_hash == token_hash(token)))
    if row is None or (row.expires_at and row.expires_at <= utcnow()):
        return ANONYMOUS
    row.last_used = utcnow()
    db.session.commit()
    g.prg32_token_id = row.id      # for the audit of what the token did (guard_request)
    scopes = tuple(row.scopes.split()) if row.scopes is not None else None
    return principal_from_user(db.session.get(User, row.user_id), token_scopes=scopes)


def current_principal() -> Principal:
    principal = getattr(g, "prg32_principal", None)
    if principal is not None:
        return principal
    principal = ANONYMOUS
    user_id = session.get("user_id")
    if user_id is not None:
        try:
            principal = _session_principal(int(user_id))
        except (TypeError, ValueError):
            principal = ANONYMOUS
        if not principal.authenticated:
            # Deleted (perhaps on the synced Cartridge Store), deactivated, signed out
            # everywhere, or simply too old: this session is over.
            session.clear()
    if not principal.authenticated:
        principal = authenticate_token(extract_token())
        g.prg32_auth_by_token = principal.authenticated
    g.prg32_principal = principal
    return principal


def _session_principal(user_id: int) -> Principal:
    user = db.session.get(User, user_id)
    if user is None or user.disabled_at or user.kit_role == "service":
        return ANONYMOUS
    if session.get("epoch") != (user.session_epoch or 0):
        return ANONYMOUS
    started = session.get("signed_in_at")
    lifetime = int(current_app.config["PERMANENT_SESSION_LIFETIME"])
    if not isinstance(started, (int, float)) or datetime.now(timezone.utc).timestamp() - started > lifetime:
        return ANONYMOUS  # sessions end a fixed time after sign-in, however active they are
    return principal_from_user(user)


def end_sessions(user: User) -> None:
    """Every session of this account ends at its next request (ADR-0016)."""
    user.session_epoch = (user.session_epoch or 0) + 1


def wants_json() -> bool:
    if request.path.startswith("/api/") or request.is_json:
        return True
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json" and request.accept_mimetypes[best] > request.accept_mimetypes["text/html"]


def auth_failure(message: str, status: int):
    if wants_json():
        return jsonify({"error": message, "user": current_principal().as_dict()}), status
    if status == 401:
        return redirect(url_for("auth.login_form", next=request.full_path.rstrip("?")))
    return render_template("error.html", error=message), status


def login_required(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if current_principal().authenticated:
            return func(*args, **kwargs)
        return auth_failure("Please sign in first", 401)

    return wrapper


def admin_required(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        principal = current_principal()
        if not principal.authenticated:
            return auth_failure("Please sign in first", 401)
        if not principal.is_admin:
            return auth_failure("Only teachers with the admin role can do this", 403)
        return func(*args, **kwargs)

    return wrapper


# --- changing users -----------------------------------------------------------
# Every change goes through these functions so the synced Cartridge Store hears about it.

def _group_id(name: str) -> int:
    normalized = str(name).strip().lower()
    if not normalized:
        raise ValueError("group name is required")
    group = db.session.scalar(select(Group).where(Group.name == normalized))
    if group is None:
        group = Group(name=normalized)
        db.session.add(group)
        db.session.flush()
    return int(group.id)


def _write_groups(user_id: int, groups: Iterable[str]) -> None:
    db.session.execute(delete(UserGroup).where(UserGroup.user_id == user_id))
    for name in sorted({str(group).strip().lower() for group in groups if str(group).strip()}):
        db.session.add(UserGroup(user_id=user_id, group_id=_group_id(name)))


def unique_username(preferred: str, email: str, ignore_user_id: int | None = None) -> str:
    def taken(candidate: str) -> bool:
        statement = select(User.id).where(User.username == candidate)
        if ignore_user_id is not None:
            statement = statement.where(User.id != ignore_user_id)
        return db.session.scalar(statement) is not None

    for candidate in (preferred, email):
        if candidate and not taken(candidate):
            return candidate
    suffix = 2
    while taken(f"{email}-{suffix}"):
        suffix += 1
    return f"{email}-{suffix}"


def _check_password(password: str) -> None:
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")


def admin_count(excluding: int | None = None) -> int:
    statement = select(func.count()).select_from(User).where(User.role == "admin")
    if excluding is not None:
        statement = statement.where(User.id != excluding)
    return int(db.session.scalar(statement) or 0)


def _notify_sync(user: User | None = None, deleted_email: str | None = None, previous_email: str | None = None) -> None:
    from . import sso

    if user is not None:
        sso.user_changed(user, previous_email=previous_email)
    elif deleted_email:
        sso.user_deleted(deleted_email)


def create_user(username: str, email: str, password: str | None, *, role: str = "user",
                groups: Iterable[str] = (), sync: bool = True) -> User:
    email = normalize_email(email)
    username = str(username or email).strip()
    if not EMAIL_RE.fullmatch(email):
        raise ValueError("email must be valid")
    if not username:
        raise ValueError("username is required")
    if password:
        _check_password(password)
    if find_user_by_email(email) is not None or db.session.scalar(select(User.id).where(User.username == username)):
        raise ValueError("a user with the same name or email already exists")
    user = User(
        username=username,
        email=email,
        # Accounts made without a password can only sign in through single sign-on.
        password_hash=generate_password_hash(password) if password else None,
        role=normalize_role(role),
        updated_at=timestamp_now(),
    )
    db.session.add(user)
    db.session.flush()
    _write_groups(int(user.id), groups)
    db.session.commit()
    if sync:
        _notify_sync(user)
    return user


def update_user(user: User, *, username: str | None = None, email: str | None = None, password: str | None = None,
                role: str | None = None, groups: Iterable[str] | None = None, kit_role: str | None = None) -> User:
    previous_email = user.email
    if kit_role is not None:
        if kit_role not in KIT_ROLES:
            raise ValueError("academic role must be one of: " + ", ".join(KIT_ROLES))
        if kit_role != user.kit_role:
            end_sessions(user)
        user.kit_role = kit_role
    if email is not None:
        email = normalize_email(email)
        if not EMAIL_RE.fullmatch(email):
            raise ValueError("email must be valid")
        other = find_user_by_email(email)
        if other is not None and other.id != user.id:
            raise ValueError("another user already has that email")
        user.email = email
    if username is not None:
        username = username.strip()
        if not username:
            raise ValueError("username is required")
        if db.session.scalar(select(User.id).where(User.username == username, User.id != user.id)):
            raise ValueError("another user already has that username")
        user.username = username
    if password:
        _check_password(password)
        user.password_hash = generate_password_hash(password)
        end_sessions(user)
    if role is not None:
        role = normalize_role(role)
        if user.role == "admin" and role != "admin" and admin_count(excluding=user.id) == 0:
            raise ValueError("the last admin cannot be demoted")
        if role != user.role:
            end_sessions(user)
        user.role = role
    if groups is not None:
        _write_groups(int(user.id), groups)
    user.updated_at = timestamp_now()
    db.session.commit()
    if password and user.role == "admin":
        forget_bootstrap_password()
    _notify_sync(user, previous_email=previous_email if previous_email != user.email else None)
    return user


def delete_user(user: User) -> None:
    if user.role == "admin" and admin_count(excluding=user.id) == 0:
        raise ValueError("the last admin cannot be deleted")
    email = user.email
    db.session.delete(user)
    db.session.commit()
    _notify_sync(deleted_email=email)


def user_as_dict(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "groups": list(groups_for_user(int(user.id))),
        "kit_role": user.kit_role or "student",
        "disabled": bool(user.disabled_at),
        "disabled_at": user.disabled_at,
        "identities": identity_summaries(int(user.id)),
        "has_password": bool(user.password_hash),
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": user.last_login,
    }


def authenticate_local_user(username: str, password: str) -> Principal:
    name = str(username or "").strip()
    user = db.session.scalar(select(User).where((User.username == name) | (User.email == name.lower())))
    if user is None or not user.password_hash or user.disabled_at or user.kit_role == "service":
        return ANONYMOUS
    if not check_password_hash(user.password_hash, password or ""):
        return ANONYMOUS
    return principal_from_user(user)


def identity_summaries(user_id: int) -> list[dict[str, str]]:
    from .identity import identities_of

    return identities_of(user_id)


# Passwords nobody may use for the first admin on a production server.
WEAK_ADMIN_PASSWORDS = {"password", "admin", "administrator", "changeme", "change-me", "change-me-before-class",
                        "prg32", "prg32-admin", "letmein", "1234567890", "password123", "teacher"}
BOOTSTRAP_PASSWORD_FILE = "initial_admin_password"


class BootstrapError(RuntimeError):
    """The first admin cannot be created safely with this configuration."""


def bootstrap_password_path(app) -> Any:
    from pathlib import Path

    return Path(app.config["DATA_DIR"]) / BOOTSTRAP_PASSWORD_FILE


def weak_admin_password(password: str) -> bool:
    return len(password) < MIN_PASSWORD_LENGTH or password.strip().lower() in WEAK_ADMIN_PASSWORDS


def bootstrap_admin(app) -> str:
    """Create the first ``admin`` account, but only while there is no admin at all.

    Returns what happened: ``"exists"``, ``"environment"`` (password from
    PRG32_ADMIN_PASSWORD) or ``"generated"`` (a random password written to
    DATA_DIR/initial_admin_password, readable only by the server's user).

    - Renaming or deleting that account never brings it back: nothing happens
      once any admin exists, or while a user called ``admin`` exists.
    - There is no built-in well-known password. A weak PRG32_ADMIN_PASSWORD
      stops a production server (PRG32_KIT_ENV=production) from starting; in
      development it works with a warning.
    - Passwords are never logged.
    """
    if admin_count() > 0:
        return "exists"
    taken = db.session.scalar(select(User.id).where((User.username == "admin") | (User.email == "admin@localhost")))
    if taken is not None:
        return "exists"
    password = app.config.get("ADMIN_PASSWORD") or ""
    production = app.config.get("KIT_ENV") == "production"
    if password:
        weak = weak_admin_password(password)
        if weak and production:
            raise BootstrapError(
                "PRG32_ADMIN_PASSWORD is too short or a well-known password, so this production server will not "
                "create its first admin with it. Choose a long random password, or leave PRG32_ADMIN_PASSWORD "
                f"unset to get a random one in the data folder ({BOOTSTRAP_PASSWORD_FILE}).")
        if weak:
            app.logger.warning("INSECURE: the first admin uses a weak PRG32_ADMIN_PASSWORD. This is allowed only "
                               "because PRG32_KIT_ENV is not 'production'. Never expose this server to a network.")
        source = "environment"
    else:
        password = secrets.token_urlsafe(18)
        path = bootstrap_password_path(app)
        path.unlink(missing_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(password + "\n")
        app.logger.warning("Created the first admin account 'admin' with a random password. Read it from the file "
                           "%s in the data folder (PRG32_KIT_DATA), sign in, and change it on My account; the file "
                           "is deleted when you do.", BOOTSTRAP_PASSWORD_FILE)
        source, weak = "generated", False
    user = User(username="admin", email="admin@localhost", password_hash=generate_password_hash(password),
                role="admin", updated_at=timestamp_now())
    db.session.add(user)
    db.session.flush()
    _write_groups(int(user.id), ["editors"])
    db.session.commit()
    security.record("admin_bootstrap", target_type="user", target_id=user.id, actor=None,
                    metadata={"source": source, "weak": weak, "environment": app.config.get("KIT_ENV")})
    return source


def forget_bootstrap_password() -> None:
    """The random first-admin password file is not needed once an admin chose a password."""
    bootstrap_password_path(current_app).unlink(missing_ok=True)


def sign_in(principal: Principal) -> None:
    user = db.session.get(User, principal.id)
    if user is not None:
        user.last_login = utcnow()
        db.session.commit()
        note_new_address(user)
    session.clear()
    session["user_id"] = principal.id
    session["epoch"] = (user.session_epoch or 0) if user is not None else 0
    session["signed_in_at"] = datetime.now(timezone.utc).timestamp()
    session.permanent = True
    # ADR-0022: the account notice (and the class notice for class members) is shown at
    # sign-in until its current version has been shown once; remember that it was.
    from . import privacy
    from .classes import ClassMember

    if user is not None:
        privacy.record_notice(user.id, "account", "sign-in")
        if db.session.scalar(select(ClassMember.class_id).where(ClassMember.user_id == user.id)) is not None:
            privacy.record_notice(user.id, "classes", "sign-in")


def safe_next(default: str = "/") -> str:
    target = request.args.get("next") or request.form.get("next") or ""
    if target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return default


# --- registration links -------------------------------------------------------

def _create_registration_token(email: str) -> str:
    token = secrets.token_urlsafe(32)
    now = utcnow()
    for old in db.session.scalars(select(RegistrationToken).where(RegistrationToken.email == email,
                                                                  RegistrationToken.used_at.is_(None))):
        old.used_at = now
    expires = (datetime.now(timezone.utc) + timedelta(hours=24)).replace(microsecond=0).isoformat()
    db.session.add(RegistrationToken(email=email, token_hash=token_hash(token), expires_at=expires))
    db.session.commit()
    return token


def _load_registration_token(token: str) -> RegistrationToken | None:
    if not token:
        return None
    record = db.session.scalar(select(RegistrationToken).where(RegistrationToken.token_hash == token_hash(token),
                                                               RegistrationToken.used_at.is_(None)))
    if record is None or record.expires_at <= utcnow():
        return None
    return record


def _send_registration_email(email: str, link: str) -> None:
    config = site_settings.view()
    if config.get("TESTING"):
        current_app.extensions["prg32_last_registration"] = {"email": email, "link": link,
                                                            "token": link.rsplit("token=", 1)[-1]}
        return
    host = str(config.get("SMTP_HOST") or "").strip()
    if not host:
        current_app.logger.warning("No SMTP server is set (PRG32_SMTP_HOST); registration link for %s: %s", email, link)
        return
    message = EmailMessage()
    message["From"] = config["SMTP_FROM"]
    message["To"] = email
    message["Subject"] = "Finish your PRG32-Construction-Kit registration"
    message.set_content("Open this link to finish your PRG32-Construction-Kit registration:\n\n"
                        f"{link}\n\nThe link expires in 24 hours.\n")
    _smtp_send(message)


def _smtp_send(message: EmailMessage) -> None:
    config = site_settings.view()
    with smtplib.SMTP(str(config["SMTP_HOST"]).strip(), int(config["SMTP_PORT"]), timeout=10) as smtp:
        if config.get("SMTP_TLS", True):
            smtp.starttls()
        if config.get("SMTP_USER"):
            smtp.login(config["SMTP_USER"], config.get("SMTP_PASSWORD", ""))
        smtp.send_message(message)


# --- sign-ins from a new address (S-6, docs/privacy/breach_playbook.md) -----------------------

SIGN_IN_ACTIONS = ("login", "oidc_sign_in", "saml_sign_in")


def note_new_address(user: User) -> bool:
    """Called at sign-in, before this sign-in is logged. When the account has signed in before but
    never from this address (within the audit log's retention), log ``login_new_address`` and, if
    the kit can send email, tell the person: a stolen password then does not go unnoticed."""
    address = security.client_address()
    earlier = select(security.AuditEvent.id).where(security.AuditEvent.actor_id == user.id,
                                                    security.AuditEvent.action.in_(SIGN_IN_ACTIONS),
                                                    security.AuditEvent.outcome == "success")
    if not address or db.session.scalar(earlier.limit(1)) is None:
        return False                                   # the first sign-in: nothing to compare with
    if db.session.scalar(earlier.where(security.AuditEvent.client == address).limit(1)) is not None:
        return False
    security.record("login_new_address", target_type="user", target_id=user.id, actor=principal_from_user(user))
    config = site_settings.view()
    text = ("Your PRG32-Construction-Kit account was just signed in to from a computer or network it has not "
            "used before.\n\nIf it was you, there is nothing to do. If not, change your password at once "
            "(Account page) and tell your teacher.\n")
    if config.get("TESTING"):
        current_app.extensions["prg32_last_notice"] = {"email": user.email, "text": text}
    elif str(config.get("SMTP_HOST") or "").strip():
        message = EmailMessage()
        message["From"] = config["SMTP_FROM"]
        message["To"] = user.email
        message["Subject"] = "New sign-in to your PRG32-Construction-Kit account"
        message.set_content(text)
        try:
            _smtp_send(message)
        except (OSError, smtplib.SMTPException) as error:   # never stop a sign-in because mail failed
            current_app.logger.warning("could not send the new sign-in notice: %s", error)
    return True


# --- the request guard --------------------------------------------------------

# Pages and files anyone may open without signing in.
PUBLIC_PREFIXES = ("/auth/", "/static/", "/docs/", "/.well-known/")
PUBLIC_PATHS = {"/documentation", "/favicon.ico", "/api/sso/users", "/service-worker.js", "/privacy",
                "/api/privacy/notices"}
# Under /auth/ but only for a signed-in account (so API-token scopes apply to them too).
ACCOUNT_PATHS = ("/auth/tokens", "/auth/password", "/auth/sessions", "/auth/identities")


def required_scope(method: str, path: str) -> str:
    """The API-token scope a request needs (ADR-0016)."""
    if path.startswith(("/api/admin", "/api/users", "/admin/")):
        return "admin"
    if path.startswith("/api/publish"):
        return "publish"
    if method == "POST" and path.endswith(("/package", "/convert", "/check", "/run")):
        return "build"
    if method in ("GET", "HEAD", "OPTIONS"):
        return "read"
    return "write"


# The guest workspace (ADR-0023): without an account, these pages open and keep the games in the
# browser; only these APIs answer, and they store nothing (guest_api.py). Everything else, such as
# building a cartridge, publishing, classes and every saved resource, still asks for a sign-in.
GUEST_PAGES = re.compile(r"^/(|sprites|player|audio-studio|(ide|projects|audio-studio)/[A-Za-z0-9_-]{1,64})$")
GUEST_APIS = re.compile(r"^/api/(guest/.+|examples|starters/[a-z]+)$")


def guest_workspace_open() -> bool:
    """True when visitors without an account may use the kit (Settings: Access)."""
    return not site_settings.get("LOGIN_REQUIRED") and site_settings.get("PRG32_GUEST_MODE") == "local"


def guest_may(method: str, path: str) -> bool:
    if not guest_workspace_open():
        return False
    if GUEST_PAGES.match(path):
        return method in ("GET", "HEAD")
    if GUEST_APIS.match(path):
        read_only = path == "/api/examples" or path.startswith(("/api/guest/examples/", "/api/starters/"))
        return method in ("GET", "HEAD") if read_only else method == "POST"
    return False


def guard_request():
    """Run before every request: ask for a sign-in, and block cross-site form posts."""
    path = request.path
    if path in PUBLIC_PATHS or (path.startswith(PUBLIC_PREFIXES) and not path.startswith(ACCOUNT_PATHS)):
        return None
    principal = current_principal()
    if not principal.authenticated:
        if guest_may(request.method, path):
            return None
        return auth_failure("Please sign in first", 401)
    if principal.token_scopes is not None:
        needed = required_scope(request.method, path)
        if not principal.has_scope(needed) or path.startswith("/auth/password"):
            security.record("api_token_scope", target_type="route", target_id=path, outcome="denied",
                            metadata={"needed": needed, "method": request.method})
            return jsonify({"error": f"this API token does not have the {needed!r} scope",
                            "code": "insufficient_scope"}), 403
    if getattr(g, "prg32_auth_by_token", False):
        # S-5: every request made with an API token is in the audit log (method and path, never the
        # body or the query), so the extent of a leaked token's use can be established.
        security.record("api_token_use", target_type="api_token", target_id=getattr(g, "prg32_token_id", ""),
                        metadata={"method": request.method, "path": path[:200]})
    from .privacy import restriction_blocks

    if restriction_blocks(principal, request.method, path):
        return jsonify({"error": "Processing of this account is restricted (a privacy request): you can read and "
                                 "download your data, but not change, build or publish.",
                        "code": "restricted"}), 423
    if (request.method == "POST" and not getattr(g, "prg32_auth_by_token", False)
            and not request.is_json and request.headers.get("X-PRG32-Kit") != "1"):
        # A web page on another site can submit a plain form (always a POST) to
        # us with the student's cookie, but it cannot add this header or send a
        # JSON body; PUT and DELETE cannot be sent from another site at all.
        return jsonify({"error": "This request must come from the Construction Kit pages"}), 403
    opened_as = str(request.headers.get("X-PRG32-User", "")).strip()
    if opened_as and not getattr(g, "prg32_auth_by_token", False) and opened_as != str(principal.id):
        # One browser shares one sign-in cookie between all its windows. This
        # window was opened as another account, so saving or building now would
        # use the wrong student's account.
        return jsonify({"error": "Somebody signed in as a different user in another window of this browser. "
                                 "Reload this window before saving or compiling. To work as two users at once, "
                                 "use two browsers or a private window.",
                        "code": "user_changed"}), 409
    return None


# --- routes -------------------------------------------------------------------

bp = Blueprint("auth", __name__)


@bp.get("/auth/login")
def login_form():
    from . import auth_adapters, sso

    return render_template("auth_login.html", next=safe_next(""), sso=sso.status(),
                           external_logins=auth_adapters.enabled_logins(current_app),
                           guest_mode=site_settings.get("PRG32_GUEST_MODE"))


def too_many(error: security.Throttled, template: str | None = None, **context: Any):
    """429 with Retry-After. The same answer whether or not an account exists."""
    minutes = max(1, (error.retry_after + 59) // 60)
    message = f"Too many attempts. Wait {minutes} minute{'s' if minutes != 1 else ''} and try again, or ask your teacher."
    if wants_json() or template is None:
        response = jsonify({"error": message, "retry_after": error.retry_after})
    else:
        response = current_app.make_response(render_template(template, error=message, **context))
    response.status_code = 429
    response.headers["Retry-After"] = str(error.retry_after)
    return response


@bp.post("/auth/login")
def login():
    from . import auth_adapters, sso

    username = request.form.get("username", "")
    address = security.client_address()
    form_context = {"next": safe_next(""), "sso": sso.status(), "external_logins": auth_adapters.enabled_logins(current_app),
                    "guest_mode": site_settings.get("PRG32_GUEST_MODE")}
    try:
        # Failures are counted per address+name (so one student's typos lock only that name)
        # and, with a much larger limit, per address.
        security.check("login_user", address, username)
        security.check("login_address", address)
    except security.Throttled as error:
        security.record("login_throttled", target_type="user", outcome="denied", actor=None,
                        metadata={"limit": "login"})
        return too_many(error, "auth_login.html", **form_context)
    principal = authenticate_local_user(username, request.form.get("password", ""))
    if not principal.authenticated:
        security.hit("login_user", address, username)
        security.hit("login_address", address)
        # For incident investigation (docs/privacy/breach_playbook.md): when and from where. Never
        # what was typed: people sometimes type their password into the username field.
        known = db.session.scalar(select(User.id).where((User.username == username.strip())
                                                         | (User.email == username.strip().lower())))
        security.record("login_failed", target_type="user", target_id=known or "", outcome="denied", actor=None)
        if wants_json():
            return jsonify({"error": "invalid username or password"}), 401
        return render_template("auth_login.html", error="Invalid username or password.", **form_context), 401
    security.reset("login_user", address, username)
    sign_in(principal)
    security.record("login", target_type="user", target_id=principal.id, actor=principal)
    if wants_json():
        return jsonify({"ok": True, "user": principal.as_dict()})
    return redirect(safe_next())


@bp.post("/auth/logout")
def logout():
    """Sign out of the kit. With school sign-in this does NOT sign out of the school's
    identity provider (no front- or back-channel logout, ADR-0016): we say so."""
    school = session.get("auth_via")
    session.clear()
    if wants_json():
        return jsonify({"ok": True, "school_session_ended": False if school else None})
    if school:
        flash("You are signed out of the kit. Your school account may still be signed in on this browser: "
              "close the browser, or sign out on the school's sign-in page, on a shared computer.")
    return redirect(url_for("auth.login_form"))


@bp.get("/auth/me")
def me():
    from . import sso

    return jsonify({"ok": True, "auth_enabled": True, "user": current_principal().as_dict(), "sso": sso.status()})


@bp.get("/auth/register")
def register_form():
    return render_template("auth_register.html", allowed=site_settings.get("ALLOW_REGISTRATION"))


@bp.post("/auth/register")
def register():
    email = normalize_email(request.form.get("email", ""))
    errors = []
    if not EMAIL_RE.fullmatch(email):
        errors.append("email must be valid")
    if not site_settings.get("ALLOW_REGISTRATION"):
        errors.append("registration is closed; ask your teacher for an account")
    domain = str(site_settings.get("REQUIRE_EMAIL_DOMAIN") or "").lower().lstrip("@")
    if domain and not email.endswith("@" + domain):
        errors.append(f"email must belong to {domain}")
    if errors:
        if wants_json():
            return jsonify({"error": "; ".join(errors)}), 400
        return render_template("auth_register.html", errors=errors, allowed=site_settings.get("ALLOW_REGISTRATION")), 400
    try:
        security.check_and_hit("register_address", security.client_address())
        security.check_and_hit("register_email", email)
    except security.Throttled as error:
        return too_many(error, "auth_register.html", allowed=site_settings.get("ALLOW_REGISTRATION"))
    # Say the same thing whether or not the account exists, so nobody can test emails.
    if find_user_by_email(email) is None:
        token = _create_registration_token(email)
        _send_registration_email(email, url_for("auth.register_complete_form", token=token, _external=True))
    if wants_json():
        return jsonify({"ok": True, "email": email, "message": "registration email sent"})
    return render_template("auth_message.html", title="Check your email",
                           message=f"If {email} can register, a link to finish is on its way. It works for 24 hours.")


@bp.get("/auth/register/complete")
def register_complete_form():
    token = request.args.get("token", "")
    record = _load_registration_token(token)
    if record is None:
        return render_template("error.html", error="This registration link is invalid or expired."), 400
    return render_template("auth_register_complete.html", email=record.email, token=token)


@bp.post("/auth/register/complete")
def register_complete():
    token = request.form.get("token", "")
    address = security.client_address()
    try:
        security.check("register_complete", address)
    except security.Throttled as error:
        return too_many(error)
    record = _load_registration_token(token)
    if record is None:
        security.hit("register_complete", address)
        if wants_json():
            return jsonify({"error": "registration link is invalid or expired"}), 400
        return render_template("error.html", error="This registration link is invalid or expired."), 400
    password = request.form.get("password", "")
    errors = []
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if password != request.form.get("password_confirm", password):
        errors.append("password confirmation does not match")
    if errors:
        if wants_json():
            return jsonify({"error": "; ".join(errors)}), 400
        return render_template("auth_register_complete.html", email=record.email, token=token, errors=errors), 400
    record.used_at = utcnow()
    db.session.commit()
    if find_user_by_email(record.email) is not None:
        if wants_json():
            return jsonify({"error": "account already exists"}), 400
        return render_template("error.html", error="This account already exists. Sign in instead."), 400
    role = site_settings.get("DEFAULT_ROLE")
    user = create_user(unique_username(record.email, record.email), record.email, password, role=role)
    security.record("user_registered", target_type="user", target_id=user.id, actor=None,
                    metadata={"role": user.role})
    principal = principal_from_user(user)
    sign_in(principal)
    if wants_json():
        return jsonify({"ok": True, "user": principal.as_dict()})
    flash("Account created.")
    return redirect(safe_next())


@bp.get("/account")
@login_required
def account_page():
    from . import sso

    return render_template("account.html", sso=sso.status())


@bp.post("/auth/password")
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    user = db.session.get(User, current_principal().id)
    if user is None:
        return jsonify({"error": "account not found"}), 404
    if user.password_hash and not check_password_hash(user.password_hash, str(data.get("current_password", ""))):
        return jsonify({"error": "current password is wrong"}), 400
    update_user(user, password=str(data.get("new_password", "")) or None)
    security.record("password_change", target_type="user", target_id=user.id)
    sign_in(principal_from_user(user))  # this window stays signed in; every other session ends
    return jsonify({"ok": True})


@bp.post("/auth/sessions/revoke")
@login_required
def revoke_my_sessions():
    """Sign out everywhere: every session of this account ends, including this one."""
    user = db.session.get(User, current_principal().id)
    end_sessions(user)
    db.session.commit()
    security.record("sessions_revoke", target_type="user", target_id=user.id, metadata={"by": "self"})
    session.clear()
    return jsonify({"ok": True})


@bp.get("/auth/sessions/recent")
@login_required
def recent_sign_ins():
    """The person's own last sign-ins (S-6), so they can spot one that was not them."""
    me = current_principal().id
    rows = db.session.scalars(
        select(security.AuditEvent).where(
            ((security.AuditEvent.actor_id == me) & security.AuditEvent.action.in_(SIGN_IN_ACTIONS + ("login_new_address",)))
            | ((security.AuditEvent.action == "login_failed") & (security.AuditEvent.target_id == str(me))))
        .order_by(security.AuditEvent.id.desc()).limit(20)).all()
    return jsonify({"sign_ins": [{"at": row.created_at, "action": row.action, "outcome": row.outcome,
                                  "address": row.client} for row in rows]})


def _token_record(row: ApiToken) -> dict[str, Any]:
    return {"id": row.id, "label": row.label, "created_at": row.created_at, "last_used": row.last_used or "",
            "scopes": row.scopes.split() if row.scopes is not None else list(TOKEN_SCOPES),
            "expires_at": row.expires_at or ""}


def _requested_scopes(data: dict[str, Any], principal: Principal) -> list[str]:
    scopes = data.get("scopes", list(DEFAULT_TOKEN_SCOPES))
    if isinstance(scopes, str):
        scopes = scopes.split()
    if not isinstance(scopes, list) or not scopes or any(scope not in TOKEN_SCOPES for scope in scopes):
        raise ValueError("scopes must be a list of: " + ", ".join(TOKEN_SCOPES))
    if "admin" in scopes and not principal.is_admin:
        raise ValueError("only administrators can make tokens with the admin scope")
    if "publish" in scopes and not role_at_least(principal.role, "publisher"):
        raise ValueError("only publishers can make tokens with the publish scope")
    if principal.token_scopes is not None and not set(scopes) <= set(principal.token_scopes):
        raise ValueError("a token cannot make a token with more scopes than its own")
    return [scope for scope in TOKEN_SCOPES if scope in scopes]


@bp.get("/auth/tokens")
@login_required
def list_tokens():
    rows = db.session.scalars(select(ApiToken).where(ApiToken.user_id == current_principal().id)
                              .order_by(ApiToken.created_at.desc(), ApiToken.id.desc())).all()
    return jsonify({"ok": True, "tokens": [_token_record(row) for row in rows]})


@bp.post("/auth/tokens")
@login_required
def create_token():
    data = request.get_json(silent=True) or {}
    label = str(data.get("label") or request.form.get("label") or "API token").strip()[:80] or "API token"
    try:
        security.check_and_hit("token_create", current_principal().id)
    except security.Throttled as error:
        security.record("api_token_create", target_type="api_token", outcome="denied", metadata={"label": label})
        return too_many(error)
    scopes = _requested_scopes(data, current_principal())
    days = data.get("expires_in_days")
    if days is not None and (not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 3650):
        raise ValueError("expires_in_days must be a whole number of days from 1 to 3650")
    expires = ((datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat()
               if days else None)
    token = "prg32_" + secrets.token_urlsafe(32)
    row = ApiToken(user_id=current_principal().id, token_hash=token_hash(token), label=label,
                   scopes=" ".join(scopes), expires_at=expires)
    db.session.add(row)
    db.session.commit()
    security.record("api_token_create", target_type="api_token", target_id=row.id,
                    metadata={"label": label, "scopes": scopes, "expires_at": expires or ""})
    # The token is shown only now; the server keeps just its hash.
    return jsonify({"ok": True, "id": row.id, "label": label, "token": token, "scopes": scopes,
                    "expires_at": expires or ""}), 201


@bp.patch("/auth/tokens/<int:token_id>")
@login_required
def rename_token(token_id: int):
    data = request.get_json(silent=True) or {}
    label = str(data.get("label") or "").strip()[:80]
    if not label:
        return jsonify({"error": "label is required"}), 400
    row = db.session.scalar(select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == current_principal().id))
    if row is None:
        return jsonify({"error": "token not found"}), 404
    row.label = label
    db.session.commit()
    return jsonify({"ok": True, "id": token_id, "label": label})


@bp.delete("/auth/tokens/<int:token_id>")
@login_required
def revoke_token(token_id: int):
    result = db.session.execute(delete(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == current_principal().id))
    db.session.commit()
    security.record("api_token_revoke", target_type="api_token", target_id=token_id,
                    outcome="success" if result.rowcount else "not_found")
    return jsonify({"ok": result.rowcount > 0})


# --- teacher (admin) user management -----------------------------------------

@bp.get("/admin/users")
@admin_required
def admin_users_page():
    from . import sso

    return render_template("admin_users.html", roles=list(ROLE_LEVELS), sso=sso.status())


@bp.get("/api/users")
@admin_required
def api_list_users():
    users = db.session.scalars(select(User).order_by(User.created_at, User.id)).all()
    return jsonify({"users": [user_as_dict(user) for user in users], "roles": list(ROLE_LEVELS)})


def _groups_from(data: dict[str, Any]) -> list[str] | None:
    groups = data.get("groups")
    if groups is None:
        return None
    if isinstance(groups, str):
        groups = groups.split(",")
    if not isinstance(groups, list):
        raise ValueError("groups must be a list")
    return [str(group) for group in groups]


@bp.post("/api/users")
@admin_required
def api_create_user():
    data = request.get_json(silent=True) or {}
    kit_role = str(data.get("kit_role") or "student")
    if kit_role not in KIT_ROLES:
        raise ValueError("academic role must be one of: " + ", ".join(KIT_ROLES))
    user = create_user(str(data.get("username") or ""), str(data.get("email") or ""), str(data.get("password") or "") or None,
                       role=str(data.get("role") or "user"), groups=_groups_from(data) or [])
    if kit_role != "student":
        user.kit_role = kit_role
        db.session.commit()
    security.record("user_create", target_type="user", target_id=user.id,
                    metadata={"username": user.username, "role": user.role, "kit_role": user.kit_role,
                              "groups": list(groups_for_user(user.id))})
    return jsonify(user_as_dict(user)), 201


@bp.route("/api/users/<int:user_id>", methods=["GET", "PUT", "DELETE"])
@admin_required
def api_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "user not found"}), 404
    if request.method == "GET":
        return jsonify(user_as_dict(user))
    me = current_principal()
    if request.method == "DELETE":
        if user.id == me.id:
            return jsonify({"error": "you cannot delete your own account"}), 400
        username, role = user.username, user.role
        removed = None
        if request.args.get("with_items") in ("1", "true"):
            from .retention import delete_account_items

            removed = delete_account_items(user.id, current_app.config["BUILD_ROOT"])
        try:
            delete_user(user)
        except ValueError:
            security.record("user_delete", target_type="user", target_id=user_id, outcome="refused",
                            metadata={"username": username})
            raise
        security.record("user_delete", target_type="user", target_id=user_id,
                        metadata={"username": username, "role": role, "items_removed": removed or {}})
        return jsonify({"deleted": True, "id": user_id, "items_removed": removed or {}})
    data = request.get_json(silent=True) or {}
    if user.id == me.id and "role" in data and data["role"] != "admin":
        return jsonify({"error": "admins cannot demote themselves"}), 400
    before = {"username": user.username, "email": user.email, "role": user.role, "groups": list(groups_for_user(user.id))}
    if user.id == me.id and "kit_role" in data and data["kit_role"] != user.kit_role:
        return jsonify({"error": "you cannot change your own academic role"}), 400
    before["kit_role"] = user.kit_role
    update_user(
        user,
        username=str(data["username"]) if "username" in data else None,
        email=str(data["email"]) if "email" in data else None,
        password=str(data.get("password") or "") or None,
        role=str(data["role"]) if "role" in data else None,
        groups=_groups_from(data),
        kit_role=str(data["kit_role"]) if "kit_role" in data else None,
    )
    after = {"username": user.username, "email": user.email, "role": user.role, "groups": list(groups_for_user(user.id)),
             "kit_role": user.kit_role}
    changes = {f"{key}_before": before[key] for key in before if before[key] != after[key]}
    changes.update({f"{key}_after": after[key] for key in after if before[key] != after[key]})
    if data.get("password"):
        changes["credentials_changed"] = True  # that the password changed, never its value
    action = ("user_role_change" if "role_after" in changes
              else "user_kit_role_change" if "kit_role_after" in changes
              else "user_groups_change" if "groups_after" in changes else "user_update")
    security.record(action, target_type="user", target_id=user_id, metadata=changes)
    return jsonify(user_as_dict(user))


def _set_disabled(user_id: int, disabled: bool):
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "user not found"}), 404
    if user.id == current_principal().id:
        return jsonify({"error": "you cannot deactivate your own account"}), 400
    if disabled and user.role == "admin" and admin_count(excluding=user.id) == 0:
        return jsonify({"error": "the last admin cannot be deactivated"}), 400
    if disabled:
        user.disabled_at = user.disabled_at or utcnow()
        end_sessions(user)
        db.session.execute(delete(ApiToken).where(ApiToken.user_id == user.id))  # tokens stop working for good
    else:
        user.disabled_at = None
    db.session.commit()
    security.record("user_deactivate" if disabled else "user_reactivate", target_type="user", target_id=user.id,
                    metadata={"username": user.username})
    return jsonify(user_as_dict(user))


@bp.post("/api/users/<int:user_id>/deactivate")
@admin_required
def api_deactivate_user(user_id: int):
    """Deprovision: no sign-in, sessions end, API tokens are revoked; the account's items stay."""
    return _set_disabled(user_id, True)


@bp.post("/api/users/<int:user_id>/reactivate")
@admin_required
def api_reactivate_user(user_id: int):
    return _set_disabled(user_id, False)


@bp.post("/api/users/<int:user_id>/sessions/revoke")
@admin_required
def api_revoke_user_sessions(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "user not found"}), 404
    end_sessions(user)
    db.session.commit()
    security.record("sessions_revoke", target_type="user", target_id=user.id, metadata={"by": "admin"})
    return jsonify({"ok": True})


# --- teacher (admin) security tools ------------------------------------------

@bp.get("/api/admin/audit")
@admin_required
def api_audit_events():
    """The audit log, newest first. Optional: ?limit=100&action=user_create&before=<id>."""
    try:
        limit = int(request.args.get("limit", "100"))
        before = int(request.args["before"]) if request.args.get("before") else None
    except ValueError:
        return jsonify({"error": "limit and before must be whole numbers"}), 400
    return jsonify({"events": security.audit_events(limit, request.args.get("action") or None, before)})


@bp.delete("/api/admin/throttles")
@admin_required
def api_clear_throttles():
    """Unlock everybody at once (for example after a class mistyped the shared password)."""
    cleared = security.clear_all()
    security.record("throttles_clear", target_type="auth_throttle", metadata={"cleared": cleared})
    return jsonify({"ok": True, "cleared": cleared})


@bp.errorhandler(ValueError)
def handle_bad_value(exc: ValueError):
    if wants_json():
        return jsonify({"error": str(exc)}), 400
    return render_template("error.html", error=str(exc)), 400


_NEW_COLUMNS = {
    "users": {"kit_role": "TEXT NOT NULL DEFAULT 'student'", "disabled_at": "TEXT",
              "session_epoch": "INTEGER NOT NULL DEFAULT 0", "restricted_at": "TEXT"},
    "api_tokens": {"scopes": "TEXT", "expires_at": "TEXT"},
}


def migrate() -> None:
    """Add the ADR-0016 columns to databases made before them (idempotent)."""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    with db.engine.begin() as connection:
        for table, columns in _NEW_COLUMNS.items():
            present = {column["name"] for column in inspector.get_columns(table)}
            for name, kind in columns.items():
                if name not in present:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {kind}"))
    from .identity import migrate_legacy_identities

    migrate_legacy_identities()


def init_app(app) -> None:
    from . import auth_adapters

    with app.app_context():
        migrate()
    app.register_blueprint(bp)
    app.before_request(guard_request)

    @app.context_processor
    def inject_current_user() -> dict[str, Any]:
        from . import sso

        principal = current_principal()
        return {"current_user": principal, "sso_enabled": sso.enabled(),
                "guest_workspace": not principal.authenticated and guest_workspace_open()}

    auth_adapters.register(app)
