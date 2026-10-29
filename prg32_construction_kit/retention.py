"""What the kit keeps, and for how long (ADR-0017).

- Projects in "Recently deleted" for PRG32_KIT_TRASH_DAYS are removed for good,
  with their history, assets, builds, artifacts and build folders.
- Each project keeps its newest PRG32_KIT_KEEP_BUILDS builds; older builds lose
  their database rows, their artifacts (cartridges, bundles, debug maps) and their
  ``<build_id>/`` folder. The newest builds are never touched.
- A ``build_...`` folder that no build refers to any more (an interrupted build) is
  removed once it is an hour old, so a build that is running is never touched.
- Switched-off accounts (ADR-0016) are listed for an administrator to review; their
  items are never deleted automatically.
- Audit events older than PRG32_KIT_AUDIT_DAYS (365) are removed, and sign-up links that
  expired or were used more than a day ago (ADR-0022, docs/privacy/retention.md). Answered
  rights requests go PRG32_KIT_PRIVACY_REQUEST_DAYS after their answer, when that is set.

Run it with ``flask --app app prg32-retention`` (shows what it would do) or
``--apply``, or ``POST /api/admin/retention``; builds are also pruned for a project
after each compile.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import literal_column, select

from .db import Artifact, Build, Project, db, delete_resource

BUILD_FOLDER = re.compile(r"^build_[0-9a-f]{12}$")
ORPHAN_AGE_SECONDS = 3600


def _iso_days_ago(days: int, now: datetime) -> str:
    return (now - timedelta(days=days)).replace(microsecond=0).isoformat()


def _folder(build_root: Path, build_id: str) -> Path | None:
    folder = (Path(build_root) / build_id).resolve()
    root = Path(build_root).resolve()
    return folder if BUILD_FOLDER.fullmatch(build_id) and folder.parent == root and folder.is_dir() else None


def _build_artifacts(build: Build) -> list[str]:
    """Ids of the artifacts a build made: its sources, bundle, cartridges and debug maps."""
    try:
        metadata = json.loads(build.metadata_json or "{}")
    except ValueError:
        metadata = {}
    ids = {build.c_artifact_id, build.bundle_artifact_id, (metadata or {}).get("asm_artifact_id")}
    for artifact in db.session.scalars(select(Artifact).where(Artifact.project_id == build.project_id)):
        try:
            data = json.loads(artifact.metadata_json or "{}")
        except ValueError:
            data = {}
        if isinstance(data, dict) and data.get("build_id") == build.id:
            ids.add(artifact.id)
    return sorted(item for item in ids if item)


def delete_artifact(artifact_id: str) -> bool:
    """Delete an artifact and its file, when the file is the kit's own and no other artifact uses it.

    Build outputs live in their build's folder (removed with it); uploads live in
    ARTIFACT_ROOT. A path outside the kit's folders, or the database and key files, is
    never touched (routes.stored_file decides, as for downloads)."""
    from flask import current_app

    from .routes import stored_file

    artifact = db.session.get(Artifact, artifact_id)
    if artifact is None:
        return False
    path = stored_file(artifact.path)
    shared = path is not None and db.session.scalar(
        select(literal_column("COUNT(*)")).select_from(Artifact).where(Artifact.path == artifact.path,
                                                                        Artifact.id != artifact_id))
    deleted = delete_resource("artifacts", artifact_id)
    if deleted and path is not None and not shared and path.is_relative_to(Path(current_app.config["ARTIFACT_ROOT"]).resolve()):
        path.unlink(missing_ok=True)
    return deleted


def _remove_build(build: Build, build_root: Path, dry_run: bool) -> dict[str, Any]:
    artifacts = _build_artifacts(build)
    folder = _folder(build_root, build.id)
    if not dry_run:
        delete_resource("builds", build.id)
        for artifact_id in artifacts:
            delete_artifact(artifact_id)
        if folder is not None:
            shutil.rmtree(folder, ignore_errors=True)
    return {"build": build.id, "project": build.project_id, "artifacts": len(artifacts), "folder": folder is not None}


def prune_builds(project_id: str, keep: int, build_root: Path, dry_run: bool = False) -> list[dict[str, Any]]:
    """Keep the newest ``keep`` builds of a project; remove the older ones completely."""
    # Newest first: by time, and by insertion order (SQLite rowid) within the same second.
    builds = db.session.scalars(select(Build).where(Build.project_id == project_id)
                                .order_by(Build.created_at.desc(), literal_column("builds.rowid").desc())).all()
    return [_remove_build(build, build_root, dry_run) for build in builds[max(0, keep):]]


def purge_project(project_id: str, build_root: Path) -> None:
    """Remove a project for good, with everything that only exists because of it."""
    prune_builds(project_id, 0, build_root)
    for artifact_id in db.session.scalars(select(Artifact.id).where(Artifact.project_id == project_id)).all():
        delete_artifact(artifact_id)
    delete_resource("projects", project_id)


def apply(config: dict[str, Any], *, dry_run: bool = True, now: datetime | None = None) -> dict[str, Any]:
    from .auth import User

    now = now or datetime.now(timezone.utc)
    build_root = Path(config["BUILD_ROOT"])
    report: dict[str, Any] = {"dry_run": dry_run, "purged_projects": [], "pruned_builds": [],
                              "removed_folders": [], "switched_off_accounts": []}
    cutoff = _iso_days_ago(int(config["PRG32_KIT_TRASH_DAYS"]), now)
    for project in db.session.scalars(select(Project).where(Project.deleted_at.is_not(None),
                                                            Project.deleted_at <= cutoff)).all():
        report["purged_projects"].append({"project": project.id, "title": project.title, "deleted_at": project.deleted_at})
        if not dry_run:
            purge_project(project.id, build_root)
    keep = int(config["PRG32_KIT_KEEP_BUILDS"])
    for project_id in db.session.scalars(select(Project.id).where(Project.deleted_at.is_(None))).all():
        report["pruned_builds"].extend(prune_builds(project_id, keep, build_root, dry_run))
    known = set(db.session.scalars(select(Build.id)))
    if build_root.is_dir():
        for folder in sorted(build_root.iterdir()):
            if (folder.is_dir() and BUILD_FOLDER.fullmatch(folder.name) and folder.name not in known
                    and time.time() - folder.stat().st_mtime > ORPHAN_AGE_SECONDS):
                report["removed_folders"].append(folder.name)
                if not dry_run:
                    shutil.rmtree(folder, ignore_errors=True)
    for user in db.session.scalars(select(User).where(User.disabled_at.is_not(None)).order_by(User.disabled_at)):
        report["switched_off_accounts"].append({"id": user.id, "username": user.username, "since": user.disabled_at})
    report.update(_expire_records(config, now, dry_run))
    return report


def _expire_records(config: dict[str, Any], now: datetime, dry_run: bool) -> dict[str, int]:
    """The audit log, sign-up links, the activity log and sent mail are kept only as long as
    docs/privacy/retention.md says."""
    from sqlalchemy import delete, or_

    from .auth import RegistrationToken
    from .security import AuditEvent

    audit_cutoff = _iso_days_ago(int(config.get("PRG32_KIT_AUDIT_DAYS", 365)), now)
    link_cutoff = _iso_days_ago(1, now)
    old_events = select(AuditEvent.id).where(AuditEvent.created_at < audit_cutoff)
    old_links = select(RegistrationToken.id).where(or_(RegistrationToken.expires_at < link_cutoff,
                                                       RegistrationToken.used_at < link_cutoff))
    counts = {"expired_audit_events": len(db.session.scalars(old_events).all()),
              "expired_signup_links": len(db.session.scalars(old_links).all()), "expired_privacy_requests": 0}
    from .privacy import FINAL_STATES, PrivacyRequest

    request_days = int(config.get("PRG32_KIT_PRIVACY_REQUEST_DAYS", 0))
    old_requests = select(PrivacyRequest.id).where(PrivacyRequest.status.in_(FINAL_STATES),
                                                   PrivacyRequest.completed_at < _iso_days_ago(request_days, now))
    if request_days > 0:
        counts["expired_privacy_requests"] = len(db.session.scalars(old_requests).all())
        if not dry_run:
            db.session.execute(delete(PrivacyRequest).where(PrivacyRequest.id.in_(old_requests)))
    from . import activity, mail_queue

    counts["expired_activity_events"] = activity.expire(int(config.get("PRG32_KIT_ACTIVITY_DAYS", 90)), now, dry_run)
    counts["expired_mail"] = mail_queue.expire(int(config.get("PRG32_KIT_MAIL_DAYS", 30)), now, dry_run)
    if not dry_run:
        db.session.execute(delete(AuditEvent).where(AuditEvent.created_at < audit_cutoff))
        db.session.execute(delete(RegistrationToken).where(or_(RegistrationToken.expires_at < link_cutoff,
                                                               RegistrationToken.used_at < link_cutoff)))
        db.session.commit()
    return counts


def delete_account_items(user_id: int, build_root: Path) -> dict[str, int]:
    """Everything an account owns, for ``DELETE /api/users/<id>?with_items=1``."""
    from .db import RESOURCE_MODELS

    counts: dict[str, int] = {}
    projects = db.session.scalars(select(Project.id).where(Project.owner_id == user_id)).all()
    for project_id in projects:
        purge_project(project_id, build_root)
    counts["projects"] = len(projects)
    for resource in ("builds", "artifacts", "sprites", "assets", "publish_profiles"):
        model = RESOURCE_MODELS[resource]
        rows = db.session.scalars(select(model.id).where(model.owner_id == user_id)).all()
        for item_id in rows:
            if resource == "builds":
                folder = _folder(build_root, item_id)
                if folder is not None:
                    shutil.rmtree(folder, ignore_errors=True)
            if resource == "artifacts":
                delete_artifact(item_id)
            else:
                delete_resource(resource, item_id)
        counts[resource] = len(rows)
    # AudioStudio sample sounds live in one folder per owner (audio_studio_api.store_sample).
    from flask import current_app

    shutil.rmtree(Path(current_app.config["ARTIFACT_ROOT"]) / "audio" / str(int(user_id)), ignore_errors=True)
    return counts
