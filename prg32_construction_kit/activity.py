"""The activity log: what each person did in the kit, for admins (docs/activity_and_statistics.md).

Every page and API request is written to ``activity_events`` *after* it is answered: who
(an account, or a visitor without one), what (the kind of action, e.g. ``compile``), the
route pattern, the answer's status and how long it took. The Activity page shows the log per
person; the Statistics page (statistics.py) is made from the same rows.

GDPR by design (Art. 5 and 25; docs/privacy/ropa.json, "activity_log"):

- **No content.** Never a request body, a query string, a header value, a project's text or a
  file name: only the route *pattern* (``/api/projects/<project_id>/package``) and, for one
  object, its id.
- **Visitors without an account** get a pseudonym that changes every day: a keyed hash of
  their address and browser made with a random *daily salt*. The salt of a past day is deleted,
  so nobody, not even an admin with the database, can link two days of one visitor or turn the
  pseudonym back into an address. A browser that sends Global Privacy Control (``Sec-GPC: 1``)
  or Do Not Track (``DNT: 1``) is counted without a pseudonym.
- **Addresses are shortened** to their network (IPv4 /24, IPv6 /48), never kept whole (the
  audit log, security.py, keeps whole addresses for security; this log does not need them).
- **Browsers** are kept as a family and a system (``Firefox · Windows``), not the full string.
- **Storage limitation.** Rows older than ``PRG32_KIT_ACTIVITY_DAYS`` (90) are deleted every day
  (and by ``flask prg32-retention``); the switch ``PRG32_KIT_ACTIVITY_LOG`` turns logging off.
- **Rights.** A person's rows are in their data export and removed when they are erased
  (privacy.py). **Accountability.** Opening one person's activity and every download is
  written to the audit log.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import ipaddress
import re
import secrets
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from flask import Blueprint, Response, current_app, g, jsonify, render_template, request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Mapped, mapped_column

from . import settings as site_settings
from .auth import admin_required
from .db import db, utcnow
from .messages import body as message_body, of as message_of, text as say

bp = Blueprint("activity", __name__)

# Never logged: files, the service worker, and the admin's own monitoring reads (they poll).
SKIPPED_PREFIXES = ("/static/", "/.well-known/")
SKIPPED_PATHS = {"/favicon.ico", "/service-worker.js"}
SKIPPED_READS = ("/api/admin/activity", "/api/admin/statistics", "/api/admin/mail")

ACTORS = ("user", "token", "guest")


class ActivityEvent(db.Model):
    """One answered request: who, what kind of action, which route, the outcome."""
    __tablename__ = "activity_events"
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False, index=True)
    day: Mapped[str] = mapped_column(db.Text, nullable=False, index=True)          # YYYY-MM-DD (UTC)
    actor: Mapped[str] = mapped_column(db.Text, nullable=False)                    # user, token, guest
    user_id: Mapped[int | None] = mapped_column(db.Integer, index=True)
    visitor: Mapped[str] = mapped_column(db.Text, nullable=False, default="", index=True)   # guest pseudonym
    category: Mapped[str] = mapped_column(db.Text, nullable=False, index=True)
    method: Mapped[str] = mapped_column(db.Text, nullable=False)
    route: Mapped[str] = mapped_column(db.Text, nullable=False)
    object_id: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    status: Mapped[int] = mapped_column(db.Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    network: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    agent: Mapped[str] = mapped_column(db.Text, nullable=False, default="")


class ActivitySalt(db.Model):
    """Today's random salt for visitor pseudonyms; yesterday's is deleted (unlinkable days)."""
    __tablename__ = "activity_salts"
    day: Mapped[str] = mapped_column(db.Text, primary_key=True)
    salt: Mapped[str] = mapped_column(db.Text, nullable=False)


# --- what kind of action a request is ----------------------------------------------------------

# (method or "*", route prefix, category): the first match wins. The route is Flask's pattern;
# the generic /api/<resource> routes are matched with the resource filled in.
CATEGORY_RULES: tuple[tuple[str, str, str], ...] = (
    ("POST", "/auth/login", "sign_in"),
    ("POST", "/auth/oidc/", "sign_in"),
    ("GET", "/auth/oidc/", "sign_in"),
    ("POST", "/auth/sso/", "sign_in"),
    ("*", "/auth/logout", "sign_out"),
    ("*", "/auth/register", "register"),
    ("*", "/auth/", "account"),
    ("POST", "/api/guest/run", "guest_run"),
    ("*", "/api/guest/", "guest_tools"),
    ("POST", "/api/projects/<project_id>/package", "compile"),
    ("POST", "/api/projects/<project_id>/run", "run"),
    ("POST", "/api/projects/<project_id>/check", "check"),
    ("POST", "/api/projects/<project_id>/convert", "generate_code"),
    ("POST", "/api/projects/<project_id>/convert_to", "convert_type"),
    ("*", "/api/projects/<project_id>/revisions", "history"),
    ("*", "/api/projects/<project_id>/audio", "audio"),
    ("*", "/api/projects/<project_id>/cloud", "cloud"),
    ("*", "/api/projects/<project_id>/export", "export"),
    ("*", "/api/projects/<project_id>/archive", "export"),
    ("*", "/api/projects/import", "project_create"),
    ("POST", "/api/projects/<project_id>/duplicate", "project_create"),
    ("POST", "/api/examples/", "project_create"),
    ("POST", "/api/projects", "project_create"),
    ("PUT", "/api/projects/", "project_save"),
    ("DELETE", "/api/projects/", "project_delete"),
    ("*", "/api/projects", "project_read"),
    ("*", "/api/sprites", "sprites"),
    ("*", "/api/assets", "assets"),
    ("*", "/api/artifacts", "artifacts"),
    ("*", "/api/builds", "builds"),
    ("*", "/api/publish", "publish"),
    ("*", "/api/deploy", "deploy"),
    ("*", "/api/evaluation", "evaluate"),
    ("*", "/api/cloud", "cloud"),
    ("*", "/cloud/", "cloud"),
    ("*", "/api/classes", "classes"),
    ("*", "/api/me/privacy", "privacy"),
    ("*", "/api/privacy", "privacy"),
    ("*", "/api/admin", "admin"),
    ("*", "/api/users", "admin"),
    ("*", "/admin/", "admin"),
    ("*", "/api/sso/", "sync"),
    ("*", "/docs/", "docs"),
    ("GET", "/documentation", "docs"),
    ("*", "/api/", "api_other"),
    ("GET", "/", "page_view"),
)


def category_of(method: str, route: str) -> str:
    for wanted, prefix, category in CATEGORY_RULES:
        if (wanted == "*" or wanted == method) and route.startswith(prefix):
            return category
    return "other"


def _route() -> str:
    """The route pattern, with a generic resource name filled in (never the real path)."""
    rule = request.url_rule.rule if request.url_rule is not None else "(no route)"
    resource = (request.view_args or {}).get("resource")
    if resource and re.fullmatch(r"[a-z_]{1,32}", str(resource)):
        rule = rule.replace("<resource>", str(resource))
    return rule[:200]


def _object_id() -> str:
    """The id of the one object a route is about (a project, a build ...), when it names one."""
    args = request.view_args or {}
    for key in ("project_id", "item_id", "sprite_id", "asset_id", "artifact_id", "deployment_id",
                "evaluation_id", "class_id", "user_id", "slug"):
        if args.get(key) not in (None, ""):
            return str(args[key])[:80]
    return ""


# --- who it was ----------------------------------------------------------------------------------

def network_of(address: str) -> str:
    """The address shortened to its network: 192.0.2.17 -> 192.0.2.0/24, IPv6 -> /48."""
    try:
        ip = ipaddress.ip_address(str(address or "").strip())
    except ValueError:
        return ""
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    prefix = 24 if ip.version == 4 else 48
    return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))


_BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"),
             ("Safari/", "Safari"))
_SYSTEMS = (("Windows", "Windows"), ("Android", "Android"), ("iPhone", "iOS"), ("iPad", "iOS"),
            ("CrOS", "ChromeOS"), ("Mac OS X", "macOS"), ("Linux", "Linux"))


def agent_of(user_agent: str) -> str:
    """``Firefox · Windows``: the browser family and system only, never the full string."""
    text = str(user_agent or "")
    if not text:
        return ""
    browser = next((name for mark, name in _BROWSERS if mark in text), "")
    if not browser:
        browser = "script" if re.match(r"(curl|python|wget|go-http|java)", text, re.I) else "other"
    system = next((name for mark, name in _SYSTEMS if mark in text), "")
    return f"{browser} · {system}" if system else browser


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _salt(day: str) -> str:
    """Today's salt (made once, shared by every process); a new day also clears old salts and rows."""
    cache = current_app.extensions.setdefault("prg32_activity_salt", {})
    if cache.get("day") == day:
        return cache["salt"]
    row = db.session.get(ActivitySalt, day)
    if row is None:
        db.session.add(ActivitySalt(day=day, salt=secrets.token_hex(32)))
        try:
            db.session.commit()
        except Exception:   # noqa: BLE001 - another process made today's salt first
            db.session.rollback()
        row = db.session.get(ActivitySalt, day)
        db.session.execute(delete(ActivitySalt).where(ActivitySalt.day != day))
        expire(int(site_settings.get("PRG32_KIT_ACTIVITY_DAYS") or 90), datetime.now(timezone.utc), dry_run=False)
        db.session.commit()
    cache.update(day=day, salt=row.salt)
    return row.salt


