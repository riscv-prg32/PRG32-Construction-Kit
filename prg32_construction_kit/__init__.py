from __future__ import annotations

from flask import Flask

from .config import Config
from .db import init_app as init_db_app
from .routes import bp
from .sample_data import seed_if_empty


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False, static_folder="../static", template_folder="../templates")
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    app.config["DATA_DIR"].mkdir(parents=True, exist_ok=True)
    app.config["BUILD_ROOT"].mkdir(parents=True, exist_ok=True)
    app.config["ARTIFACT_ROOT"].mkdir(parents=True, exist_ok=True)

    init_db_app(app)
    app.register_blueprint(bp)

    with app.app_context():
        seed_if_empty(app.config["DEFAULT_STORE_URL"])

    @app.cli.command("init-db")
    def init_db_command():
        from .db import init_db

        init_db()
        seed_if_empty(app.config["DEFAULT_STORE_URL"])
        print("Initialized PRG32-Construction-Kit database.")

    return app
