"""Sign-in throttling and the administrator audit log.

Throttling
----------
Guessing passwords, sending many registration e-mails or minting many API
tokens are slowed down by counting attempts in the database (so every
gunicorn worker sees the same counts). Each limit is a number of attempts in
a time window; when it is reached the request gets ``429 Too Many Requests``
with a ``Retry-After`` header, and the counter forgets old attempts by
itself when the window ends.

A classroom often shares one public address, so sign-in failures are counted
per *address and username*: one student's typos never lock out the class.
A second, much larger limit per address stops someone trying many names.

The client address is the connecting address. ``X-Forwarded-For`` is used
only when ``PRG32_KIT_PROXY_COUNT`` says how many trusted reverse proxies are
in front of the kit (see docs/security.md).

Audit log
---------
Security-relevant actions (accounts, roles, groups, API tokens, the first
admin, publishing, single-sign-on sync, clearing throttles) are written to
``audit_events``: who did what to what, when, and whether it worked. Only
safe facts go in the metadata: never passwords, tokens, tickets or cookies.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from flask import current_app, has_request_context, request
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete, select
from sqlalchemy.orm import Mapped, mapped_column

from .db import db, utcnow

# --- audit log ---------------------------------------------------------------

# Metadata keys that must never be stored, whatever the caller passes.
_SECRET_WORDS = ("password", "token", "secret", "ticket", "cookie", "authorization", "hash")


class AuditEvent(db.Model):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow, index=True)
    actor_id: Mapped[int | None] = mapped_column(db.Integer, index=True)
    actor_name: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    action: Mapped[str] = mapped_column(db.Text, nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    target_id: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    outcome: Mapped[str] = mapped_column(db.Text, nullable=False, default="success")
    client: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    metadata_json: Mapped[str] = mapped_column("metadata", db.Text, nullable=False, default="{}")


def safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Drop anything that looks like a secret and keep values short."""
    safe: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        if any(word in str(key).lower() for word in _SECRET_WORDS):
            continue
        if isinstance(value, str):
            value = value[:200]
        elif isinstance(value, (list, tuple)):
            value = [str(item)[:80] for item in list(value)[:50]]
        elif not isinstance(value, (int, float, bool)) and value is not None:
            value = str(value)[:200]
        safe[str(key)[:60]] = value
    return safe


def record(action: str, *, target_type: str = "", target_id: Any = "", outcome: str = "success",
           metadata: dict[str, Any] | None = None, actor: Any = None) -> None:
    """Write one audit event in its own transaction (it never breaks the request that caused it)."""
    if actor is None and has_request_context():
        from .auth import current_principal

        actor = current_principal()
    actor_id = getattr(actor, "id", None) if getattr(actor, "authenticated", True) else None
    event = AuditEvent(
        created_at=utcnow(),
        actor_id=actor_id,
        actor_name=str(getattr(actor, "name", "") or "system")[:120],
        action=action,
        target_type=target_type,
        target_id=str(target_id or "")[:120],
        outcome=outcome,
        client=client_address() if has_request_context() else "",
        metadata_json=json.dumps(safe_metadata(metadata), sort_keys=True),
    )
    try:
        db.session.add(event)
        db.session.commit()
    except Exception:  # an audit failure must not undo the action it describes
        db.session.rollback()
        current_app.logger.exception("Could not write audit event %s", action)


def audit_events(limit: int = 100, action: str | None = None, before_id: int | None = None) -> list[dict[str, Any]]:
    statement = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(max(1, min(int(limit), 500)))
    if action:
        statement = statement.where(AuditEvent.action == action)
    if before_id:
        statement = statement.where(AuditEvent.id < int(before_id))
    return [{"id": event.id, "created_at": event.created_at, "actor_id": event.actor_id,
             "actor_name": event.actor_name, "action": event.action, "target_type": event.target_type,
             "target_id": event.target_id, "outcome": event.outcome, "client": event.client,
             "metadata": json.loads(event.metadata_json or "{}")}
            for event in db.session.scalars(statement).all()]


# --- client address ----------------------------------------------------------

