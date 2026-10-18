"""Single sign-on and user sync between this kit and one PRG32 Cartridge Store.

Turn it on by giving *both* services the same two settings:

    PRG32_SSO_SECRET    a long random secret (at least 32 characters)
    PRG32_SSO_PEER_URL  the other service's address, e.g. http://store.school:5080

Then:

- a user created, changed or deleted here is created, changed or deleted on
  the Cartridge Store too, and the other way round;
- "Open Cartridge Store" signs the student in there without a second password;
- publishing to that store happens as the signed-in student.

If the other service is offline, the change waits in a small outbox and is
sent with the next change or the next "Sync now". The protocol itself is in
``sso_protocol.py``, which is the same file in both repositories.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from . import sso_protocol as protocol
from .db import db, utcnow

AUDIENCE_HERE = protocol.AUDIENCE_KIT
AUDIENCE_PEER = protocol.AUDIENCE_STORE


class SsoNonce(db.Model):
    """Tickets already used; a ticket only ever works once."""
    __tablename__ = "sso_nonces"
    nonce: Mapped[str] = mapped_column(db.Text, primary_key=True)
    expires_at: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)


class SsoOutbox(db.Model):
    """Users whose latest change has not reached the other service yet."""
    __tablename__ = "sso_outbox"
    email: Mapped[str] = mapped_column(db.Text, primary_key=True)
    payload: Mapped[str] = mapped_column(db.Text, nullable=False)
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)
    attempts: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)


# --- settings -----------------------------------------------------------------

def enabled() -> bool:
    config = current_app.config
    return protocol.secret_is_usable(config.get("SSO_SECRET")) and bool(peer_url())


def peer_url() -> str:
    return str(current_app.config.get("SSO_PEER_URL") or "").strip().rstrip("/")


def _secret() -> str:
    return str(current_app.config["SSO_SECRET"])


def same_service(url: str) -> bool:
    """True when ``url`` points at the synced Cartridge Store."""
    return enabled() and str(url or "").strip().rstrip("/").lower() == peer_url().lower()


def status() -> dict[str, Any]:
    if not enabled():
        return {"enabled": False, "abi": protocol.SSO_ABI}
    pending = db.session.query(SsoOutbox).count()
    return {"enabled": True, "abi": protocol.SSO_ABI, "peer_url": peer_url(), "pending": pending}


# --- talking to the other service --------------------------------------------

Transport = Callable[[str, str, dict[str, str], bytes], tuple[int, bytes]]


def _urllib_transport(method: str, url: str, headers: dict[str, str], body: bytes) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body if method != "GET" else None, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=float(current_app.config.get("SSO_TIMEOUT", 5))) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _call_peer(method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8") if payload is not None else b""
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    headers.update(protocol.sign_request(_secret(), method, protocol.USERS_PATH, body))
    transport: Transport = current_app.config.get("SSO_TRANSPORT") or _urllib_transport
    status_code, raw = transport(method, peer_url() + protocol.USERS_PATH, headers, body)
    if status_code != 200:
        raise ConnectionError(f"Cartridge Store answered {status_code}: {raw[:200]!r}")
    return json.loads(raw.decode("utf-8"))


# --- records ------------------------------------------------------------------

def user_record(user) -> dict[str, Any]:
    from .auth import groups_for_user

    return {
        "email": user.email,
        "username": user.username,
        "password_hash": user.password_hash,
        "role": user.role,
        "groups": list(groups_for_user(int(user.id))),
        "updated_at": user.updated_at,
        "deleted": False,
    }


def _queue(records: list[dict[str, Any]]) -> None:
    for record in records:
        row = db.session.get(SsoOutbox, record["email"])
        if row is None:
            db.session.add(SsoOutbox(email=record["email"], payload=json.dumps(record), attempts=1))
        else:
            row.payload = json.dumps(record)
            row.attempts += 1
    db.session.commit()


def push(records: list[dict[str, Any]]) -> bool:
    """Send records (plus anything still waiting in the outbox) to the other service."""
    if not enabled():
        return False
    waiting = {row.email: json.loads(row.payload) for row in db.session.scalars(select(SsoOutbox))}
    for record in records:
        waiting.pop(record["email"], None)
    batch = list(waiting.values()) + records
    if not batch:
        return True
    try:
        _call_peer("POST", {"abi": protocol.SSO_ABI, "users": batch})
    except Exception as exc:  # the store may be offline; try again later
        current_app.logger.warning("User sync with %s failed, will retry: %s", peer_url(), exc)
        _queue(batch)
        return False
    db.session.execute(delete(SsoOutbox).where(SsoOutbox.email.in_([record["email"] for record in batch])))
    db.session.commit()
    return True


def user_changed(user, previous_email: str | None = None) -> None:
    if not enabled():
        return
    record = user_record(user)
    if previous_email:
        record["previous_email"] = previous_email
    push([record])


def user_deleted(email: str) -> None:
    if enabled():
        push([{"email": email, "deleted": True, "updated_at": protocol.timestamp_now()}])


def apply_record(data: Any) -> str:
    """Store one user record that came from the other service. The newest change wins.

    This never sends anything back, so two services cannot bounce a change forever.
    """
    from .auth import User, _write_groups, admin_count, find_user_by_email, unique_username

    record = protocol.clean_record(data)
    user = find_user_by_email(record["email"])
    if user is None and record["previous_email"]:
        user = find_user_by_email(record["previous_email"])
    if record["deleted"]:
        if user is None:
            return "unknown"
        if not protocol.is_newer(record["updated_at"], user.updated_at):
            return "stale"
        if user.role == "admin" and admin_count(excluding=user.id) == 0:
            return "kept-last-admin"
        db.session.delete(user)
        db.session.commit()
        return "deleted"
    if user is not None and not protocol.is_newer(record["updated_at"], user.updated_at):
        return "stale"
    if user is None:
        user = User(username=unique_username(record["username"], record["email"]), email=record["email"])
        db.session.add(user)
        result = "created"
    else:
        if user.role == "admin" and record["role"] != "admin" and admin_count(excluding=user.id) == 0:
            return "kept-last-admin"
        user.email = record["email"]
        if record["username"] != user.username:
            user.username = unique_username(record["username"], record["email"], ignore_user_id=user.id)
        result = "updated"
    user.password_hash = record["password_hash"]
    user.role = record["role"]
    user.updated_at = record["updated_at"] or protocol.timestamp_now()
    db.session.flush()
    _write_groups(int(user.id), record["groups"])
    db.session.commit()
    return result


def full_sync() -> dict[str, Any]:
    """Make both services agree: send waiting changes, take theirs, then send ours."""
    from .auth import User

    if not enabled():
        raise ValueError("Single sign-on is not configured (PRG32_SSO_SECRET and PRG32_SSO_PEER_URL)")
    if not push([]):
        raise ConnectionError(f"Could not reach {peer_url()}")
    remote = _call_peer("GET").get("users", [])
    results: dict[str, int] = {}
    for record in remote:
        try:
            outcome = apply_record(record)
        except ValueError:
            outcome = "invalid"
        results[outcome] = results.get(outcome, 0) + 1
    local = [user_record(user) for user in db.session.scalars(select(User))]
    sent = push(local)
    return {"ok": sent, "received": len(remote), "applied": results, "sent": len(local)}


# --- tickets ------------------------------------------------------------------

def make_ticket(email: str, purpose: str) -> str:
    ttl = protocol.LOGIN_TICKET_SECONDS if purpose == "login" else protocol.API_TICKET_SECONDS
    return protocol.make_ticket(_secret(), email=email, audience=AUDIENCE_PEER, purpose=purpose, ttl=ttl)


def use_ticket(ticket: str, purpose: str) -> str | None:
    """Return the email inside a valid ticket meant for us, and mark it used."""
    if not enabled():
        return None
    claims = protocol.read_ticket(_secret(), ticket, audience=AUDIENCE_HERE, purpose=purpose)
    if claims is None:
        return None
    db.session.execute(delete(SsoNonce).where(SsoNonce.expires_at < int(time.time())))
    db.session.add(SsoNonce(nonce=claims["nonce"], expires_at=int(claims["exp"])))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None  # this ticket was already used
    return str(claims["email"])


# --- routes -------------------------------------------------------------------

bp = Blueprint("sso", __name__)


def _signed_by_peer() -> bool:
    return enabled() and protocol.verify_request(_secret(), request.method, protocol.USERS_PATH,
                                                 request.get_data(cache=True), request.headers)


@bp.route(protocol.USERS_PATH, methods=["GET", "POST"])
def peer_users():
    """Only the synced Cartridge Store can call this: every request is signed."""
    from .auth import User

    if not _signed_by_peer():
        return jsonify({"error": "bad or missing SSO signature"}), 403
    if request.method == "GET":
        users = [user_record(user) for user in db.session.scalars(select(User))]
        return jsonify({"abi": protocol.SSO_ABI, "users": users})
    data = request.get_json(silent=True) or {}
    records = data.get("users")
    if not isinstance(records, list):
        return jsonify({"error": "users must be a list"}), 400
    results = []
    for record in records:
        try:
            results.append(apply_record(record))
        except ValueError as exc:
            results.append(f"invalid: {exc}")
    return jsonify({"ok": True, "abi": protocol.SSO_ABI, "results": results})


@bp.post("/api/sso/sync")
def sync_now():
    from .auth import current_principal

    from . import security

    if not current_principal().is_admin:
        security.record("sso_sync", target_type="sso", outcome="denied")
        return jsonify({"error": "Only teachers with the admin role can do this"}), 403
    try:
        result = full_sync()
    except ValueError as exc:
        security.record("sso_sync", target_type="sso", outcome="refused", metadata={"reason": str(exc)})
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        security.record("sso_sync", target_type="sso", outcome="failed", metadata={"reason": type(exc).__name__})
        return jsonify({"error": f"Sync failed: {exc}"}), 502
    from urllib.parse import urlparse

    security.record("sso_sync", target_type="sso", metadata={"peer_host": urlparse(peer_url()).hostname or ""})
    return jsonify(result)


@bp.get("/auth/sso/peer")
def go_to_peer():
    """Sign the current user in on the Cartridge Store and open it there."""
    from .auth import auth_failure, current_principal

    principal = current_principal()
    if not principal.authenticated:
        return auth_failure("Please sign in first", 401)
    if not enabled():
        return render_template("error.html", error="Single sign-on with a Cartridge Store is not configured."), 404
    target = request.args.get("next") or "/"
    if not target.startswith("/") or target.startswith("//"):
        target = "/"
    return render_template("sso_redirect.html", action=peer_url() + protocol.ACCEPT_PATH,
                           ticket=make_ticket(principal.email, "login"), next=target)


@bp.post(protocol.ACCEPT_PATH)
def accept_login():
    """The Cartridge Store sent a signed-in user here with a one-time ticket."""
    from .auth import find_user_by_email, principal_from_user, safe_next, sign_in

    email = use_ticket(request.form.get("ticket", ""), "login")
    if email is None:
        return render_template("error.html", error="This sign-in link is invalid, expired, or already used."), 400
    user = find_user_by_email(email)
    if user is None:
        return render_template("error.html", error="Your account has not reached the Construction Kit yet. "
                                                   "Ask your teacher to press Sync now."), 404
    sign_in(principal_from_user(user))
    session["sso"] = True
    return redirect(safe_next())


def init_app(app) -> None:
    app.register_blueprint(bp)
