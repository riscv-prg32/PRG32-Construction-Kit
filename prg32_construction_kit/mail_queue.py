"""The email sending queue: the SMTP server never gets more than a fixed number of messages at once.

Every message the kit sends (sign-up links, new sign-in notices, the admin's test mail) is
first written to ``mail_outbox`` with the state ``queued``. A small sender thread in each
server process hands queued messages to the SMTP server, but only while it holds one of the
*mail slots*: lock files in ``<DATA_DIR>/.mail_slots``, exactly like the build slots
(build_slots.py). There are as many slots as the **Email sending queue size** setting
(``SMTP_MAX_PARALLEL``, 5 by default), and a file lock is shared by every thread and every
worker process, so the limit holds for the whole server.

A message goes ``queued`` -> ``sending`` -> ``sent``. When the server refuses it, it goes back
to ``queued`` and is tried again later (after 1, then 5 minutes); after ``MAX_ATTEMPTS`` it is
``failed`` and an admin can try it again from the Email tab.

Privacy (docs/privacy/ropa.json, "email_queue"): a message's text can hold a sign-up link, so it
is stored encrypted (``secrets_at_rest``) and wiped as soon as the message is sent (a failed one
keeps it, sealed, so an admin can try again, until the row expires). What stays, for ``PRG32_KIT_MAIL_DAYS`` days, is who it went to, the subject and the
outcome; the admin page shows the address shortened (``ma***@school.example``).
"""

from __future__ import annotations

import os
import smtplib
import threading
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable

from flask import current_app
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Mapped, mapped_column

from . import settings as site_settings
from .build_slots import release_slot, try_slot
from .db import db, utcnow

STATES = ("queued", "sending", "sent", "failed")
MAX_ATTEMPTS = 3
RETRY_MINUTES = (1, 5)              # wait before the 2nd and the 3rd attempt
STALE_SENDING_MINUTES = 10          # a "sending" row this old belonged to a process that stopped
KINDS = ("registration", "new_sign_in", "smtp_test")
_PURPOSE = b"mail-outbox"
_POLL_SECONDS = 15.0


class MailMessage(db.Model):
    """One message in the queue (the admin's Email tab lists them)."""
    __tablename__ = "mail_outbox"
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(db.Text, nullable=False)
    recipient: Mapped[str] = mapped_column(db.Text, nullable=False, index=True)
    subject: Mapped[str] = mapped_column(db.Text, nullable=False)
    body: Mapped[str] = mapped_column(db.Text, nullable=False, default="")      # sealed; "" once done
    status: Mapped[str] = mapped_column(db.Text, nullable=False, default="queued", index=True)
    attempts: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    last_error: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow, index=True)
    next_attempt_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)
    started_at: Mapped[str | None] = mapped_column(db.Text)
    finished_at: Mapped[str | None] = mapped_column(db.Text)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def limit() -> int:
    """The queue size: how many messages may be with the SMTP server at the same time."""
    return max(1, int(site_settings.get("SMTP_MAX_PARALLEL") or 5))


def _slot_dir() -> Path:
    return Path(current_app.config["DATA_DIR"]) / ".mail_slots"


# --- putting a message in the queue ---------------------------------------------------------

def enqueue(kind: str, recipient: str, subject: str, text: str) -> MailMessage:
    """Queue one plain-text message and wake this process's sender."""
    from .secrets_at_rest import seal

    item = MailMessage(kind=kind if kind in KINDS else "other", recipient=str(recipient)[:320],
                       subject=str(subject)[:200], body=seal(text, purpose=_PURPOSE), status="queued",
                       created_at=utcnow(), next_attempt_at=utcnow())
    db.session.add(item)
    db.session.commit()
    start_sender(current_app._get_current_object())
    return item


# --- sending ------------------------------------------------------------------------------

def _transport(message: EmailMessage) -> None:
    """Hand one message to the SMTP server (tests replace this)."""
    from .auth import _smtp_send

    _smtp_send(message)