def visitor_of(address: str, user_agent: str, day: str) -> str:
    """A visitor's pseudonym for one day: unlinkable to other days once that day's salt is gone."""
    digest = hmac.new(_salt(day).encode(), f"{address}\x1f{user_agent}".encode(), hashlib.sha256).hexdigest()
    return "guest-" + digest[:10]


def opted_out() -> bool:
    """Global Privacy Control or Do Not Track: count the request, give the visitor no pseudonym."""
    return request.headers.get("Sec-GPC", "").strip() == "1" or request.headers.get("DNT", "").strip() == "1"


# --- writing the log ---------------------------------------------------------------------------

def _skip() -> bool:
    path = request.path
    if request.method in ("OPTIONS", "HEAD") or path in SKIPPED_PATHS or path.startswith(SKIPPED_PREFIXES):
        return True
    return request.method == "GET" and path.startswith(SKIPPED_READS)


def _started() -> None:
    g.activity_started = time.monotonic()


def _record(response):
    """Write one row for this request (after it is answered; a failure never breaks the answer)."""
    try:
        if _skip() or not site_settings.get("PRG32_KIT_ACTIVITY_LOG"):
            return response
        from . import security
        from .auth import current_principal

        principal = current_principal()
        address = security.client_address()
        day = _today()
        if principal.authenticated:
            actor = "token" if principal.token_scopes is not None else "user"
            user_id, visitor = principal.id, ""
        else:
            actor, user_id = "guest", None
            visitor = "" if opted_out() else visitor_of(address, request.headers.get("User-Agent", ""), day)
        route = _route()
        started = getattr(g, "activity_started", None)
        db.session.rollback()          # whatever the request left uncommitted is not ours to save
        db.session.add(ActivityEvent(
            created_at=utcnow(), day=day, actor=actor, user_id=user_id, visitor=visitor,
            category=category_of(request.method, route), method=request.method, route=route,
            object_id=_object_id(), status=int(response.status_code),
            duration_ms=int((time.monotonic() - started) * 1000) if started else 0,
            network=network_of(address), agent=agent_of(request.headers.get("User-Agent", ""))))
        db.session.commit()
    except Exception:   # noqa: BLE001 - logging must never change what the person gets
        db.session.rollback()
        current_app.logger.exception("could not write an activity event")
    return response


