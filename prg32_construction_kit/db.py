from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, func, inspect, or_, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column

db = SQLAlchemy()


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class TimestampedModel(db.Model):
    __abstract__ = True
    id: Mapped[str] = mapped_column(db.Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(db.Text, nullable=False)
    # The user who made it. Empty (NULL) means a shared classroom item that
    # every signed-in user can read and only admins can change.
    owner_id: Mapped[int | None] = mapped_column(db.Integer, index=True)


class Project(TimestampedModel):
    __tablename__ = "projects"
    title: Mapped[str] = mapped_column(db.Text, nullable=False)
    description: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    author: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    tags: Mapped[str] = mapped_column(db.Text, nullable=False, default="[]")
    blocks_json: Mapped[str] = mapped_column(db.Text, nullable=False, default="{}")
    game_json: Mapped[str] = mapped_column(db.Text, nullable=False, default="{}")
    # Set when a student deletes the project: it moves to "Recently deleted"
    # and can be restored. Only an admin removes it for good (purge).
    deleted_at: Mapped[str | None] = mapped_column(db.Text, index=True)


class ProjectRevision(db.Model):
    """One saved version of a project, kept so a student can go back to it.

    A revision holds exactly the files of a project archive
    (see project_format.project_files): the manifest, the source, and one file
    per sprite and asset. So restoring a revision or downloading it as a
    .prg32project.zip works the same way as importing an archive.
    """
    __tablename__ = "project_revisions"
    id: Mapped[str] = mapped_column(db.Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(db.Text, db.ForeignKey("projects.id", ondelete="CASCADE"),
                                            nullable=False, index=True)
    owner_id: Mapped[int | None] = mapped_column(db.Integer, index=True)
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False)
    # 1, 2, 3, ... per project: orders revisions saved within the same second.
    seq: Mapped[int] = mapped_column(nullable=False, default=1)
    # Why it was saved: "save" (before a change was stored) or "restore" (before going back).
    reason: Mapped[str] = mapped_column(db.Text, nullable=False, default="save")
    # The prg32.project.json text, the source file text (blocks JSON or C),
    # and the sprite/asset files as a JSON object {path: text}.
    manifest: Mapped[str] = mapped_column(db.Text, nullable=False)
    source: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    assets: Mapped[str] = mapped_column(db.Text, nullable=False, default="{}")
    # A fingerprint of all the files, to skip saving the same version twice in a row.
    digest: Mapped[str] = mapped_column(db.Text, nullable=False)


class Sprite(TimestampedModel):
    __tablename__ = "sprites"
    project_id: Mapped[str | None] = mapped_column(db.Text, db.ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(db.Text, nullable=False)
    width: Mapped[int] = mapped_column(nullable=False, default=16)
    height: Mapped[int] = mapped_column(nullable=False, default=16)
    pixels: Mapped[str] = mapped_column(db.Text, nullable=False, default="[]")
    data_url: Mapped[str] = mapped_column(db.Text, nullable=False, default="")


class Asset(TimestampedModel):
    __tablename__ = "assets"
    project_id: Mapped[str | None] = mapped_column(db.Text, db.ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(db.Text, nullable=False)
    kind: Mapped[str] = mapped_column(db.Text, nullable=False, default="text")
    content_type: Mapped[str] = mapped_column(db.Text, nullable=False, default="text/plain")
    data: Mapped[str] = mapped_column(db.Text, nullable=False, default="{}")


class Artifact(TimestampedModel):
    __tablename__ = "artifacts"
    project_id: Mapped[str | None] = mapped_column(db.Text, db.ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    sprite_id: Mapped[str | None] = mapped_column(db.Text, db.ForeignKey("sprites.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(db.Text, nullable=False)
    name: Mapped[str] = mapped_column(db.Text, nullable=False)
    content_type: Mapped[str] = mapped_column(db.Text, nullable=False, default="text/plain")
    path: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    text_content: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    metadata_json: Mapped[str] = mapped_column("metadata", db.Text, nullable=False, default="{}")


class Build(TimestampedModel):
    __tablename__ = "builds"
    project_id: Mapped[str | None] = mapped_column(db.Text, db.ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(db.Text, nullable=False)
    log: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    c_artifact_id: Mapped[str | None] = mapped_column(db.Text, db.ForeignKey("artifacts.id", ondelete="SET NULL"))
    bundle_artifact_id: Mapped[str | None] = mapped_column(db.Text, db.ForeignKey("artifacts.id", ondelete="SET NULL"))
    metadata_json: Mapped[str] = mapped_column("metadata", db.Text, nullable=False, default="{}")


class PublishProfile(TimestampedModel):
    __tablename__ = "publish_profiles"
    name: Mapped[str] = mapped_column(db.Text, nullable=False)
    store_url: Mapped[str] = mapped_column(db.Text, nullable=False)
    bearer_token: Mapped[str] = mapped_column(db.Text, nullable=False, default="")


RESOURCE_COLUMNS: dict[str, list[str]] = {
    "projects": ["title", "description", "author", "tags", "blocks_json", "game_json", "owner_id"],
    "sprites": ["project_id", "name", "width", "height", "pixels", "data_url", "owner_id"],
    "assets": ["project_id", "name", "kind", "content_type", "data", "owner_id"],
    "artifacts": ["project_id", "sprite_id", "kind", "name", "content_type", "path", "text_content", "metadata", "owner_id"],
    "builds": ["project_id", "status", "log", "c_artifact_id", "bundle_artifact_id", "metadata", "owner_id"],
    "publish_profiles": ["name", "store_url", "bearer_token", "owner_id"],
}
RESOURCE_MODELS = {"projects": Project, "sprites": Sprite, "assets": Asset, "artifacts": Artifact, "builds": Build, "publish_profiles": PublishProfile}
JSON_COLUMNS = {"projects": {"tags", "blocks_json", "game_json"}, "sprites": {"pixels"}, "assets": {"data"}, "artifacts": {"metadata"}, "builds": {"metadata"}, "publish_profiles": set()}
DEFAULTS: dict[str, dict[str, Any]] = {
    "projects": {"title": "Untitled PRG32 Game", "description": "", "author": "Student", "tags": [], "blocks_json": {}, "game_json": {}, "owner_id": None},
    "sprites": {"project_id": None, "name": "sprite", "width": 16, "height": 16, "pixels": [], "data_url": "", "owner_id": None},
    "assets": {"project_id": None, "name": "asset", "kind": "text", "content_type": "text/plain", "data": {}, "owner_id": None},
    "artifacts": {"project_id": None, "sprite_id": None, "kind": "note", "name": "artifact", "content_type": "text/plain", "path": "", "text_content": "", "metadata": {}, "owner_id": None},
    "builds": {"project_id": None, "status": "created", "log": "", "c_artifact_id": None, "bundle_artifact_id": None, "metadata": {}, "owner_id": None},
    "publish_profiles": {"name": "Local Cartridge Store", "store_url": "http://127.0.0.1:5080", "bearer_token": ""},
}


_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
NUMBER_COLUMNS = {"width", "height"}


def _attribute(column: str) -> str:
    return "metadata_json" if column == "metadata" else column


def _encode_value(resource: str, column: str, value: Any) -> Any:
    if column == "owner_id":
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError("owner_id must be a user id") from None
    if column in JSON_COLUMNS[resource]:
        if value is None:
            value = [] if column in {"tags", "pixels"} else {}
        return json.dumps(value, separators=(",", ":"), sort_keys=False)
    if column in NUMBER_COLUMNS:
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{column} must be a whole number") from None
    if value is None:
        return None if column.endswith("_id") else ""
    if isinstance(value, (dict, list)):
        raise ValueError(f"{column} must be text, not a list or object")
    return str(value)


def _decode_value(resource: str, column: str, value: Any) -> Any:
    if column not in JSON_COLUMNS[resource] or value in (None, ""):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def _as_dict(resource: str, instance: TimestampedModel | None) -> dict[str, Any] | None:
    if instance is None:
        return None
    item = {"id": instance.id}
    for column in RESOURCE_COLUMNS[resource]:
        item[column] = _decode_value(resource, column, getattr(instance, _attribute(column)))
    item.update(created_at=instance.created_at, updated_at=instance.updated_at)
    if resource == "projects":
        # Shown, but not in RESOURCE_COLUMNS: only DELETE and restore may change it.
        item["deleted_at"] = instance.deleted_at
    return item


@event.listens_for(Engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    if dbapi_connection.__class__.__module__.split(".")[0] != "sqlite3":
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    # Many students saving at once: wait for the writer lock instead of failing.
    cursor.execute("PRAGMA busy_timeout = 15000")
    cursor.close()


def init_app(app) -> None:
    db.init_app(app)
    with app.app_context():
        init_db()


def init_db() -> None:
    db.create_all()
    _add_missing_owner_columns()
    _add_missing_deleted_at_column()


def _add_missing_owner_columns() -> None:
    """Databases made before accounts existed have no owner_id column yet; add it.

    Their existing rows keep owner_id empty, so they become shared classroom items.
    """
    inspector = inspect(db.engine)
    with db.engine.begin() as connection:
        for table in RESOURCE_MODELS:
            columns = {column["name"] for column in inspector.get_columns(table)}
            if "owner_id" not in columns:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN owner_id INTEGER"))
            connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_owner_id ON {table} (owner_id)"))


def _add_missing_deleted_at_column() -> None:
    """Databases made before "Recently deleted" existed have no projects.deleted_at; add it."""
    columns = {column["name"] for column in inspect(db.engine).get_columns("projects")}
    with db.engine.begin() as connection:
        if "deleted_at" not in columns:
            connection.execute(text("ALTER TABLE projects ADD COLUMN deleted_at TEXT"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_projects_deleted_at ON projects (deleted_at)"))


def list_resources(resource: str, filters: dict[str, str] | None = None, viewer_id: int | None = None,
                   deleted: bool = False) -> list[dict[str, Any]]:
    """List items. With ``viewer_id`` only that user's items and shared items are listed.

    Deleted projects are left out; ``deleted=True`` lists only those instead
    (and then only the viewer's own, never the shared ones).
    """
    model = RESOURCE_MODELS.get(resource)
    if model is None:
        raise KeyError(resource)
    statement = select(model)
    if resource == "projects":
        statement = statement.where(model.deleted_at.is_not(None) if deleted else model.deleted_at.is_(None))
    if deleted and viewer_id is not None:
        statement = statement.where(model.owner_id == viewer_id)
    elif viewer_id is not None:
        statement = statement.where(or_(model.owner_id == viewer_id, model.owner_id.is_(None)))
    for key, value in (filters or {}).items():
        if key in {"project_id", "sprite_id", "kind", "status"} and key in RESOURCE_COLUMNS[resource]:
            statement = statement.where(getattr(model, key) == value)
    statement = statement.order_by(model.updated_at.desc(), model.created_at.desc())
    return [_as_dict(resource, item) for item in db.session.scalars(statement).all()]


def get_resource(resource: str, item_id: str, include_deleted: bool = False) -> dict[str, Any] | None:
    """One item, or None. A deleted project counts as missing unless ``include_deleted``."""
    model = RESOURCE_MODELS.get(resource)
    if model is None:
        raise KeyError(resource)
    instance = db.session.get(model, item_id)
    if resource == "projects" and instance is not None and instance.deleted_at and not include_deleted:
        return None
    return _as_dict(resource, instance)


def _check_payload(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    return payload


def create_resource(resource: str, payload: dict[str, Any]) -> dict[str, Any]:
    model = RESOURCE_MODELS.get(resource)
    if model is None:
        raise KeyError(resource)
    values = {**DEFAULTS[resource], **_check_payload(payload)}
    item_id = values.get("id") or new_id(resource.rstrip("s"))
    if not isinstance(item_id, str) or not _ID_RE.match(item_id):
        raise ValueError("id may only use letters, digits, '-' and '_' (at most 64 characters)")
    now = utcnow()
    attributes = {_attribute(column): _encode_value(resource, column, values.get(column)) for column in RESOURCE_COLUMNS[resource]}
    instance = model(id=item_id, created_at=now, updated_at=now, **attributes)
    try:
        db.session.add(instance)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    created = _as_dict(resource, instance)
    assert created is not None
    return created


def update_resource(resource: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    model = RESOURCE_MODELS.get(resource)
    if model is None:
        raise KeyError(resource)
    payload = _check_payload(payload)
    instance = db.session.get(model, item_id)
    if instance is None:
        return None
    try:
        for column in RESOURCE_COLUMNS[resource]:
            if column in payload:
                setattr(instance, _attribute(column), _encode_value(resource, column, payload[column]))
        instance.updated_at = utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return _as_dict(resource, instance)


def delete_resource(resource: str, item_id: str) -> bool:
    model = RESOURCE_MODELS.get(resource)
    if model is None:
        raise KeyError(resource)
    instance = db.session.get(model, item_id)
    if instance is None:
        return False
    try:
        db.session.delete(instance)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return True


def set_project_deleted(project_id: str, deleted: bool) -> dict[str, Any] | None:
    """Move a project to "Recently deleted" (``deleted=True``) or bring it back."""
    instance = db.session.get(Project, project_id)
    if instance is None:
        return None
    try:
        instance.deleted_at = utcnow() if deleted else None
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return _as_dict("projects", instance)


# --- project revisions ---------------------------------------------------------

def _revision_dict(revision: ProjectRevision, with_files: bool = False) -> dict[str, Any]:
    manifest = json.loads(revision.manifest)
    item: dict[str, Any] = {
        "id": revision.id,
        "project_id": revision.project_id,
        "owner_id": revision.owner_id,
        "created_at": revision.created_at,
        "reason": revision.reason,
        "title": manifest.get("title", ""),
        "authoring_mode": manifest.get("authoring_mode", "blocks"),
        "number": revision.seq,
        "source_bytes": len(revision.source.encode("utf-8")),
        "sprite_count": sum(1 for entry in manifest.get("assets", []) if entry.get("kind") == "sprite"),
        "asset_count": sum(1 for entry in manifest.get("assets", []) if entry.get("kind") == "asset"),
    }
    if with_files:
        files = {"prg32.project.json": revision.manifest, manifest["source"]: revision.source}
        files.update(json.loads(revision.assets))
        item["files"] = {path: content.encode("utf-8") for path, content in files.items()}
    return item


def list_revisions(project_id: str) -> list[dict[str, Any]]:
    """A project's revisions, newest first."""
    statement = (select(ProjectRevision).where(ProjectRevision.project_id == project_id)
                 .order_by(ProjectRevision.created_at.desc(), ProjectRevision.seq.desc()))
    return [_revision_dict(revision) for revision in db.session.scalars(statement).all()]


def get_revision(project_id: str, revision_id: str) -> dict[str, Any] | None:
    """One revision with its files ({path: bytes}), or None if it is not this project's."""
    revision = db.session.get(ProjectRevision, revision_id)
    if revision is None or revision.project_id != project_id:
        return None
    return _revision_dict(revision, with_files=True)


def add_revision(project: dict[str, Any], files: dict[str, bytes], reason: str, keep: int) -> dict[str, Any] | None:
    """Save the project files as a new revision and keep only the newest ``keep``.

    Nothing is saved (and None is returned) when the files are the same as in
    the newest revision: pressing Save twice does not fill the history.
    """
    texts = {path: content.decode("utf-8") for path, content in files.items()}
    manifest_text = texts.pop("prg32.project.json")
    source_path = json.loads(manifest_text)["source"]
    source = texts.pop(source_path, "")
    assets_text = json.dumps(texts, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(json.dumps([manifest_text, source, assets_text]).encode("utf-8")).hexdigest()
    newest = db.session.scalars(select(ProjectRevision).where(ProjectRevision.project_id == project["id"])
                                .order_by(ProjectRevision.seq.desc()).limit(1)).first()
    if newest is not None and newest.digest == digest:
        return None
    revision = ProjectRevision(id=new_id("rev"), project_id=project["id"], owner_id=project.get("owner_id"),
                               created_at=utcnow(), seq=(newest.seq + 1) if newest else 1, reason=reason,
                               manifest=manifest_text, source=source, assets=assets_text, digest=digest)
    try:
        db.session.add(revision)
        db.session.flush()
        old = db.session.scalars(select(ProjectRevision).where(ProjectRevision.project_id == project["id"])
                                 .order_by(ProjectRevision.seq.desc()).offset(max(1, keep))).all()
        for item in old:
            db.session.delete(item)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return _revision_dict(revision)


def update_if_unchanged(resource: str, item_id: str, expected: dict[str, Any], changes: dict[str, Any]) -> bool:
    """Write ``changes`` only if the columns in ``expected`` still hold those values.

    Two browsers can work on the same project at the same time. This lets the
    server store a result computed from what it read earlier without
    overwriting something another browser saved in the meantime.
    """
    model = RESOURCE_MODELS.get(resource)
    if model is None:
        raise KeyError(resource)
    statement = update(model).where(model.id == item_id)
    for column, value in expected.items():
        statement = statement.where(getattr(model, _attribute(column)) == _encode_value(resource, column, value))
    values = {_attribute(column): _encode_value(resource, column, value) for column, value in changes.items()}
    values["updated_at"] = utcnow()
    try:
        result = db.session.execute(statement.values(**values))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return result.rowcount == 1


def release_connection() -> None:
    """Give the database connection back to the pool before slow work (like compiling)."""
    db.session.close()


def count(resource: str) -> int:
    model = RESOURCE_MODELS.get(resource)
    if model is None:
        raise KeyError(resource)
    return int(db.session.scalar(select(func.count()).select_from(model)) or 0)
