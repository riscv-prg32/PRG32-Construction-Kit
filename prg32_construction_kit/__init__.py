from __future__ import annotations

import os
import secrets
from pathlib import Path

from flask import Flask

from . import auth, security, sso
from .config import Config
from .db import db, init_app as init_db_app
from .routes import bp
from .sample_data import seed_if_empty


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False, static_folder="../static", template_folder="../templates")
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{app.config['DB_PATH']}"

    app.config["DATA_DIR"].mkdir(parents=True, exist_ok=True)
    app.config["BUILD_ROOT"].mkdir(parents=True, exist_ok=True)
    app.config["ARTIFACT_ROOT"].mkdir(parents=True, exist_ok=True)

    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _stored_secret_key(Path(app.config["DATA_DIR"]) / "secret_key")
    if app.config.get("SSO_SECRET") and len(str(app.config["SSO_SECRET"])) < 32:
        app.logger.warning("PRG32_SSO_SECRET is shorter than 32 characters; single sign-on stays off")

    init_db_app(app)
    auth.init_app(app)
    sso.init_app(app)
    app.register_blueprint(bp)

    with app.app_context():
        auth.bootstrap_admin(app)
        security.forget_expired()  # old sign-in counters
        seed_if_empty(app.config["DEFAULT_STORE_URL"])
        # gunicorn --preload builds the app once and then forks workers; each
        # worker must open its own database connections instead of sharing these.
        db.engine.dispose()

    @app.cli.command("init-db")
    def init_db_command():
        from .db import init_db

        init_db()
        auth.bootstrap_admin(app)
        seed_if_empty(app.config["DEFAULT_STORE_URL"])
        print("Initialized PRG32-Construction-Kit database.")

    return app


def _stored_secret_key(path: Path) -> str:
    """Read the cookie-signing key, creating a random one the first time."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    with os.fdopen(fd, "w", encoding="utf-8") as fp:
        fp.write(key)
    return key