def expire(days: int, now: datetime, dry_run: bool) -> int:
    """Rows older than ``days`` (also run by retention.py)."""
    cutoff = (now - timedelta(days=max(1, int(days)))).date().isoformat()
    count = int(db.session.scalar(select(func.count()).select_from(ActivityEvent)
                                  .where(ActivityEvent.day < cutoff)) or 0)
    if not dry_run and count:
        db.session.execute(delete(ActivityEvent).where(ActivityEvent.day < cutoff))
        db.session.commit()
    return count


# --- reading it (admins) -----------------------------------------------------------------------

def day_range(args) -> tuple[str, str]:
    """``?from=YYYY-MM-DD&to=YYYY-MM-DD`` (both included); the last 30 days when not given."""
    today = datetime.now(timezone.utc).date()
    try:
        last = date.fromisoformat(args.get("to")) if args.get("to") else today
        first = date.fromisoformat(args.get("from")) if args.get("from") else last - timedelta(days=29)
    except ValueError:
        raise ValueError(say("activity", "dates are written YYYY-MM-DD")) from None
    if first > last:
        first, last = last, first
    if (last - first).days > 731:
        first = last - timedelta(days=731)
    return first.isoformat(), last.isoformat()


def usernames(user_ids) -> dict[int, str]:
    from .auth import User

    ids = {int(item) for item in user_ids if item is not None}
    if not ids:
        return {}
    return dict(db.session.execute(select(User.id, User.username).where(User.id.in_(ids))).all())


