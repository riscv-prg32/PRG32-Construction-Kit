"""Statistics for admins: how the kit is used, as charts, tables and CSV files (docs/activity_and_statistics.md).

Everything here is counted, never copied: the numbers come from the activity log
(activity.py) and from the kit's own tables (accounts, projects, builds, publications).

- **summary**: accounts, active people, visitors without an account, requests, errors, speed;
- **daily**: one row per day (active accounts, visitors, requests, compiles, guest runs, errors);
- **hours**: requests per hour of the day (UTC), accounts and visitors apart;
- **categories**: what people do (compile, save, run, ...), with how many accounts and visitors;
- **per_user**: one row per account active in the range.

GDPR (docs/privacy/ropa.json, "activity_log"): visitors without an account are counted as
*visitor-days* (a pseudonym lives one day, so the same visitor on two days counts twice: the kit
cannot and does not link them). The per-account table and its CSV show a pseudonym instead of
the username unless the admin asks for names (``?names=1``), and every CSV download is written
to the audit log. The numbers follow the activity log's retention (``PRG32_KIT_ACTIVITY_DAYS``).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import case, func, select

from .activity import ActivityEvent, csv_response, day_range, usernames
from .auth import admin_required
from .db import Build, Project, db
from .messages import body as message_body, text as say

bp = Blueprint("statistics", __name__)

TABLES = ("summary", "daily", "hours", "categories", "per_user")
COLUMNS = {
    "summary": ("metric", "value"),
    "daily": ("day", "active_users", "guest_visitors", "requests", "page_views", "compiles", "guest_runs",
              "project_saves", "errors", "new_accounts"),
    "hours": ("hour", "user_requests", "guest_requests"),
    "categories": ("category", "requests", "users", "guest_visitor_days", "errors", "avg_ms"),
    "per_user": ("user", "role", "kit_role", "requests", "active_days", "page_views", "project_saves", "compiles",
                 "runs", "errors", "projects_owned", "builds", "builds_ok", "first_seen", "last_seen"),
}


def _days(first: str, last: str) -> list[str]:
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    return [(start + timedelta(days=offset)).isoformat() for offset in range((end - start).days + 1)]


def _count_if(condition):
    return func.sum(case((condition, 1), else_=0))


def collect(first: str, last: str, *, names: bool = False) -> dict[str, Any]:
    """Every table of the Statistics page for the days ``first``..``last`` (both included)."""
    from .auth import User
    from .privacy import pseudonym
    from .publishing import PublishAttempt

    events = ActivityEvent
    in_range = (events.day >= first, events.day <= last)
    is_guest = events.actor == "guest"
    guest_visitor_day = case((is_guest & (events.visitor != ""), events.day + ":" + events.visitor))
    after, before = first + "T", last + "T99"     # created_at is ISO text: the whole of both days

    # --- daily -----------------------------------------------------------------------------
    rows = db.session.execute(
        select(events.day, func.count(func.distinct(events.user_id)), func.count(func.distinct(guest_visitor_day)),
               func.count(), _count_if(events.category == "page_view"), _count_if(events.category == "compile"),
               _count_if(events.category == "guest_run"), _count_if(events.category == "project_save"),
               _count_if(events.status >= 500))
        .where(*in_range).group_by(events.day)).all()
    by_day = {row[0]: row for row in rows}
    new_accounts = dict(db.session.execute(
        select(func.substr(User.created_at, 1, 10), func.count())
        .where(User.created_at >= after, User.created_at <= before)
        .group_by(func.substr(User.created_at, 1, 10))).all())
    daily = []
    for day in _days(first, last):
        row = by_day.get(day)
        values = [int(value or 0) for value in row[1:]] if row else [0] * 8
        daily.append(dict(zip(COLUMNS["daily"], [day, *values, int(new_accounts.get(day, 0))])))

    # --- hours -------------------------------------------------------------------------------
    hour = func.substr(events.created_at, 12, 2)
    hours = {int(row[0]): row for row in db.session.execute(
        select(hour, _count_if(~is_guest), _count_if(is_guest)).where(*in_range).group_by(hour)).all()
        if str(row[0] or "").isdigit()}
    hour_rows = [{"hour": number, "user_requests": int(hours[number][1] or 0) if number in hours else 0,
                  "guest_requests": int(hours[number][2] or 0) if number in hours else 0} for number in range(24)]

    # --- categories -------------------------------------------------------------------------
    categories = [{"category": row[0], "requests": int(row[1]), "users": int(row[2]), "guest_visitor_days": int(row[3]),
                   "errors": int(row[4] or 0), "avg_ms": int(row[5] or 0)}
                  for row in db.session.execute(
                      select(events.category, func.count(), func.count(func.distinct(events.user_id)),
                             func.count(func.distinct(guest_visitor_day)), _count_if(events.status >= 500),
                             func.avg(events.duration_ms))
                      .where(*in_range).group_by(events.category).order_by(func.count().desc())).all()]

    # --- per account ------------------------------------------------------------------------
    people = db.session.execute(
        select(events.user_id, func.count(), func.count(func.distinct(events.day)),
               _count_if(events.category == "page_view"), _count_if(events.category == "project_save"),
               _count_if(events.category == "compile"), _count_if(events.category == "run"),
               _count_if(events.status >= 500), func.min(events.created_at), func.max(events.created_at))
        .where(*in_range, events.user_id.is_not(None)).group_by(events.user_id)
        .order_by(func.count().desc())).all()
    ids = [row[0] for row in people]
    accounts = {user.id: user for user in db.session.scalars(select(User).where(User.id.in_(ids)))} if ids else {}
    owned = dict(db.session.execute(select(Project.owner_id, func.count()).where(
        Project.owner_id.in_(ids), Project.deleted_at.is_(None)).group_by(Project.owner_id)).all()) if ids else {}
    built = {row[0]: row for row in db.session.execute(
        select(Build.owner_id, func.count(), _count_if(Build.status == "ready"))
        .where(Build.owner_id.in_(ids), Build.created_at >= after, Build.created_at <= before)
        .group_by(Build.owner_id)).all()} if ids else {}
    per_user = []
    for row in people:
        account = accounts.get(row[0])
        shown = (account.username if account else f"(deleted #{row[0]})") if names else pseudonym(row[0])
        builds = built.get(row[0])
        per_user.append({"user_id": row[0] if names else None, "user": shown,
                         "role": account.role if account else "", "kit_role": account.kit_role if account else "",
                         "requests": int(row[1]), "active_days": int(row[2]), "page_views": int(row[3] or 0),
                         "project_saves": int(row[4] or 0), "compiles": int(row[5] or 0), "runs": int(row[6] or 0),
                         "errors": int(row[7] or 0), "projects_owned": int(owned.get(row[0], 0)),
                         "builds": int(builds[1]) if builds else 0, "builds_ok": int(builds[2] or 0) if builds else 0,
                         "first_seen": row[8], "last_seen": row[9]})

    # --- summary -----------------------------------------------------------------------------
    totals = db.session.execute(
        select(func.count(), func.count(func.distinct(events.user_id)), func.count(func.distinct(guest_visitor_day)),
               _count_if(is_guest), _count_if(is_guest & (events.visitor == "")), _count_if(events.status >= 500),
               _count_if((events.status >= 400) & (events.status < 500)), func.avg(events.duration_ms),
               _count_if(events.category == "page_view")).where(*in_range)).one()
    durations = db.session.scalars(select(events.duration_ms).where(*in_range).order_by(events.duration_ms)).all()
    p95 = durations[min(len(durations) - 1, int(len(durations) * 0.95))] if durations else 0
    roles = dict(db.session.execute(select(User.role, func.count()).group_by(User.role)).all())
    kit_roles = dict(db.session.execute(select(User.kit_role, func.count()).group_by(User.kit_role)).all())
    builds = dict(db.session.execute(select(Build.status, func.count())
                                     .where(Build.created_at >= after, Build.created_at <= before)
                                     .group_by(Build.status)).all())
    projects = int(db.session.scalar(select(func.count()).select_from(Project).where(Project.deleted_at.is_(None))) or 0)
    publications = int(db.session.scalar(select(func.count()).select_from(PublishAttempt).where(
        PublishAttempt.created_at >= after, PublishAttempt.created_at <= before)) or 0)
    summary = {
        "days": len(daily), "accounts": sum(int(value) for value in roles.values()),
        "accounts_by_role": {key: int(value) for key, value in roles.items()},
        "accounts_by_kit_role": {key: int(value) for key, value in kit_roles.items()},
        "new_accounts": sum(item["new_accounts"] for item in daily),
        "active_users": int(totals[1] or 0), "guest_visitor_days": int(totals[2] or 0),
        "requests": int(totals[0] or 0), "page_views": int(totals[8] or 0), "guest_requests": int(totals[3] or 0),
        "guest_requests_without_pseudonym": int(totals[4] or 0), "server_errors": int(totals[5] or 0),
        "refused_requests": int(totals[6] or 0), "avg_ms": int(totals[7] or 0), "p95_ms": int(p95 or 0),
        "projects": projects, "builds": sum(int(value) for value in builds.values()),
        "builds_by_status": {key: int(value) for key, value in builds.items()}, "publications": publications,
    }
    return {"from": first, "to": last, "names": names, "summary": summary, "daily": daily, "hours": hour_rows,
            "categories": categories, "per_user": per_user}


def summary_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """The summary as metric/value rows (nested counts become ``accounts_by_role.admin``...)."""
    rows = []
    for key, value in summary.items():
        if isinstance(value, dict):
            rows += [{"metric": f"{key}.{name}", "value": count} for name, count in sorted(value.items())]
        else:
            rows.append({"metric": key, "value": value})
    return rows


@bp.get("/admin/statistics")
@admin_required
def statistics_page():
    return render_template("admin_statistics.html", tables=TABLES)


@bp.get("/api/admin/statistics")
@admin_required
def api_statistics():
    """Every table for ?from=YYYY-MM-DD&to=YYYY-MM-DD (the last 30 days by default); ?names=1 for usernames."""
    try:
        first, last = day_range(request.args)
    except ValueError as error:
        return jsonify({**message_body(error)}), 400
    names = request.args.get("names") == "1"
    if names:
        from . import security

        security.record("statistics_names", target_type="statistics", metadata={"from": first, "to": last})
    return jsonify(collect(first, last, names=names))


@bp.get("/api/admin/statistics/<table>.csv")
@admin_required
def api_statistics_csv(table: str):
    from . import security

    if table not in TABLES:
        return jsonify({**message_body(say("statistics", "unknown table {table}", table=repr(table)))}), 404
    try:
        first, last = day_range(request.args)
    except ValueError as error:
        return jsonify({**message_body(error)}), 400
    names = request.args.get("names") == "1"
    data = collect(first, last, names=names)
    rows = summary_rows(data["summary"]) if table == "summary" else data[table]
    security.record("statistics_export", target_type="statistics", target_id=table,
                    metadata={"from": first, "to": last, "names": names})
    return csv_response(rows, COLUMNS[table], f"prg32-statistics-{table}-{first}-{last}.csv")


def init_app(app) -> None:
    app.register_blueprint(bp)
