"""Optional school sign-in with SAML 2.0, and the list of school sign-in buttons.

OpenID Connect lives in identity.py (PKCE, several providers, ADR-0016). SAML stays
off unless the ``PRG32_SAML_*`` environment variables are set and ``python3-saml``
is installed; it uses the same accounts by issuer (the IdP entity id) + subject
(the NameID), never joined to another account by email.
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
    """The school sign-in buttons: every enabled OIDC provider (identity.py), then SAML."""
    from .identity import enabled_logins as oidc_logins

    return oidc_logins() + list(app.extensions.get("prg32_external_logins", []))


def register(app: Flask) -> None:
    app.extensions["prg32_external_logins"] = []
    _register_saml(app)


def _finish_external_login(issuer: str, subject: str, email: str, username: str):
    """SAML: the same issuer + subject accounts as OIDC (identity.py, ADR-0016), never joined by email."""
    from . import security
    from .auth import principal_from_user, sign_in
    from .identity import SignInRefused, complete_external_sign_in

    try:
        user, created = complete_external_sign_in(provider_slug="saml", issuer=issuer, subject=subject, email=email,
                                                  username=username)
    except SignInRefused as refusal:
        security.record("saml_sign_in", target_type="identity_provider", target_id="saml", outcome="refused",
                        metadata={"reason": refusal.reason}, actor=None)
        return Response(str(refusal) + "\n", status=403)
    principal = principal_from_user(user)
    sign_in(principal)
    security.record("saml_sign_in", target_type="identity_provider", target_id="saml", actor=principal,
                    metadata={"account_created": created})
    return redirect(url_for("kit.index"))


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
        if not saml.get_nameid():
            return Response("The school sign-in did not send a NameID.\n", status=401)
        return _finish_external_login(config["idp_entity_id"], saml.get_nameid(), email, email)

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
