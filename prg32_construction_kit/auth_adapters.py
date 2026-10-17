"""Optional school sign-in with OpenID Connect (OIDC) or SAML 2.0.

These work like the Cartridge Store adapters. They stay off unless the
matching ``PRG32_OIDC_*`` or ``PRG32_SAML_*`` environment variables are set and
the optional library (``authlib`` or ``python3-saml``) is installed.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from flask import Flask, Response, redirect, request, url_for

log = logging.getLogger(__name__)


def _enabled(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def enabled_logins(app: Flask) -> list[dict[str, str]]:
    return list(app.extensions.get("prg32_external_logins", []))


def register(app: Flask) -> None:
    app.extensions["prg32_external_logins"] = []
    _register_oidc(app)
    _register_saml(app)


def _finish_external_login(provider: str, external_id: str, email: str, username: str):
    from .auth import principal_from_user, sign_in, upsert_external_user

    user = upsert_external_user(provider=provider, external_id=external_id, email=email, username=username)
    sign_in(principal_from_user(user))
    return redirect(url_for("kit.index"))


def _register_oidc(app: Flask) -> None:
    config = {
        "enabled": os.environ.get("PRG32_OIDC_ENABLED", ""),
        "issuer": os.environ.get("PRG32_OIDC_ISSUER", ""),
        "client_id": os.environ.get("PRG32_OIDC_CLIENT_ID", ""),
        "client_secret": os.environ.get("PRG32_OIDC_CLIENT_SECRET", ""),
        "scope": os.environ.get("PRG32_OIDC_SCOPE", "openid email profile"),
    }
    if not _enabled(config["enabled"]):
        return
    if not config["issuer"] or not config["client_id"] or not config["client_secret"]:
        log.warning("OIDC sign-in disabled because issuer, client id, or client secret is missing")
        return
    try:
        from authlib.integrations.flask_client import OAuth
    except Exception as exc:  # pragma: no cover - optional dependency
        log.warning("OIDC sign-in disabled because authlib is not installed: %s", exc)
        return

    oidc = OAuth(app).register(
        name="prg32_oidc",
        server_metadata_url=config["issuer"].rstrip("/") + "/.well-known/openid-configuration",
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        client_kwargs={"scope": config["scope"]},
    )

    @app.get("/auth/oidc/login")
    def auth_oidc_login():
        return oidc.authorize_redirect(url_for("auth_oidc_callback", _external=True))

    @app.get("/auth/oidc/callback")
    def auth_oidc_callback():
        token = oidc.authorize_access_token()
        profile = token.get("userinfo") or {}
        if not profile.get("sub") or not profile.get("email"):
            profile = oidc.get("userinfo", token=token).json()
        if not profile.get("sub") or not profile.get("email"):
            return Response("The school sign-in did not send an email address.\n", status=401)
        return _finish_external_login("oidc", str(profile["sub"]), str(profile["email"]),
                                      str(profile.get("preferred_username") or profile["email"]))

    app.extensions["prg32_external_logins"].append({"label": "School sign-in (OIDC)", "url": "/auth/oidc/login"})


def _register_saml(app: Flask) -> None:
    config = {key: os.environ.get("PRG32_SAML_" + key.upper(), "") for key in (
        "enabled", "entity_id", "acs_url", "sls_url", "idp_entity_id", "idp_sso_url", "idp_slo_url", "idp_x509cert")}
    if not _enabled(config["enabled"]):
        return
    if not config["idp_sso_url"] or not config["idp_entity_id"] or not config["idp_x509cert"]:
        log.warning("SAML sign-in disabled because IdP SSO URL, entity id, or certificate is missing")
        return
    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
        from onelogin.saml2.settings import OneLogin_Saml2_Settings
    except Exception as exc:  # pragma: no cover - optional dependency
        log.warning("SAML sign-in disabled because python3-saml is not installed: %s", exc)
        return
    base = app.config.get("PREFERRED_URL_SCHEME", "http") + "://localhost"
    config["entity_id"] = config["entity_id"] or base + "/auth/saml/metadata"
    config["acs_url"] = config["acs_url"] or base + "/auth/saml/acs"
    settings = _saml_settings(config)

    @app.get("/auth/saml/login")
    def auth_saml_login():
        return redirect(OneLogin_Saml2_Auth(_saml_request(), settings).login())

    @app.post("/auth/saml/acs")
    def auth_saml_acs():
        saml = OneLogin_Saml2_Auth(_saml_request(), settings)
        saml.process_response()
        if saml.get_errors() or not saml.is_authenticated():
            log.warning("SAML ACS failed: %s %s", saml.get_errors(), saml.get_last_error_reason())
            return Response("SAML authentication failed.\n", status=401)
        attributes = saml.get_attributes()
        email = next((str(attributes[name][0]) for name in ("email", "mail", "Email") if attributes.get(name)), "")
        if not email:
            return Response("The school sign-in did not send an email address.\n", status=401)
        return _finish_external_login("saml", saml.get_nameid() or email, email, email)

    @app.get("/auth/saml/metadata")
    def auth_saml_metadata():
        sp = OneLogin_Saml2_Settings(settings, sp_validation_only=True)
        metadata = sp.get_sp_metadata()
        errors = sp.validate_metadata(metadata)
        if errors:
            return Response("\n".join(errors), status=500, mimetype="text/plain")
        return Response(metadata, mimetype="application/xml")

    app.extensions["prg32_external_logins"].append({"label": "School sign-in (SAML)", "url": "/auth/saml/login"})


def _saml_settings(config: dict[str, str]) -> dict[str, Any]:
    redirect_binding = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
    return {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": config["entity_id"],
            "assertionConsumerService": {"url": config["acs_url"], "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"},
            "singleLogoutService": {"url": config["sls_url"], "binding": redirect_binding},
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        },
        "idp": {
            "entityId": config["idp_entity_id"],
            "singleSignOnService": {"url": config["idp_sso_url"], "binding": redirect_binding},
            "singleLogoutService": {"url": config["idp_slo_url"], "binding": redirect_binding},
            "x509cert": config["idp_x509cert"],
        },
    }


def _saml_request() -> dict[str, Any]:
    return {
        "https": "on" if request.scheme == "https" else "off",
        "http_host": request.host,
        "server_port": request.environ.get("SERVER_PORT"),
        "script_name": request.path,
        "get_data": request.args.copy(),
        "post_data": request.form.copy(),
    }
