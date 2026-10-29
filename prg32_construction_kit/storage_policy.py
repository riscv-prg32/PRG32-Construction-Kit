"""How much each account stores, and the limits (ADR-0017).

An account's usage is everything it owns, in bytes as stored:

- projects (title, description, Blocks JSON, game JSON) and their saved history;
- sprites and assets;
- artifacts: their text (generated C, assembly) and their files on disk
  (cartridges, Store bundles, debug maps).

The limits come from PRG32_KIT_QUOTA_PROJECTS and PRG32_KIT_QUOTA_MB (0 = none).
Administrators have no limit. Going over is refused with QuotaExceeded before
anything is written; a student frees space by deleting (and asking a teacher to
empty "Recently deleted") or by removing old builds.
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import func, select

from .db import Artifact, Asset, Project, ProjectRevision, Sprite, db
from .messages import text as say


class QuotaExceeded(Exception):
    def __init__(self, message: str, usage: dict[str, Any]):
        super().__init__(message)
        self.usage = usage


def _length(*columns):
    total = 0
    for column in columns:
        total = total + func.coalesce(func.length(column), 0)
    return func.coalesce(func.sum(total), 0)


def usage(owner_id: int, config: dict[str, Any]) -> dict[str, Any]:
    """Bytes and project count of one account, with its limits."""
    projects = db.session.execute(select(func.count(Project.id), _length(Project.title, Project.description,
                                                                          Project.tags, Project.blocks_json,
                                                                          Project.game_json))
                                  .where(Project.owner_id == owner_id)).one()
    history = db.session.scalar(select(_length(ProjectRevision.manifest, ProjectRevision.source, ProjectRevision.assets))
                                .where(ProjectRevision.owner_id == owner_id)) or 0
    sprites = db.session.scalar(select(_length(Sprite.pixels, Sprite.data_url, Sprite.name))
                                .where(Sprite.owner_id == owner_id)) or 0
    assets = db.session.scalar(select(_length(Asset.data, Asset.name)).where(Asset.owner_id == owner_id)) or 0
    texts = db.session.scalar(select(_length(Artifact.text_content)).where(Artifact.owner_id == owner_id)) or 0
    files = 0
    for path in db.session.scalars(select(Artifact.path).where(Artifact.owner_id == owner_id, Artifact.path != "")):
        try:
            files += os.path.getsize(path)
        except OSError:
            pass  # a file removed by retention or by hand counts as nothing
    parts = {"projects": int(projects[1]), "history": int(history), "sprites": int(sprites), "assets": int(assets),
             "artifact_texts": int(texts), "artifact_files": files}
    quota_mb = int(config.get("PRG32_KIT_QUOTA_MB") or 0)
    return {"bytes": sum(parts.values()), "parts": parts, "projects": int(projects[0]),
            "quota_bytes": quota_mb * 1024 * 1024, "quota_projects": int(config.get("PRG32_KIT_QUOTA_PROJECTS") or 0)}


def check(principal, config: dict[str, Any], *, adding_bytes: int = 0, adding_projects: int = 0) -> None:
    """Refuse a change that would take the account over its limits."""
    if not principal.authenticated or principal.is_admin or principal.id is None:
        return
    now = usage(principal.id, config)
    if adding_projects and now["quota_projects"] and now["projects"] + adding_projects > now["quota_projects"]:
        raise QuotaExceeded(say("storage", "You already have {now} projects, the most this kit allows ({now2}). Delete one you no longer need.", now=now['projects'], now2=now['quota_projects']), now)
    if now["quota_bytes"] and (adding_bytes > 0 or adding_projects) and now["bytes"] + max(0, adding_bytes) > now["quota_bytes"]:
        megabytes = now["quota_bytes"] // (1024 * 1024)
        raise QuotaExceeded(say("storage", "Your space is full ({megabytes} MB). Delete old projects or builds, or ask your teacher.", megabytes=megabytes), now)
