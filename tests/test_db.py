from __future__ import annotations

from sqlalchemy import inspect

from prg32_construction_kit.db import db


def test_sqlalchemy_creates_the_compatible_resource_schema(app):
    with app.app_context():
        assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///")
        tables = set(inspect(db.engine).get_table_names())
        assert tables >= {"projects", "sprites", "assets", "artifacts", "builds", "publish_profiles"}
        project_columns = {column["name"] for column in inspect(db.engine).get_columns("projects")}
        assert project_columns >= {"id", "title", "tags", "blocks_json", "game_json", "created_at", "updated_at"}
