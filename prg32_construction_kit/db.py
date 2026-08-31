from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, func, select
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


class Project(TimestampedModel):
    __tablename__ = "projects"
    title: Mapped[str] = mapped_column(db.Text, nullable=False)
    description: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    author: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    tags: Mapped[str] = mapped_column(db.Text, nullable=False, default="[]")
    blocks_json: Mapped[str] = mapped_column(db.Text, nullable=False, default="{}")
    game_json: Mapped[str] = mapped_column(db.Text, nullable=False, default="{}")


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
    "projects": ["title", "description", "author", "tags", "blocks_json", "game_json"],
    "sprites": ["project_id", "name", "width", "height", "pixels", "data_url"],
    "assets": ["project_id", "name", "kind", "content_type", "data"],
    "artifacts": ["project_id", "sprite_id", "kind", "name", "content_type", "path", "text_content", "metadata"],
    "builds": ["project_id", "status", "log", "c_artifact_id", "bundle_artifact_id", "metadata"],
    "publish_profiles": ["name", "store_url", "bearer_token"],
}
RESOURCE_MODELS = {"projects": Project, "sprites": Sprite, "assets": Asset, "artifacts": Artifact, "builds": Build, "publish_profiles": PublishProfile}
JSON_COLUMNS = {"projects": {"tags", "blocks_json", "game_json"}, "sprites": {"pixels"}, "assets": {"data"}, "artifacts": {"metadata"}, "builds": {"metadata"}, "publish_profiles": set()}
DEFAULTS: dict[str, dict[str, Any]] = {
    "projects": {"title": "Untitled PRG32 Game", "description": "", "author": "Student", "tags": [], "blocks_json": {}, "game_json": {}},
    "sprites": {"project_id": None, "name": "sprite", "width": 16, "height": 16, "pixels": [], "data_url": ""},
    "assets": {"project_id": None, "name": "asset", "kind": "text", "content_type": "text/plain", "data": {}},
    "artifacts": {"project_id": None, "sprite_id": None, "kind": "note", "name": "artifact", "content_type": "text/plain", "path": "", "text_content": "", "metadata": {}},
    "builds": {"project_id": None, "status": "created", "log": "", "c_artifact_id": None, "bundle_artifact_id": None, "metadata": {}},
    "publish_profiles": {"name": "Local Cartridge Store", "store_url": "http://127.0.0.1:5080", "bearer_token": ""},
}


def _attribute(column: str) -> str:
    return "metadata_json" if column == "metadata" else column


def _encode_value(resource: str, column: str, value: Any) -> Any:
    if column in JSON_COLUMNS[resource]:
        if value is None:
            value = [] if column in {"tags", "pixels"} else {}
        return json.dumps(value, separators=(",", ":"), sort_keys=False)
    return value


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
    return item


@event.listens_for(Engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    if dbapi_connection.__class__.__module__.split(".")[0] != "sqlite3":
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA busy_timeout = 5000")
    cursor.close()


def init_app(app) -> None:
    db.init_app(app)
    with app.app_context():
        init_db()


def init_db() -> None:
    db.create_all()


def list_resources(resource: str, filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
    model = RESOURCE_MODELS.get(resource)
    if model is None:
        raise KeyError(resource)
    statement = select(model)
    for key, value in (filters or {}).items():
        if key in {"project_id", "sprite_id", "kind", "status"} and key in RESOURCE_COLUMNS[resource]:
            statement = statement.where(getattr(model, key) == value)
    statement = statement.order_by(model.updated_at.desc(), model.created_at.desc())
    return [_as_dict(resource, item) for item in db.session.scalars(statement).all()]


def get_resource(resource: str, item_id: str) -> dict[str, Any] | None:
    model = RESOURCE_MODELS.get(resource)
    if model is None:
        raise KeyError(resource)
    return _as_dict(resource, db.session.get(model, item_id))


def create_resource(resource: str, payload: dict[str, Any]) -> dict[str, Any]:
    model = RESOURCE_MODELS.get(resource)
    if model is None:
        raise KeyError(resource)
    values = {**DEFAULTS[resource], **(payload or {})}
    now = utcnow()
    attributes = {_attribute(column): _encode_value(resource, column, values.get(column)) for column in RESOURCE_COLUMNS[resource]}
    instance = model(id=values.get("id") or new_id(resource.rstrip("s")), created_at=now, updated_at=now, **attributes)
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
    instance = db.session.get(model, item_id)
    if instance is None:
        return None
    for column in RESOURCE_COLUMNS[resource]:
        if column in (payload or {}):
            setattr(instance, _attribute(column), _encode_value(resource, column, payload[column]))
    instance.updated_at = utcnow()
    try:
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


def count(resource: str) -> int:
    model = RESOURCE_MODELS.get(resource)
    if model is None:
        raise KeyError(resource)
    return int(db.session.scalar(select(func.count()).select_from(model)) or 0)
