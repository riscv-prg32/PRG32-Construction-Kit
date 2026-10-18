from __future__ import annotations

import os
import secrets
from pathlib import Path

from flask import Flask

from . import auth, security, sso
from .config import Config
from .db import db
from .db import init_app as init_db_app
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
    app.before_request(new_csp_nonce)
    app.after_request(browser_security_headers)

    @app.context_processor
    def inject_csp_nonce() -> dict:
        from flask import g

        return {"csp_nonce": getattr(g, "csp_nonce", "")}

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


# The two stylesheets Blockly 11.2.1 writes into the page as <style> elements (its core CSS and
# its renderer CSS). Allowing exactly these, by hash, keeps 'unsafe-inline' out of style-src on
# the static offline pages, which cannot carry a per-request nonce. Kit pages also get a nonce
# (new_csp_nonce) that static/js/csp_nonce.js puts on every <style> a library creates (Monaco).
# A Blockly upgrade changes the hashes; tests/test_browser_offline.py then reports the violation.
BLOCKLY_STYLE_HASHES = ("'sha256-13eeyLxDr6pLorEKUUklmpuV8Z1YLs/1MWMLY8Zk3pA='",
                        "'sha256-0tN7GGHXLmMTzeNJNnrOblI9B4sRETd8GoaYB0Lmw3Q='")


def new_csp_nonce() -> None:
    """A fresh random nonce for this response's CSP (styles created by Blockly and Monaco)."""
    from flask import g

    g.csp_nonce = secrets.token_urlsafe(18)


def content_security_policy(config, nonce: str = "", editor_page: bool = False) -> str:
    """The Content Security Policy for every page (docs/adr/0012-offline-frontend-and-csp.md).

    Everything comes from the kit itself: no CDNs, no inline scripts, no eval.
    'wasm-unsafe-eval' lets the browser compile the PRG32 core (WebAssembly),
    nothing else. A form may post to the kit, and to the linked Cartridge Store
    for single sign-on (templates/sso_redirect.html).
    """
    from urllib.parse import urlsplit

    form_targets = ["'self'"]
    peer = urlsplit(str(config.get("SSO_PEER_URL") or ""))
    if peer.scheme in ("http", "https") and peer.netloc:
        form_targets.append(f"{peer.scheme}://{peer.netloc}")
    return "; ".join([
        "default-src 'self'",
        "script-src 'self' 'wasm-unsafe-eval'",
        "style-src 'self' " + (f"'nonce-{nonce}' " if nonce else "") + " ".join(BLOCKLY_STYLE_HASHES),
        # Only on IDE pages (ADR-0013): Monaco writes code lines as HTML with style="..."
        # attributes, which a nonce cannot cover. Style attributes cannot run script or load
        # anything outside img-src/font-src; <style> elements stay nonce/hash-only (style-src-elem).
        *(["style-src-elem 'self' " + (f"'nonce-{nonce}' " if nonce else "") + " ".join(BLOCKLY_STYLE_HASHES),
           "style-src-attr 'unsafe-inline'"] if editor_page else []),
        "img-src 'self' data: blob:",
        "font-src 'self'",
        "connect-src 'self'",
        "media-src 'self' data: blob:",
        "worker-src 'self'",
        "manifest-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
        "form-action " + " ".join(form_targets),
    ])


def browser_security_headers(response):
    """CSP and friends on every answer; signed-in pages and API answers are never cached."""
    from flask import current_app, g, request

    nonce = getattr(g, "csp_nonce", "") if response.mimetype == "text/html" else ""
    editor_page = request.path.startswith("/ide/")
    response.headers.setdefault("Content-Security-Policy",
                                content_security_policy(current_app.config, nonce, editor_page))
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if request.path.startswith("/static/vendor/"):
        # Versioned folders (vendor/<name>/<version>/): a file there never changes.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif not request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response