def _filtered(args):
    first, last = day_range(args)
    statement = select(ActivityEvent).where(ActivityEvent.day >= first, ActivityEvent.day <= last)
    if args.get("user_id"):
        try:
            statement = statement.where(ActivityEvent.user_id == int(args["user_id"]))
        except ValueError:
            raise ValueError(say("activity", "user_id must be a whole number")) from None
    if args.get("visitor"):
        statement = statement.where(ActivityEvent.visitor == str(args["visitor"])[:40])
    if args.get("actor") in ACTORS:
        statement = statement.where(ActivityEvent.actor == args["actor"])
    if args.get("category"):
        statement = statement.where(ActivityEvent.category == str(args["category"])[:40])
    if args.get("outcome") == "error":
        statement = statement.where(ActivityEvent.status >= 400)
    return statement


def as_dict(event: ActivityEvent, names: dict[int, str]) -> dict[str, Any]:
    return {"id": event.id, "created_at": event.created_at, "actor": event.actor, "user_id": event.user_id,
            "username": names.get(event.user_id, "") if event.user_id is not None else "",
            "visitor": event.visitor, "category": event.category, "method": event.method, "route": event.route,
            "object_id": event.object_id, "status": event.status, "duration_ms": event.duration_ms,
            "network": event.network, "agent": event.agent}


def _audit_reading(args, action: str) -> None:
    """Accountability: looking at one person's activity, or downloading the log, is itself logged."""
    from . import security

    if action == "activity_export" or args.get("user_id") or args.get("visitor"):
        security.record(action, target_type="user" if args.get("user_id") else "activity",
                        target_id=args.get("user_id") or args.get("visitor") or "",
                        metadata={"from": args.get("from", ""), "to": args.get("to", ""),
                                  "category": args.get("category", "")})


@bp.get("/admin/activity")
@admin_required
def activity_page():
    return render_template("admin_activity.html", categories=sorted({rule[2] for rule in CATEGORY_RULES} | {"other"}))


@bp.get("/api/admin/activity")
@admin_required
def api_activity():
    """The log, newest first: ?from&to&user_id&visitor&actor&category&outcome=error&before=<id>&limit."""
    try:
        statement = _filtered(request.args)
        limit = max(1, min(int(request.args.get("limit", "200")), 1000))
        if request.args.get("before"):
            statement = statement.where(ActivityEvent.id < int(request.args["before"]))
    except ValueError as error:
        return jsonify({**message_body(error if message_of(error) else
                                       say("activity", "limit and before must be whole numbers"))}), 400
    events = db.session.scalars(statement.order_by(ActivityEvent.id.desc()).limit(limit)).all()
    names = usernames(event.user_id for event in events)
    _audit_reading(request.args, "activity_view")
    return jsonify({"events": [as_dict(event, names) for event in events],
                    "next_before": events[-1].id if len(events) == limit else None,
                    "enabled": bool(site_settings.get("PRG32_KIT_ACTIVITY_LOG")),
                    "days_kept": int(site_settings.get("PRG32_KIT_ACTIVITY_DAYS") or 90)})