def _claim(now: datetime) -> int | None:
    """Mark the oldest due queued message as ``sending`` and return its id (None: nothing due).

    The UPDATE checks the state again, so two processes never take the same message.
    """
    stamp = _iso(now)
    candidates = db.session.scalars(select(MailMessage.id).where(MailMessage.status == "queued",
                                                                 MailMessage.next_attempt_at <= stamp)
                                    .order_by(MailMessage.id).limit(5)).all()
    for message_id in candidates:
        taken = db.session.execute(update(MailMessage).where(MailMessage.id == message_id,
                                                             MailMessage.status == "queued")
                                   .values(status="sending", started_at=stamp,
                                           attempts=MailMessage.attempts + 1))
        db.session.commit()
        if taken.rowcount:
            return message_id
    return None


def _deliver(app, message_id: int, slot, done: Callable[[], None]) -> None:
    """Send one claimed message while holding a mail slot, then record what happened."""
    from .secrets_at_rest import unseal

    try:
        with app.app_context():
            item = db.session.get(MailMessage, message_id)
            error = ""
            try:
                text = unseal(item.body, purpose=_PURPOSE)
                if text is None:
                    raise ValueError("the message text cannot be read (the server's secret key changed)")
                message = EmailMessage()
                message["From"] = site_settings.get("SMTP_FROM")
                message["To"] = item.recipient
                message["Subject"] = item.subject
                message.set_content(text)
                _transport(message)
            except (OSError, smtplib.SMTPException, ValueError) as problem:
                error = str(problem)[:300] or problem.__class__.__name__
            now = _now()
            item.finished_at = _iso(now)
            if not error:
                item.status, item.body, item.last_error = "sent", "", ""
            elif item.attempts >= MAX_ATTEMPTS:
                item.status, item.last_error = "failed", error      # text kept (sealed) for a retry
                app.logger.warning("mail %s to the queue failed for good: %s", message_id, error)
            else:
                wait = RETRY_MINUTES[min(item.attempts, len(RETRY_MINUTES)) - 1]
                item.status, item.last_error = "queued", error
                item.next_attempt_at = _iso(now + timedelta(minutes=wait))
            db.session.commit()
    finally:
        release_slot(slot)
        done()


def _requeue_stale(now: datetime) -> None:
    """Messages left ``sending`` by a process that stopped go back in the queue."""
    cutoff = _iso(now - timedelta(minutes=STALE_SENDING_MINUTES))
    db.session.execute(update(MailMessage).where(MailMessage.status == "sending", MailMessage.started_at < cutoff)
                       .values(status="queued", next_attempt_at=_iso(now)))
    db.session.commit()


def dispatch(app, *, wait: bool = False) -> int:
    """Start sending every due message there is a free slot for; return how many were started.

    ``wait=True`` (tests, the CLI) keeps going until nothing due is left and every send ended.
    """
    started = 0
    threads: list[threading.Thread] = []
    finished = threading.Event()
    while True:
        with app.app_context():
            _requeue_stale(_now())
            slot_dir, size = _slot_dir(), limit()
            progressed = False
            while True:
                slot = try_slot(slot_dir, size)
                if slot is None:
                    break
                message_id = _claim(_now())
                if message_id is None:
                    release_slot(slot)
                    break
                thread = threading.Thread(target=_deliver, args=(app, message_id, slot, finished.set),
                                          name=f"prg32-mail-{message_id}", daemon=True)
                thread.start()
                threads.append(thread)
                started += 1
                progressed = True
            due = db.session.scalar(select(func.count()).select_from(MailMessage).where(
                MailMessage.status == "queued", MailMessage.next_attempt_at <= _iso(_now())))
        if not wait:
            return started
        alive = [thread for thread in threads if thread.is_alive()]
        if not due and not alive:
            return started
        if not progressed:
            finished.wait(0.05)
            finished.clear()