def client_address() -> str:
    """The address of the browser, trusting X-Forwarded-For only behind configured proxies."""
    proxies = int(current_app.config.get("PROXY_COUNT") or 0)
    if proxies > 0:
        forwarded = [part.strip() for part in request.headers.get("X-Forwarded-For", "").split(",") if part.strip()]
        # Each trusted proxy appends the address it saw; the client is that many entries from the end.
        if len(forwarded) >= proxies:
            return forwarded[-proxies][:64]
    return str(request.remote_addr or "")[:64]


# --- throttling --------------------------------------------------------------

@dataclass(frozen=True)
class Limit:
    """At most ``attempts`` within ``window`` seconds."""
    name: str
    attempts: int
    window: int


# Conservative defaults for a classroom; each can be changed with an environment variable
# (see config.py and docs/security.md).
LIMITS = {
    "login_user": Limit("login_user", 5, 15 * 60),       # wrong passwords for one name from one address
    "login_address": Limit("login_address", 100, 15 * 60),  # wrong passwords from one address, any name
    "register_address": Limit("register_address", 10, 60 * 60),
    "register_email": Limit("register_email", 3, 60 * 60),
    "register_complete": Limit("register_complete", 20, 60 * 60),  # bad or reused links from one address
    "token_create": Limit("token_create", 20, 60 * 60),  # new API tokens per user
    # Code generation and sound previews for visitors without an account, from one address (ADR-0023).
    "guest_api": Limit("guest_api", 600, 60 * 60),
    # Run builds for visitors without an account (each one compiles a cartridge): per address.
    "guest_run": Limit("guest_run", 30, 60 * 60),
}


class ThrottleCounter(db.Model):
    __tablename__ = "auth_throttle"
    key: Mapped[str] = mapped_column(db.Text, primary_key=True)
    window_start: Mapped[int] = mapped_column(db.Integer, nullable=False)
    attempts: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)


class Throttled(Exception):
    def __init__(self, retry_after: int):
        super().__init__("Too many attempts")
        self.retry_after = max(1, int(retry_after))


def limit(name: str) -> Limit:
    configured = current_app.config.get("THROTTLE_LIMITS", {}).get(name)
    base = LIMITS[name]
    if configured:
        return Limit(name, int(configured[0]), int(configured[1]))
    return base


def _key(name: str, *parts: Any) -> str:
    # Only a hash is stored: the table never holds usernames, e-mails or addresses in clear.
    raw = "\x1f".join([name, *(str(part).strip().lower() for part in parts)])
    return name + ":" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now() -> int:
    return int(time.time())


def check(name: str, *parts: Any) -> None:
    """Raise Throttled when the limit is already used up (does not count this attempt)."""
    rule = limit(name)
    row = db.session.get(ThrottleCounter, _key(name, *parts))
    now = _now()
    if row is not None and now - row.window_start < rule.window and row.attempts >= rule.attempts:
        raise Throttled(row.window_start + rule.window - now)


def hit(name: str, *parts: Any) -> None:
    """Count one attempt; a new window starts when the old one has ended."""
    rule = limit(name)
    key = _key(name, *parts)
    for _attempt in range(2):
        now = _now()
        row = db.session.get(ThrottleCounter, key)
        if row is None:
            db.session.add(ThrottleCounter(key=key, window_start=now, attempts=1))
        elif now - row.window_start >= rule.window:
            row.window_start = now
            row.attempts = 1
        else:
            row.attempts += 1
        try:
            db.session.commit()
            return
        except IntegrityError:
            # Two requests from one address at once both found no counter and both added one:
            # the other one won, so count this attempt on its row.
            db.session.rollback()


def check_and_hit(name: str, *parts: Any) -> None:
    check(name, *parts)
    hit(name, *parts)


def reset(name: str, *parts: Any) -> None:
    db.session.execute(delete(ThrottleCounter).where(ThrottleCounter.key == _key(name, *parts)))
    db.session.commit()


def clear_all() -> int:
    """Remove every counter (the teacher's way to unlock a class at once)."""
    result = db.session.execute(delete(ThrottleCounter))
    db.session.commit()
    return int(result.rowcount or 0)


def forget_expired() -> None:
    """Delete counters whose window ended long ago, so the table stays small."""
    longest = max(rule.window for rule in LIMITS.values())
    db.session.execute(delete(ThrottleCounter).where(ThrottleCounter.window_start < _now() - 2 * longest))
    db.session.commit()