@bp.get("/api/admin/activity/people")
@admin_required
def api_activity_people():
    """Who was active in the range: accounts and (per day) visitors without one, busiest first."""
    try:
        first, last = day_range(request.args)
    except ValueError as error:
        return jsonify({**message_body(error)}), 400
    in_range = (ActivityEvent.day >= first, ActivityEvent.day <= last)
    users = db.session.execute(
        select(ActivityEvent.user_id, func.count(), func.count(func.distinct(ActivityEvent.day)),
               func.min(ActivityEvent.created_at), func.max(ActivityEvent.created_at))
        .where(*in_range, ActivityEvent.user_id.is_not(None)).group_by(ActivityEvent.user_id)
        .order_by(func.count().desc()).limit(500)).all()
    names = usernames(row[0] for row in users)
    guests = db.session.execute(
        select(ActivityEvent.visitor, ActivityEvent.day, func.count(), func.min(ActivityEvent.created_at),
               func.max(ActivityEvent.created_at), func.max(ActivityEvent.agent), func.max(ActivityEvent.network))
        .where(*in_range, ActivityEvent.actor == "guest", ActivityEvent.visitor != "")
        .group_by(ActivityEvent.visitor, ActivityEvent.day).order_by(func.count().desc()).limit(500)).all()
    unnamed = db.session.scalar(select(func.count()).select_from(ActivityEvent).where(
        *in_range, ActivityEvent.actor == "guest", ActivityEvent.visitor == "")) or 0
    return jsonify({
        "from": first, "to": last,
        "users": [{"user_id": row[0], "username": names.get(row[0], f"(deleted #{row[0]})"), "requests": row[1],
                   "active_days": row[2], "first_seen": row[3], "last_seen": row[4]} for row in users],
        "guests": [{"visitor": row[0], "day": row[1], "requests": row[2], "first_seen": row[3], "last_seen": row[4],
                    "agent": row[5], "network": row[6]} for row in guests],
        "guest_requests_without_pseudonym": int(unnamed)})


CSV_COLUMNS = ("id", "created_at", "actor", "user_id", "username", "visitor", "category", "method", "route",
               "object_id", "status", "duration_ms", "network", "agent")


def csv_response(rows: list[dict[str, Any]], columns, filename: str) -> Response:
    """A CSV download (UTF-8 with a BOM, so spreadsheet programs read accents right)."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        # A cell starting with = + - @ is a formula in a spreadsheet: quote it as text.
        writer.writerow({key: ("'" + value if isinstance(value, str) and value and value[0] in "=+-@" else value)
                         for key, value in row.items()})
    return Response("﻿" + buffer.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@bp.get("/api/admin/activity.csv")
@admin_required
def api_activity_csv():
    """The filtered log as CSV (at most 100 000 rows); pseudonymised unless ?names=1."""
    from .privacy import pseudonym

    try:
        statement = _filtered(request.args)
        first, last = day_range(request.args)
    except ValueError as error:
        return jsonify({**message_body(error)}), 400
    events = db.session.scalars(statement.order_by(ActivityEvent.id).limit(100_000)).all()
    names = usernames(event.user_id for event in events) if request.args.get("names") == "1" else {}
    rows = []
    for event in events:
        row = as_dict(event, names)
        if not names and event.user_id is not None:
            row["user_id"], row["username"] = "", pseudonym(event.user_id)
        rows.append(row)
    _audit_reading({**request.args, "from": first, "to": last}, "activity_export")
    return csv_response(rows, CSV_COLUMNS, f"prg32-activity-{first}-{last}.csv")


def init_app(app) -> None:
    app.register_blueprint(bp)
    app.before_request(_started)
    app.after_request(_record)