# --- the sender thread of each process -------------------------------------------------------

_sender: dict[str, Any] = {"pid": None, "wake": None}
_sender_lock = threading.Lock()


def wake() -> None:
    event = _sender.get("wake")
    if event is not None and _sender.get("pid") == os.getpid():
        event.set()


def start_sender(app) -> None:
    """Make sure this process has its sender thread (after a fork, gunicorn --preload, start a new one)."""
    if app.config.get("TESTING"):
        return                         # tests call dispatch(app, wait=True) themselves
    with _sender_lock:
        if _sender["pid"] != os.getpid():
            event = threading.Event()
            _sender.update(pid=os.getpid(), wake=event)
            threading.Thread(target=_sender_loop, args=(app, event), name="prg32-mail-sender", daemon=True).start()
    wake()


def _sender_loop(app, event: threading.Event) -> None:
    while True:
        try:
            dispatch(app)
        except Exception:   # noqa: BLE001 - the sender must outlive one bad round (the database was busy)
            app.logger.exception("mail queue round failed")
        event.wait(_POLL_SECONDS if not _busy(app) else 1.0)
        event.clear()


def _busy(app) -> bool:
    with app.app_context():
        return bool(db.session.scalar(select(MailMessage.id).where(MailMessage.status.in_(("queued", "sending")))
                                      .limit(1)))


# --- what the admin's Email tab shows ----------------------------------------------------------

def masked(address: str) -> str:
    """``mario.rossi@school.example`` -> ``ma***@school.example``: enough to recognise, not to copy."""
    name, _, domain = str(address or "").partition("@")
    return (name[:2] + "***@" + domain) if domain else "***"


def as_dict(item: MailMessage) -> dict[str, Any]:
    return {"id": item.id, "kind": item.kind, "recipient": masked(item.recipient), "subject": item.subject,
            "status": item.status, "attempts": item.attempts, "last_error": item.last_error,
            "created_at": item.created_at, "next_attempt_at": item.next_attempt_at if item.status == "queued" else None,
            "started_at": item.started_at, "finished_at": item.finished_at}


def status(state: str | None = None, max_items: int = 100) -> dict[str, Any]:
    counts = dict(db.session.execute(select(MailMessage.status, func.count()).group_by(MailMessage.status)).all())
    statement = select(MailMessage).order_by(MailMessage.id.desc()).limit(max(1, min(int(max_items), 500)))
    if state in STATES:
        statement = statement.where(MailMessage.status == state)
    return {"limit": limit(), "counts": {name: int(counts.get(name, 0)) for name in STATES},
            "smtp_configured": bool(str(site_settings.get("SMTP_HOST") or "").strip()),
            "messages": [as_dict(item) for item in db.session.scalars(statement)]}


def retry(message_id: int) -> bool:
    """Put a failed message back in the queue (only possible while its text is still kept)."""
    item = db.session.get(MailMessage, message_id)
    if item is None or item.status != "failed" or not item.body:
        return False
    item.status, item.attempts, item.next_attempt_at = "queued", 0, utcnow()
    db.session.commit()
    start_sender(current_app._get_current_object())
    return True


def expire(days: int, now: datetime, dry_run: bool) -> int:
    """Sent and failed rows older than ``days`` (retention.py)."""
    cutoff = _iso(now - timedelta(days=max(1, int(days))))
    old = (MailMessage.status.in_(("sent", "failed")), MailMessage.created_at < cutoff)
    count = int(db.session.scalar(select(func.count()).select_from(MailMessage).where(*old)) or 0)
    if not dry_run and count:
        db.session.execute(delete(MailMessage).where(*old))
        db.session.commit()
    return count


def init_app(app) -> None:
    @app.before_request
    def _keep_sender_running():
        # Messages left from before a restart still go out: the first request starts the sender.
        if _sender["pid"] != os.getpid():
            start_sender(app)
