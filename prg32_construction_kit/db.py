from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import current_app, g

RESOURCE_COLUMNS: dict[str, list[str]] = {
    "projects": ["title", "description", "author", "tags", "blocks_json", "game_json"],
    "sprites": ["project_id", "name", "width", "height", "pixels", "data_url"],
    "assets": ["project_id", "name", "kind", "content_type", "data"],
    "artifacts": ["project_id", "sprite_id", "kind", "name", "content_type", "path", "text_content", "metadata"],
    "builds": ["project_id", "status", "log", "c_artifact_id", "bundle_artifact_id", "metadata"],
    "publish_profiles": ["name", "store_url", "bearer_token"],
}

JSON_COLUMNS = {
    "projects": {"tags", "blocks_json", "game_json"},
    "sprites": {"pixels"},
    "assets": {"data"},
    "artifacts": {"metadata"},
    "builds": {"metadata"},
    "publish_profiles": set(),
}

DEFAULTS: dict[str, dict[str, Any]] = {
    "projects": {
        "title": "Untitled PRG32 Game",
        "description": "",
        "author": "Student",
        "tags": [],
        "blocks_json": {},
        "game_json": {},
    },
    "sprites": {
        "project_id": None,
        "name": "sprite",
        "width": 16,
        "height": 16,
        "pixels": [],
        "data_url": "",
    },
    "assets": {
        "project_id": None,
        "name": "asset",
        "kind": "text",
        "content_type": "text/plain",
        "data": {},
    },
    "artifacts": {
        "project_id": None,
        "sprite_id": None,
        "kind": "note",
        "name": "artifact",
        "content_type": "text/plain",
        "path": "",
        "text_content": "",
        "metadata": {},
    },
    "builds": {
        "project_id": None,
        "status": "created",
        "log": "",
        "c_artifact_id": None,
        "bundle_artifact_id": None,
        "metadata": {},
    },
    "publish_profiles": {
        "name": "Local Cartridge Store",
        "store_url": "http://127.0.0.1:5080",
        "bearer_token": "",
    },
}


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db_path: Path = current_app.config["DB_PATH"]
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(_: Exception | None = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            author TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '[]',
            blocks_json TEXT NOT NULL DEFAULT '{}',
            game_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sprites (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            name TEXT NOT NULL,
            width INTEGER NOT NULL DEFAULT 16,
            height INTEGER NOT NULL DEFAULT 16,
            pixels TEXT NOT NULL DEFAULT '[]',
            data_url TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS assets (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            name TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'text',
            content_type TEXT NOT NULL DEFAULT 'text/plain',
            data TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            sprite_id TEXT,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'text/plain',
            path TEXT NOT NULL DEFAULT '',
            text_content TEXT NOT NULL DEFAULT '',
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL,
            FOREIGN KEY(sprite_id) REFERENCES sprites(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS builds (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            status TEXT NOT NULL,
            log TEXT NOT NULL DEFAULT '',
            c_artifact_id TEXT,
            bundle_artifact_id TEXT,
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(c_artifact_id) REFERENCES artifacts(id) ON DELETE SET NULL,
            FOREIGN KEY(bundle_artifact_id) REFERENCES artifacts(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS publish_profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            store_url TEXT NOT NULL,
            bearer_token TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_sprites_project ON sprites(project_id);
        CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id);
        CREATE INDEX IF NOT EXISTS idx_artifacts_project ON artifacts(project_id);
        CREATE INDEX IF NOT EXISTS idx_builds_project ON builds(project_id);
        """
    )
    db.commit()


def _encode_value(resource: str, column: str, value: Any) -> Any:
    if column in JSON_COLUMNS.get(resource, set()):
        if value is None:
            value = [] if column in {"tags", "pixels"} else {}
        return json.dumps(value, indent=None, sort_keys=False)
    return value


def _decode_row(resource: str, row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    for column in JSON_COLUMNS.get(resource, set()):
        if column in item:
            raw = item[column]
            try:
                item[column] = json.loads(raw) if raw not in (None, "") else None
            except json.JSONDecodeError:
                item[column] = raw
    return item


def list_resources(resource: str, filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
    if resource not in RESOURCE_COLUMNS:
        raise KeyError(resource)
    filters = filters or {}
    where: list[str] = []
    params: list[Any] = []
    for key, value in filters.items():
        if key in {"project_id", "sprite_id", "kind", "status"} and key in RESOURCE_COLUMNS[resource]:
            where.append(f"{key} = ?")
            params.append(value)
    sql = f"SELECT * FROM {resource}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY updated_at DESC, created_at DESC"
    rows = get_db().execute(sql, params).fetchall()
    return [_decode_row(resource, row) for row in rows if row is not None]


def get_resource(resource: str, item_id: str) -> dict[str, Any] | None:
    if resource not in RESOURCE_COLUMNS:
        raise KeyError(resource)
    row = get_db().execute(f"SELECT * FROM {resource} WHERE id = ?", (item_id,)).fetchone()
    return _decode_row(resource, row)


def create_resource(resource: str, payload: dict[str, Any]) -> dict[str, Any]:
    if resource not in RESOURCE_COLUMNS:
        raise KeyError(resource)
    now = utcnow()
    defaults = DEFAULTS.get(resource, {})
    values: dict[str, Any] = {**defaults, **(payload or {})}
    item_id = values.get("id") or new_id(resource.rstrip("s"))
    columns = ["id", *RESOURCE_COLUMNS[resource], "created_at", "updated_at"]
    row_values = [item_id]
    for column in RESOURCE_COLUMNS[resource]:
        row_values.append(_encode_value(resource, column, values.get(column)))
    row_values.extend([now, now])
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {resource} ({', '.join(columns)}) VALUES ({placeholders})"
    get_db().execute(sql, row_values)
    get_db().commit()
    created = get_resource(resource, item_id)
    assert created is not None
    return created


def update_resource(resource: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if resource not in RESOURCE_COLUMNS:
        raise KeyError(resource)
    current = get_resource(resource, item_id)
    if current is None:
        return None
    payload = payload or {}
    assignments: list[str] = []
    params: list[Any] = []
    for column in RESOURCE_COLUMNS[resource]:
        if column in payload:
            assignments.append(f"{column} = ?")
            params.append(_encode_value(resource, column, payload[column]))
    assignments.append("updated_at = ?")
    params.append(utcnow())
    params.append(item_id)
    get_db().execute(f"UPDATE {resource} SET {', '.join(assignments)} WHERE id = ?", params)
    get_db().commit()
    return get_resource(resource, item_id)


def delete_resource(resource: str, item_id: str) -> bool:
    if resource not in RESOURCE_COLUMNS:
        raise KeyError(resource)
    cur = get_db().execute(f"DELETE FROM {resource} WHERE id = ?", (item_id,))
    get_db().commit()
    return cur.rowcount > 0


def count(resource: str) -> int:
    row = get_db().execute(f"SELECT COUNT(*) AS c FROM {resource}").fetchone()
    return int(row["c"])
