"""Personal data and the rights of the people it is about (docs/privacy/, ADR-0022).

The kit does not decide anything legal: the school or operator running it is the
controller (docs/privacy/roles_and_legal_bases.md). What the kit does is make the
rights workable and checkable:

- **Notices.** ``privacy_notices.json`` holds the short notice shown at each place the
  kit collects personal data, with a version. ``record_notice`` remembers which
  version each person was shown, and when.
- **Access and portability.** ``export_personal_data`` gathers every row about one
  person from every table, as one structured JSON document (not a project archive).
  Secrets (password hashes, token hashes, encrypted cloud tokens, Store tokens) are
  never exported: the document says they exist.
- **Requests.** ``privacy_requests`` is the register of rights requests: what was
  asked, by whom, when it is due (one month, Article 12(3)), who handled it and the
  outcome, including what failed.
- **Restriction.** A restricted account can still sign in, read and download its
  data, but the kit refuses every change, build, publication and cloud sync.
- **Erasure.** ``erase_account`` removes the person from every table and folder the
  kit owns, revokes cloud tokens where the provider allows it, tells the Cartridge
  Store (shared accounts) and lists what stays outside the kit (backups until they
  expire, the school's sign-in service, copies in the person's own cloud account,
  the browser). Audit events stay, with the person replaced by a pseudonym.

Every table must be listed in ``PERSONAL_TABLES`` or ``NOT_PERSONAL``
(tests/test_privacy_rights.py fails otherwise), so a new table cannot hold
personal data the rights workflows do not know about.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import select, text
from sqlalchemy.orm import Mapped, mapped_column

from .auth import admin_required
from .db import db, utcnow
from . import settings as site_settings

bp = Blueprint("privacy", __name__)

NOTICES_FILE = Path(__file__).with_name("privacy_notices.json")
RESPONSE_DAYS = 30            # Article 12(3): one month
MAX_EXTENSION_DAYS = 60       # ... extendable by two further months, with reasons
KINDS = ("access", "portability", "rectification", "erasure", "restriction", "objection", "withdrawal")
FINAL_STATES = ("completed", "refused", "partial")

# table -> how its rows belong to a person: ("user", column) for a user id, ("email", column)
# for an email address. Projects' own children (revisions, assets ...) follow owner_id.
PERSONAL_TABLES: dict[str, tuple[str, str]] = {
    "users": ("user", "id"),
    "external_identities": ("user", "user_id"),
    "user_groups": ("user", "user_id"),
    "class_members": ("user", "user_id"),
    "classes": ("user", "created_by"),
    "api_tokens": ("user", "user_id"),
    "cloud_accounts": ("user", "user_id"),
    "cloud_links": ("user", "user_id"),
    "projects": ("user", "owner_id"),
    "project_revisions": ("user", "owner_id"),
    "sprites": ("user", "owner_id"),
    "assets": ("user", "owner_id"),
    "artifacts": ("user", "owner_id"),
    "builds": ("user", "owner_id"),
    "publish_profiles": ("user", "owner_id"),
    "publish_attempts": ("user", "user_id"),
    "audit_events": ("user", "actor_id"),
    "sso_outbox": ("email", "email"),
    "registration_tokens": ("email", "email"),
    "privacy_notice_records": ("user", "user_id"),
    "privacy_requests": ("user", "user_id"),
}
# Tables with nothing about a person, and why.
NOT_PERSONAL: dict[str, str] = {
    "groups": "group names chosen by the administrator; membership is in user_groups",
    "identity_providers": "school sign-in settings; the client secret is a reference to the environment",
    "site_settings": "the admin Settings page; who changed what is in the audit log, secrets are sealed",
    "sso_nonces": "random single-use ticket values, kept until they expire (minutes)",
    "auth_throttle": "sign-in attempt counters keyed by a SHA-256 hash, never a name or address in clear; "
                     "each window lasts minutes",
}
# Columns never exported or shown: the document says they exist, nothing more.
SECRET_COLUMNS = {
    ("users", "password_hash"), ("api_tokens", "token_hash"), ("cloud_accounts", "tokens"),
    ("publish_profiles", "bearer_token"), ("registration_tokens", "token_hash"),
}


class PrivacyNoticeRecord(db.Model):
    """Which version of which notice a person was shown, where and when."""
    __tablename__ = "privacy_notice_records"
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)
    notice: Mapped[str] = mapped_column(db.Text, nullable=False)
    version: Mapped[str] = mapped_column(db.Text, nullable=False)
    context: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    shown_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)


class PrivacyRequest(db.Model):
    """One rights request (the register in docs/privacy/rights_requests.md)."""
    __tablename__ = "privacy_requests"
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    # The person; after an erasure only the pseudonym remains, so the register still shows
    # that the request was answered (accountability) without naming them.
    user_id: Mapped[int | None] = mapped_column(db.Integer, index=True)
    subject_ref: Mapped[str] = mapped_column(db.Text, nullable=False)
    kind: Mapped[str] = mapped_column(db.Text, nullable=False)
    details: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(db.Text, nullable=False, default="received")
    # How the person's identity was checked: "signed in" for their own request, or the
    # staff member's note for a request made on their behalf.
    verified_by: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    received_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)
    due_at: Mapped[str] = mapped_column(db.Text, nullable=False)
    extension_reason: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    handled_by: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    completed_at: Mapped[str | None] = mapped_column(db.Text)
    outcome: Mapped[str] = mapped_column(db.Text, nullable=False, default="{}")


# --- notices ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def notices() -> dict[str, dict[str, Any]]:
    data = json.loads(NOTICES_FILE.read_text(encoding="utf-8"))
    return {item["id"]: item for item in data["notices"]}


def record_notice(user_id: int | None, notice: str, context: str = "") -> bool:
    """Remember that this person was shown the current version of a notice (once per version)."""
    if user_id is None:
        return False
    version = notices()[notice]["version"]
    seen = db.session.scalar(select(PrivacyNoticeRecord.id).where(
        PrivacyNoticeRecord.user_id == user_id, PrivacyNoticeRecord.notice == notice,
        PrivacyNoticeRecord.version == version))
    if seen is not None:
        return False
    db.session.add(PrivacyNoticeRecord(user_id=user_id, notice=notice, version=version, context=context[:80]))
    db.session.commit()
    return True


# --- who someone is, in records that outlive them ---------------------------------------

def pseudonym(user_id: int) -> str:
    """A stable stand-in for a person in the audit log and the request register.

    Keyed with the installation's secret, so it cannot be turned back into the id by
    hashing guesses without that secret."""
    secret = str(current_app.config.get("SECRET_KEY") or "")
    digest = hashlib.sha256(f"prg32-privacy\x1f{secret}\x1f{int(user_id)}".encode()).hexdigest()
    return "person-" + digest[:12]


# --- access and portability --------------------------------------------------------------

def _rows(table: str, column: str, value: Any) -> list[dict[str, Any]]:
    # Table and column names come from PERSONAL_TABLES above, never from a request.
    result = db.session.execute(text(f'SELECT * FROM "{table}" WHERE "{column}" = :value'), {"value": value})
    rows = []
    for row in result.mappings():
        item = {}
        for key, cell in row.items():
            if (table, key) in SECRET_COLUMNS:
                item[key] = "(kept secret, not exported)" if cell else None
            elif isinstance(cell, bytes):
                item[key] = {"bytes": len(cell), "sha256": hashlib.sha256(cell).hexdigest()}
            else:
                item[key] = cell
        rows.append(item)
    return rows


def _files_of(user_id: int) -> list[dict[str, Any]]:
    """Files the kit keeps for this person: artifact files and AudioStudio sample sounds."""
    from .db import Artifact

    files = []
    for artifact in db.session.scalars(select(Artifact).where(Artifact.owner_id == user_id)):
        path = Path(artifact.path) if artifact.path else None
        if path is not None and path.is_file():
            files.append({"artifact_id": artifact.id, "name": path.name, "bytes": path.stat().st_size,
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "download": f"/api/artifacts/{artifact.id}?download=1"})
    samples = Path(current_app.config["ARTIFACT_ROOT"]) / "audio" / str(int(user_id))
    if samples.is_dir():
        for path in sorted(samples.rglob("*")):
            if path.is_file():
                files.append({"audio_sample": path.name, "bytes": path.stat().st_size,
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return files


def export_personal_data(user_id: int) -> dict[str, Any]:
    """Everything the kit holds about one person, table by table (Articles 15 and 20)."""
    from .auth import User

    user = db.session.get(User, user_id)
    if user is None:
        raise LookupError("no such account")
    sections: dict[str, list[dict[str, Any]]] = {}
    for table, (kind, column) in PERSONAL_TABLES.items():
        value = user.email if kind == "email" else user_id
        rows = _rows(table, column, value)
        if table == "audit_events":
            # Also what was done to the account; other people's names are not theirs to see.
            rows += [row for row in _rows(table, "target_id", str(user_id)) if row.get("target_type") == "user"
                     and row.get("actor_id") != user_id]
            for row in rows:
                if row.get("actor_id") != user_id:
                    row["actor_name"] = "(staff or system)"
                    row["actor_id"] = None
        sections[table] = rows
    return {
        "format": "prg32-personal-data-export",
        "format_version": 1,
        "generated_at": utcnow(),
        "subject": {"id": user.id, "username": user.username},
        "notice_versions": {key: item["version"] for key, item in notices().items()},
        "tables": sections,
        "files": _files_of(user_id),
        "not_in_this_export": not_held_by_the_kit(),
    }


def not_held_by_the_kit() -> list[dict[str, str]]:
    """Where else data about the person may be: the controller answers for these separately."""
    days = int(site_settings.get("PRG32_KIT_BACKUP_DAYS"))
    return [
        {"where": "this browser (IndexedDB)", "what": "guest games and unsaved work, on the person's own device",
         "how": "Clear site data in the browser."},
        {"where": "backups", "what": f"copies of the database and folders, kept {days} days (PRG32_KIT_BACKUP_DAYS)",
         "how": "They expire; a restored backup is checked against the erasure register (docs/privacy/retention.md)."},
        {"where": "Cartridge Store", "what": "published games and, with shared accounts, the account there",
         "how": "The Store keeps its own records (docs/privacy/processors_and_transfers.md)."},
        {"where": "school sign-in service", "what": "the school account used to sign in",
         "how": "Managed by the school's identity provider."},
        {"where": "Google Drive or OneDrive", "what": "copies the person saved in their own cloud folder",
         "how": "They belong to the person's own cloud account."},
        {"where": "web server and proxy logs", "what": "addresses and times of requests, if the operator keeps them",
         "how": "Configured by the operator (docs/privacy/retention.md)."},
    ]


# --- requests ------------------------------------------------------------------------------

def _days_from(start: str, days: int) -> str:
    when = datetime.fromisoformat(start.replace("Z", "+00:00"))
    return (when + timedelta(days=days)).replace(microsecond=0).isoformat()


def request_as_dict(item: PrivacyRequest) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {"id": item.id, "user_id": item.user_id, "subject": item.subject_ref, "kind": item.kind,
            "details": item.details, "status": item.status, "verified_by": item.verified_by,
            "received_at": item.received_at, "due_at": item.due_at, "extension_reason": item.extension_reason,
            "handled_by": item.handled_by, "completed_at": item.completed_at, "outcome": json.loads(item.outcome or "{}"),
            "overdue": item.status not in FINAL_STATES and item.due_at < now}


def open_request(user_id: int, kind: str, details: str, verified_by: str) -> PrivacyRequest:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    received = utcnow()
    item = PrivacyRequest(user_id=user_id, subject_ref=pseudonym(user_id), kind=kind, details=details[:2000],
                          verified_by=verified_by[:200], received_at=received, due_at=_days_from(received, RESPONSE_DAYS))
    db.session.add(item)
    db.session.commit()
    return item


def close_request(item: PrivacyRequest, status: str, outcome: dict[str, Any], handled_by: str) -> None:
    item.status = status
    item.outcome = json.dumps(outcome, sort_keys=True, default=str)
    item.handled_by = handled_by[:120]
    item.completed_at = utcnow()
    db.session.commit()


# --- restriction ----------------------------------------------------------------------------

# What a restricted account may still do: read, download its data, follow its requests, sign out.
RESTRICTED_ALLOWED = ("/api/me/privacy", "/auth/logout")


def restriction_blocks(principal, method: str, path: str) -> bool:
    if not getattr(principal, "restricted", False):
        return False
    if method in ("GET", "HEAD", "OPTIONS"):
        return False
    return not path.startswith(RESTRICTED_ALLOWED)


def set_restricted(user_id: int, restricted: bool) -> None:
    from .auth import User

    user = db.session.get(User, user_id)
    if user is None:
        raise LookupError("no such account")
    user.restricted_at = (user.restricted_at or utcnow()) if restricted else None
    db.session.commit()


# --- erasure -------------------------------------------------------------------------------

def _scrub(value: Any, words: list[str]) -> Any:
    if isinstance(value, str):
        for word in words:
            if word:
                value = value.replace(word, "(erased)")
        return value
    if isinstance(value, list):
        return [_scrub(item, words) for item in value]
    if isinstance(value, dict):
        return {key: _scrub(item, words) for key, item in value.items()}
    return value


def erase_account(user_id: int, handled_by: str) -> dict[str, Any]:
    """Remove one person from everything the kit holds (Article 17), and say what is left elsewhere.

    The order matters: external tokens are revoked while they can still be read, the
    person's items and folders go next, then every row naming them, and the account last
    (which also tells the Cartridge Store, with shared accounts). Each step's failure is
    recorded and the rest still runs: a partial erasure is reported as partial."""
    from . import cloud_storage, security
    from .auth import ApiToken, RegistrationToken, User, UserGroup, delete_user
    from .classes import ClassMember, SchoolClass
    from .identity import ExternalIdentity
    from .publishing import PublishAttempt
    from .retention import delete_account_items
    from .sso import SsoOutbox

    user = db.session.get(User, user_id)
    if user is None:
        raise LookupError("no such account")
    username, email, ref = user.username, user.email, pseudonym(user_id)
    outcome: dict[str, Any] = {"subject": ref, "steps": {}, "failures": [], "outside_the_kit": []}

    def step(name: str, action) -> None:
        try:
            outcome["steps"][name] = action()
        except Exception as error:   # noqa: BLE001 - every failure is recorded, the rest still runs
            db.session.rollback()
            outcome["failures"].append({"step": name, "error": str(error)[:300]})

    def revoke_cloud():
        revoked = []
        for account in db.session.scalars(select(cloud_storage.CloudAccount).where(
                cloud_storage.CloudAccount.user_id == user_id)).all():
            tokens = cloud_storage.unseal(account.tokens) if account.tokens else None
            done = False
            try:
                item = cloud_storage.provider_named(account.provider)
                done = bool(tokens) and item.revoke(tokens)
            except Exception:   # noqa: BLE001 - the provider may be switched off or unreachable
                done = False
            revoked.append({"provider": account.provider, "revoked_at_provider": done})
            if not done:
                outcome["outside_the_kit"].append({
                    "where": f"{account.provider} account settings",
                    "what": "the kit's permission (the provider offers no revocation, or it failed)",
                    "action": "The person, or the school's administrator, removes the app's access there."})
        return revoked

    def published():
        attempts = db.session.scalars(select(PublishAttempt).where(PublishAttempt.user_id == user_id)).all()
        listed = [{"store": attempt.store_host, "cartridge": attempt.cartridge_id, "version": attempt.cartridge_version,
                   "state": attempt.state} for attempt in attempts if attempt.state != "failed"]
        if listed:
            outcome["outside_the_kit"].append({
                "where": "Cartridge Store", "what": f"{len(listed)} published or submitted game(s)", "items": listed,
                "action": "The Store's operator removes them (the Store is a separate service and controller decision)."})
        return len(attempts)

    def items():
        return delete_account_items(user_id, Path(current_app.config["BUILD_ROOT"]))

    def rows():
        counts = {}
        for model, column in ((ApiToken, ApiToken.user_id), (cloud_storage.CloudAccount, cloud_storage.CloudAccount.user_id),
                              (cloud_storage.CloudLink, cloud_storage.CloudLink.user_id),
                              (ExternalIdentity, ExternalIdentity.user_id), (UserGroup, UserGroup.user_id),
                              (ClassMember, ClassMember.user_id), (PublishAttempt, PublishAttempt.user_id),
                              (PrivacyNoticeRecord, PrivacyNoticeRecord.user_id)):
            found = db.session.scalars(select(model).where(column == user_id)).all()
            for row in found:
                db.session.delete(row)
            counts[model.__tablename__] = len(found)
        for model, column in ((SsoOutbox, SsoOutbox.email), (RegistrationToken, RegistrationToken.email)):
            found = db.session.scalars(select(model).where(column == email)).all()
            for row in found:
                db.session.delete(row)
            counts[model.__tablename__] = len(found)
        for school_class in db.session.scalars(select(SchoolClass).where(SchoolClass.created_by == user_id)).all():
            school_class.created_by = None       # the class stays for its other members
        db.session.commit()
        return counts

    def audit():
        changed = 0
        words = [username, email]
        for event in db.session.scalars(select(security.AuditEvent)).all():
            metadata = json.loads(event.metadata_json or "{}")
            scrubbed = _scrub(metadata, words)
            about = event.actor_id == user_id or (event.target_type == "user" and event.target_id == str(user_id))
            if event.actor_id == user_id:
                event.actor_id = None
                event.actor_name = ref
            if event.target_type == "user" and event.target_id == str(user_id):
                event.target_id = ref
            if about:
                event.client = ""        # the address a request came from
            if about or scrubbed != metadata:
                event.metadata_json = json.dumps(scrubbed, sort_keys=True)
                changed += 1
        db.session.commit()
        return changed

    def requests_register():
        for item in db.session.scalars(select(PrivacyRequest).where(PrivacyRequest.user_id == user_id)).all():
            item.user_id = None
            item.details = _scrub(item.details, [username, email])
        db.session.commit()
        return "kept under the pseudonym"

    def account():
        delete_user(db.session.get(User, user_id))
        return "deleted (the Cartridge Store is told when accounts are shared)"

    step("cloud_tokens", revoke_cloud)
    step("store_publications", published)
    step("items_and_folders", items)
    step("rows", rows)
    step("audit_events", audit)
    step("request_register", requests_register)
    step("account", account)
    days = int(site_settings.get("PRG32_KIT_BACKUP_DAYS"))
    outcome["backups_expire_by"] = _days_from(utcnow(), days)
    outcome["outside_the_kit"] += [item for item in not_held_by_the_kit()
                                   if item["where"] in ("this browser (IndexedDB)", "school sign-in service",
                                                        "Google Drive or OneDrive", "web server and proxy logs")]
    outcome["status"] = "partial" if outcome["failures"] else "completed"
    security.record("privacy_erasure", target_type="user", target_id=ref, outcome=outcome["status"],
                    metadata={"failures": len(outcome["failures"]), "handled_by": handled_by})
    return outcome


# --- after restoring a backup ---------------------------------------------------------------

def erased_subjects() -> list[str]:
    """The pseudonyms of everyone erased: keep this list outside the backups (docs/privacy/retention.md)."""
    rows = db.session.scalars(select(PrivacyRequest.subject_ref).where(
        PrivacyRequest.kind == "erasure", PrivacyRequest.status.in_(("completed", "partial")))).all()
    return sorted(set(rows))


def reapply_erasures(subjects: list[str]) -> list[dict[str, Any]]:
    """A restored backup may hold people erased after it was made: erase them again.

    Needs the restored installation's secret key (it is in the backup), which makes the
    pseudonyms match."""
    from .auth import User

    wanted = set(subjects)
    done = []
    for user_id in db.session.scalars(select(User.id)).all():
        if pseudonym(user_id) in wanted:
            outcome = erase_account(user_id, "restore check")
            done.append({"subject": outcome["subject"], "status": outcome["status"]})
    return done


# --- routes ------------------------------------------------------------------------------

def _me():
    from .auth import current_principal

    principal = current_principal()
    if getattr(g, "prg32_auth_by_token", False):
        # A rights request changes or reveals everything about a person: only their own
        # signed-in browser may make it, never an API token that might have leaked.
        return None, (jsonify({"error": "privacy requests need a signed-in browser, not an API token"}), 403)
    return principal, None


# Everything the kit keeps in a visitor's browser (the "Cookies & storage" part of /privacy and
# the storage notice). Keep it in step with the browser_storage rows of docs/privacy/ropa.json.
BROWSER_STORAGE = (
    {"name": "prg32_kit_session", "kind": "cookie", "why": "keeps you signed in; holds your account number and "
     "sign-in time, signed so it cannot be changed", "how_long": "until you sign out, or a few hours after "
     "signing in", "needed": True},
    {"name": "prg32-kit-guest", "kind": "IndexedDB", "why": "the games, sprites and sounds you make without an "
     "account", "how_long": "until you delete them or clear this site's data", "needed": True},
    {"name": "prg32-source-language-<project>", "kind": "localStorage", "why": "which code view (C or assembly) "
     "you last opened for a project", "how_long": "until you clear this site's data", "needed": True},
    {"name": "prg32-kit-breakpoints:<...>, prg32-kit-source-breakpoints:<...>", "kind": "localStorage", "why": "the breakpoints you set in the "
     "debugger", "how_long": "until you clear this site's data", "needed": True},
    {"name": "prg32-kit-debugger-view", "kind": "localStorage", "why": "beginner or advanced debugger view",
     "how_long": "until you clear this site's data", "needed": True},
    {"name": "prg32-kit-last-project", "kind": "localStorage", "why": "the project AudioStudio offers to "
     "continue with", "how_long": "until you clear this site's data", "needed": True},
    {"name": "prg32-kit-storage-notice", "kind": "localStorage", "why": "that you have read this storage notice",
     "how_long": "until you clear this site's data", "needed": True},
    {"name": "prg32-kit-v*", "kind": "Cache Storage", "why": "the kit's own pages and libraries, so it opens "
     "without a connection; never your games or account pages", "how_long": "until the kit is updated",
     "needed": True},
)


@bp.get("/privacy")
def privacy_page():
    from flask import render_template

    return render_template("privacy.html", notices=list(notices().values()), storage=BROWSER_STORAGE,
                           controller=site_settings.get("PRG32_PRIVACY_CONTROLLER"),
                           contact=site_settings.get("PRG32_PRIVACY_CONTACT"))


def init_app(app) -> None:
    app.jinja_env.globals["privacy_notice"] = lambda notice_id: notices()[notice_id]


@bp.get("/api/privacy/notices")
def api_notices():
    return jsonify({"notices": list(notices().values())})


@bp.get("/api/me/privacy/export")
def api_my_export():
    from . import security

    principal, refused = _me()
    if refused:
        return refused
    item = open_request(principal.id, "access", "self-service download", "signed in")
    document = export_personal_data(principal.id)
    close_request(item, "completed", {"tables": {key: len(rows) for key, rows in document["tables"].items()},
                                      "files": len(document["files"])}, "self-service")
    security.record("privacy_export", target_type="user", target_id=principal.id)
    response = jsonify(document)
    response.headers["Content-Disposition"] = "attachment; filename=prg32-my-data.json"
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.route("/api/me/privacy/requests", methods=["GET", "POST"])
def api_my_requests():
    from . import security

    principal, refused = _me()
    if refused:
        return refused
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        kind = str(data.get("kind") or "")
        if kind not in KINDS or kind in ("access", "portability"):
            return jsonify({"error": "ask for rectification, erasure, restriction, objection or withdrawal; "
                                     "download your data with /api/me/privacy/export"}), 400
        item = open_request(principal.id, kind, str(data.get("details") or ""), "signed in")
        security.record("privacy_request", target_type="privacy_request", target_id=item.id, metadata={"kind": kind})
        return jsonify(request_as_dict(item)), 201
    mine = db.session.scalars(select(PrivacyRequest).where(PrivacyRequest.user_id == principal.id)
                              .order_by(PrivacyRequest.id.desc())).all()
    return jsonify({"requests": [request_as_dict(item) for item in mine]})


@bp.get("/api/admin/privacy/requests")
@admin_required
def api_admin_requests():
    items = db.session.scalars(select(PrivacyRequest).order_by(PrivacyRequest.due_at)).all()
    return jsonify({"requests": [request_as_dict(item) for item in items]})


@bp.post("/api/admin/privacy/users/<int:user_id>/requests")
@admin_required
def api_admin_open(user_id: int):
    """A request made on someone's behalf (by letter, in person): say how their identity was checked."""
    from . import security
    from .auth import User

    data = request.get_json(silent=True) or {}
    verified = str(data.get("verified_by") or "").strip()
    if not verified:
        return jsonify({"error": "say how the person's identity was checked (verified_by)"}), 400
    if db.session.get(User, user_id) is None:
        return jsonify({"error": "user not found"}), 404
    try:
        item = open_request(user_id, str(data.get("kind") or ""), str(data.get("details") or ""), verified)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    security.record("privacy_request", target_type="privacy_request", target_id=item.id,
                    metadata={"kind": item.kind, "on_behalf": True})
    return jsonify(request_as_dict(item)), 201


@bp.post("/api/admin/privacy/requests/<int:request_id>")
@admin_required
def api_admin_decide(request_id: int):
    """Carry out, refuse or extend a request. Erasure and restriction are done here, nowhere else."""
    from . import security
    from .auth import current_principal

    item = db.session.get(PrivacyRequest, request_id)
    if item is None:
        return jsonify({"error": "request not found"}), 404
    if item.status in FINAL_STATES:
        return jsonify({"error": f"this request is already {item.status}"}), 409
    data = request.get_json(silent=True) or {}
    action = str(data.get("action") or "")
    reason = str(data.get("reason") or "").strip()
    staff = current_principal().name
    if action == "extend":
        days = int(data.get("days") or 0)
        if not reason or not 0 < days <= MAX_EXTENSION_DAYS:
            return jsonify({"error": f"an extension needs a reason and 1-{MAX_EXTENSION_DAYS} days"}), 400
        item.due_at = _days_from(item.due_at, days)
        item.extension_reason = reason[:500]
        db.session.commit()
    elif action == "refuse":
        if not reason:
            return jsonify({"error": "a refusal needs its reason (the exemption relied on)"}), 400
        close_request(item, "refused", {"reason": reason}, staff)
    elif action == "complete":
        if item.user_id is None:
            return jsonify({"error": "the account no longer exists"}), 409
        # The confirmation must name the account: an erasure cannot be confirmed by accident.
        if item.kind == "erasure" and str(data.get("confirm_user_id")) != str(item.user_id):
            return jsonify({"error": "confirm the erasure with confirm_user_id", "code": "confirm_required"}), 400
        if item.kind == "erasure":
            outcome = erase_account(item.user_id, staff)
            close_request(item, outcome["status"], outcome, staff)
        elif item.kind == "restriction":
            set_restricted(item.user_id, bool(data.get("restricted", True)))
            close_request(item, "completed", {"restricted": bool(data.get("restricted", True)), "note": reason}, staff)
        else:
            # Rectification is done with the account editor (PUT /api/users/<id>); objection and
            # withdrawal are decided by the controller. The outcome records what was done.
            if not reason:
                return jsonify({"error": "describe what was done (reason)"}), 400
            close_request(item, "completed", {"note": reason}, staff)
    else:
        return jsonify({"error": "action must be complete, refuse or extend"}), 400
    security.record("privacy_request_" + action, target_type="privacy_request", target_id=item.id,
                    outcome=item.status, metadata={"kind": item.kind})
    return jsonify(request_as_dict(item))


@bp.get("/api/admin/privacy/users/<int:user_id>/export")
@admin_required
def api_admin_export(user_id: int):
    from . import security

    try:
        document = export_personal_data(user_id)
    except LookupError:
        return jsonify({"error": "user not found"}), 404
    security.record("privacy_export", target_type="user", target_id=user_id, metadata={"by_admin": True})
    response = jsonify(document)
    response.headers["Cache-Control"] = "no-store"
    return response
