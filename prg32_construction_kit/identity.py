"""School sign-in: OpenID Connect with PKCE, accounts keyed by issuer + subject (ADR-0016).

How a sign-in works, in order:

1. ``/auth/oidc/<provider>/login`` makes a random state, nonce and PKCE verifier,
   keeps them in the (signed) session for 10 minutes and sends the browser to the
   school's sign-in page with the S256 code challenge.
2. The school sends the browser back to ``/auth/oidc/<provider>/callback`` with a
   code. The kit checks the state (once only), swaps code + verifier for tokens at
   the provider's token endpoint and verifies the ID token: signature with a key from
   the provider's JWKS (RS256, PS256 or ES256 only), issuer, audience, expiry, nonce.
3. The person is found by (issuer, subject) in ``external_identities``. A new person
   gets a new account, unless an account already uses that email: then sign-in is
   refused and they link the school account from the Account page while signed in.
   Accounts are never joined because two emails match.

Administrators configure the providers (``/api/admin/identity_providers``); the client
secret is a reference (``env:NAME`` or ``file:/path``), never stored or shown.
``PRG32_OIDC_*`` environment variables still configure one provider called ``oidc``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlencode, urlsplit

import requests
from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from . import security
from .db import db, utcnow
from . import settings as site_settings
from .messages import body as message_body, fields as message_fields, text as say

FLOW_SECONDS = 600          # a sign-in must come back within 10 minutes
MAX_FLOWS = 5               # sign-ins started in parallel (several tabs) per browser
CLOCK_SKEW = 120            # seconds of clock difference accepted for exp/iat
CACHE_SECONDS = 3600        # discovery documents and keys
JWKS_REFRESH_SECONDS = 60   # an unknown key id fetches the keys again at most this often
MAX_RESPONSE_BYTES = 256 * 1024
HTTP_TIMEOUT = 10
ALLOWED_ALGORITHMS = ("RS256", "PS256", "ES256")
ACADEMIC_ROLES = ("student", "teacher", "facilitator")  # what a provider claim may grant; never a global role
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,31}$")


# --- tables -------------------------------------------------------------------

class IdentityProvider(db.Model):
    __tablename__ = "identity_providers"
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(db.Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(db.Text, nullable=False)
    issuer: Mapped[str] = mapped_column(db.Text, nullable=False)
    client_id: Mapped[str] = mapped_column(db.Text, nullable=False)
    client_secret_ref: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    scopes: Mapped[str] = mapped_column(db.Text, nullable=False, default="openid email profile")
    role_claim: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    role_map: Mapped[str] = mapped_column(db.Text, nullable=False, default="{}")
    new_account_role: Mapped[str] = mapped_column(db.Text, nullable=False, default="student")
    allowed_domains: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    enabled: Mapped[int] = mapped_column(db.Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)
    updated_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)


class ExternalIdentity(db.Model):
    __tablename__ = "external_identities"
    __table_args__ = (UniqueConstraint("issuer", "subject", name="external_identity_issuer_subject"),)
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
                                         index=True)
    provider: Mapped[str] = mapped_column(db.Text, nullable=False)
    issuer: Mapped[str] = mapped_column(db.Text, nullable=False)
    subject: Mapped[str] = mapped_column(db.Text, nullable=False)
    email: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)
    last_login: Mapped[str | None] = mapped_column(db.Text)


# --- providers ----------------------------------------------------------------

@dataclass
class Provider:
    slug: str
    name: str
    issuer: str
    client_id: str
    client_secret_ref: str = ""
    scopes: str = "openid email profile"
    role_claim: str = ""
    role_map: dict[str, str] = field(default_factory=dict)
    new_account_role: str = "student"
    allowed_domains: tuple[str, ...] = ()
    from_environment: bool = False

    def secret(self) -> str:
        return resolve_secret(self.client_secret_ref)

    def public(self) -> dict[str, Any]:
        return {"slug": self.slug, "name": self.name, "issuer": self.issuer, "client_id": self.client_id,
                "client_secret_ref": self.client_secret_ref, "scopes": self.scopes, "role_claim": self.role_claim,
                "role_map": self.role_map, "new_account_role": self.new_account_role,
                "allowed_domains": list(self.allowed_domains), "from_environment": self.from_environment}


def resolve_secret(reference: str) -> str:
    """``env:NAME`` or ``file:/path``; empty means a public client (PKCE only)."""
    reference = str(reference or "").strip()
    if not reference:
        return ""
    if reference.startswith("env:"):
        return os.environ.get(reference[4:], "")
    if reference.startswith("file:"):
        try:
            with open(reference[5:], encoding="utf-8") as handle:
                return handle.read().strip()
        except OSError:
            return ""
    raise ValueError(say("identity", "client secret must be a reference: env:NAME or file:/path"))


def check_endpoint(url: str) -> str:
    """https, or plain http to this computer only (a provider for tests or a lab)."""
    parts = urlsplit(str(url or ""))
    if parts.scheme == "https" and parts.hostname:
        return url
    if parts.scheme == "http" and parts.hostname:
        try:
            if ipaddress.ip_address(parts.hostname).is_loopback:
                return url
        except ValueError:
            if parts.hostname == "localhost":
                return url
    raise ValueError(say("identity", "identity provider addresses must use https: {url}", url=repr(url)))


def _environment_provider() -> Provider | None:
    if str(os.environ.get("PRG32_OIDC_ENABLED", "")).strip().lower() not in {"1", "true", "yes"}:
        return None
    issuer = os.environ.get("PRG32_OIDC_ISSUER", "").strip()
    client_id = os.environ.get("PRG32_OIDC_CLIENT_ID", "").strip()
    if not issuer or not client_id:
        return None
    return Provider(slug="oidc", name=os.environ.get("PRG32_OIDC_NAME", "School sign-in"), issuer=issuer,
                    client_id=client_id, client_secret_ref="env:PRG32_OIDC_CLIENT_SECRET",
                    scopes=os.environ.get("PRG32_OIDC_SCOPE", "openid email profile"), from_environment=True)


def _from_row(row: IdentityProvider) -> Provider:
    try:
        role_map = json.loads(row.role_map or "{}")
    except ValueError:
        role_map = {}
    return Provider(slug=row.slug, name=row.name, issuer=row.issuer, client_id=row.client_id,
                    client_secret_ref=row.client_secret_ref, scopes=row.scopes, role_claim=row.role_claim,
                    role_map=role_map if isinstance(role_map, dict) else {}, new_account_role=row.new_account_role,
                    allowed_domains=tuple(row.allowed_domains.split()))


def providers(enabled_only: bool = True) -> list[Provider]:
    found = [_from_row(row) for row in db.session.scalars(select(IdentityProvider).order_by(IdentityProvider.slug))
             if row.enabled or not enabled_only]
    environment = _environment_provider()
    if environment and all(item.slug != environment.slug for item in found):
        found.insert(0, environment)
    return found


def provider(slug: str) -> Provider | None:
    return next((item for item in providers() if item.slug == slug), None)


def enabled_logins() -> list[dict[str, str]]:
    return [{"label": item.name, "url": f"/auth/oidc/{item.slug}/login"} for item in providers()]


# --- HTTP to providers ----------------------------------------------------------
# One function, so tests can put an in-process identity provider behind it.

def _http(method: str, url: str, data: dict[str, str] | None = None,
          auth: tuple[str, str] | None = None) -> tuple[int, Any]:
    check_endpoint(url)
    response = requests.request(method, url, data=data, auth=auth, timeout=HTTP_TIMEOUT, allow_redirects=False,
                                stream=True, headers={"Accept": "application/json"})
    body = response.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
    if len(body) > MAX_RESPONSE_BYTES:
        raise OidcError(say("identity", "the identity provider sent too much data"))
    try:
        return response.status_code, json.loads(body or b"null")
    except ValueError as error:
        raise OidcError(say("identity", "the identity provider did not answer with JSON")) from error


http: Callable[..., tuple[int, Any]] = _http

_discovery: dict[str, tuple[float, dict[str, Any]]] = {}
_keys: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def now_seconds() -> float:
    """The clock for flows, caches and token times (one function, so tests can move it alone)."""
    return time.time()


class OidcError(Exception):
    """A sign-in that must not go on. The message is safe to show (no tokens, no secrets)."""


def discovery(item: Provider) -> dict[str, Any]:
    cached = _discovery.get(item.issuer)
    if cached and 0 <= now_seconds() - cached[0] < CACHE_SECONDS:   # a clock that went back = stale
        return cached[1]
    status, document = http("GET", item.issuer.rstrip("/") + "/.well-known/openid-configuration")
    if status != 200 or not isinstance(document, dict):
        raise OidcError(say("identity", "the school's sign-in service could not be reached"))
    if document.get("issuer") != item.issuer:
        raise OidcError(say("identity", "the school's sign-in service names a different issuer"))
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        check_endpoint(document.get(key, ""))
    _discovery[item.issuer] = (now_seconds(), document)
    return document


def signing_keys(jwks_uri: str, refresh: bool = False) -> list[dict[str, Any]]:
    cached = _keys.get(jwks_uri)
    age = now_seconds() - cached[0] if cached else -1
    fresh = cached and 0 <= age < CACHE_SECONDS           # a negative age (the clock went back) is stale
    recently = cached and 0 <= age < JWKS_REFRESH_SECONDS
    if cached and (fresh and not refresh or refresh and recently):
        return cached[1]
    status, document = http("GET", jwks_uri)
    keys = document.get("keys") if status == 200 and isinstance(document, dict) else None
    if not isinstance(keys, list):
        raise OidcError(say("identity", "the school's sign-in keys could not be read"))
    _keys[jwks_uri] = (now_seconds(), keys)
    return keys


def forget_caches() -> None:
    _discovery.clear()
    _keys.clear()


# --- ID token verification ---------------------------------------------------------

def _b64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _public_key(jwk: dict[str, Any]):
    from cryptography.hazmat.primitives.asymmetric import ec, rsa

    if jwk.get("kty") == "RSA":
        return rsa.RSAPublicNumbers(int.from_bytes(_b64(jwk["e"]), "big"),
                                    int.from_bytes(_b64(jwk["n"]), "big")).public_key()
    if jwk.get("kty") == "EC" and jwk.get("crv") == "P-256":
        return ec.EllipticCurvePublicNumbers(int.from_bytes(_b64(jwk["x"]), "big"),
                                             int.from_bytes(_b64(jwk["y"]), "big"), ec.SECP256R1()).public_key()
    raise OidcError(say("identity", "the school's sign-in key has an unsupported type"))


def _verify_signature(algorithm: str, jwk: dict[str, Any], signed: bytes, signature: bytes) -> None:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, padding, utils

    key = _public_key(jwk)
    try:
        if algorithm == "RS256":
            key.verify(signature, signed, padding.PKCS1v15(), hashes.SHA256())
        elif algorithm == "PS256":
            key.verify(signature, signed, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
                       hashes.SHA256())
        elif algorithm == "ES256":
            if len(signature) != 64:
                raise OidcError(say("identity", "the sign-in token's signature is not valid"))
            der = utils.encode_dss_signature(int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:], "big"))
            key.verify(der, signed, ec.ECDSA(hashes.SHA256()))
        else:
            raise OidcError(say("identity", "the sign-in token uses an algorithm the kit does not accept"))
    except (InvalidSignature, TypeError, ValueError) as error:
        raise OidcError(say("identity", "the sign-in token's signature is not valid")) from error


def verify_id_token(token: str, item: Provider, jwks_uri: str, nonce: str, now: float | None = None) -> dict[str, Any]:
    """The verified claims of an ID token, or OidcError."""
    parts = str(token or "").split(".")
    if len(parts) != 3:
        raise OidcError(say("identity", "the school did not send a valid sign-in token"))
    try:
        header = json.loads(_b64(parts[0]))
        claims = json.loads(_b64(parts[1]))
        signature = _b64(parts[2])
    except (ValueError, TypeError) as error:
        raise OidcError(say("identity", "the school did not send a valid sign-in token")) from error
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise OidcError(say("identity", "the school did not send a valid sign-in token"))
    algorithm = header.get("alg")
    if algorithm not in ALLOWED_ALGORITHMS:  # never "none", never a shared-secret (HMAC) algorithm
        raise OidcError(say("identity", "the sign-in token uses an algorithm the kit does not accept"))
    kid = header.get("kid")

    def matching(keys: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [key for key in keys if (kid is None or key.get("kid") == kid) and key.get("use", "sig") == "sig"]

    candidates = matching(signing_keys(jwks_uri))
    if not candidates:
        candidates = matching(signing_keys(jwks_uri, refresh=True))  # the provider rotated its keys
    if not candidates:
        raise OidcError(say("identity", "the sign-in token was signed with an unknown key"))
    _verify_signature(algorithm, candidates[0], (parts[0] + "." + parts[1]).encode("ascii"), signature)
    now = now_seconds() if now is None else now
    if claims.get("iss") != item.issuer:
        raise OidcError(say("identity", "the sign-in token comes from another issuer"))
    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if item.client_id not in audiences:
        raise OidcError(say("identity", "the sign-in token is meant for another application"))
    if len(audiences) > 1 and claims.get("azp") != item.client_id:
        raise OidcError(say("identity", "the sign-in token is meant for another application"))
    if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] < now - CLOCK_SKEW:
        raise OidcError(say("identity", "the sign-in token has expired: sign in again"))
    if isinstance(claims.get("iat"), (int, float)) and claims["iat"] > now + CLOCK_SKEW:
        raise OidcError(say("identity", "the sign-in token is dated in the future"))
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise OidcError(say("identity", "the sign-in token does not belong to this sign-in"))
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise OidcError(say("identity", "the sign-in token has no subject"))
    return claims


# --- accounts -------------------------------------------------------------------

def identities_of(user_id: int) -> list[dict[str, str]]:
    rows = db.session.scalars(select(ExternalIdentity).where(ExternalIdentity.user_id == user_id)
                              .order_by(ExternalIdentity.id)).all()
    return [{"id": row.id, "provider": row.provider, "issuer": row.issuer, "email": row.email,
             "created_at": row.created_at, "last_login": row.last_login or ""} for row in rows]


def migrate_legacy_identities() -> None:
    """Accounts linked before ADR-0016 (users.external_provider/external_id) keep their link."""
    from .auth import User

    for user in db.session.scalars(select(User).where(User.external_id.is_not(None))):
        issuer = f"legacy:{user.external_provider or 'external'}"
        exists = db.session.scalar(select(ExternalIdentity.id).where(ExternalIdentity.issuer == issuer,
                                                                     ExternalIdentity.subject == user.external_id))
        if exists is None:
            db.session.add(ExternalIdentity(user_id=user.id, provider=user.external_provider or "external",
                                            issuer=issuer, subject=user.external_id, email=user.email))
    db.session.commit()


class SignInRefused(Exception):
    """Shown to the person; recorded in the audit log with ``reason``."""

    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.reason = reason


def academic_role(claims: dict[str, Any], item: Provider) -> str:
    """The academic role for a new account: from the configured claim, else the provider's default."""
    values = claims.get(item.role_claim) if item.role_claim else None
    values = values if isinstance(values, list) else [values] if values else []
    for value in values:
        mapped = item.role_map.get(str(value))
        if mapped in ACADEMIC_ROLES:
            return mapped
    return item.new_account_role if item.new_account_role in ACADEMIC_ROLES else "student"


def complete_external_sign_in(*, provider_slug: str, issuer: str, subject: str, email: str, username: str = "",
                              kit_role: str = "student", allowed_domains: tuple[str, ...] = ()):
    """The account for (issuer, subject): found, or new. Never joined to another account by email."""
    from .auth import User, create_user, find_user_by_email, normalize_email, unique_username

    row = db.session.scalar(select(ExternalIdentity).where(ExternalIdentity.issuer == issuer,
                                                           ExternalIdentity.subject == subject))
    email = normalize_email(email)
    if row is not None:
        user = db.session.get(User, row.user_id)
        if user is None or user.disabled_at:
            raise SignInRefused(say("identity", "This account is switched off. Ask your teacher."), "account_disabled")
        row.last_login = utcnow()
        if email:
            row.email = email
        db.session.commit()
        return user, False
    if not email:
        raise SignInRefused(say("identity", "The school sign-in did not send an email address, so no account can be made."),
                            "no_email")
    if allowed_domains and email.rsplit("@", 1)[-1] not in allowed_domains:
        raise SignInRefused(say("identity", "This school sign-in is not for your email address."), "domain_not_allowed")
    if find_user_by_email(email) is not None:
        raise SignInRefused(say("identity", "An account with this email already exists. Sign in to it the usual way, then link your school account on the Account page."), "email_in_use")
    user = create_user(unique_username(username or email, email), email, None,
                       role=site_settings.get("DEFAULT_ROLE"))
    user.kit_role = kit_role if kit_role in ACADEMIC_ROLES else "student"
    db.session.add(ExternalIdentity(user_id=user.id, provider=provider_slug, issuer=issuer, subject=subject,
                                    email=email, last_login=utcnow()))
    db.session.commit()
    return user, True


# --- the sign-in flow ----------------------------------------------------------------

bp = Blueprint("identity", __name__)


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _redirect_uri(slug: str) -> str:
    base = str(site_settings.get("PUBLIC_URL") or "").rstrip("/")
    path = url_for("identity.callback", slug=slug)
    return base + path if base else url_for("identity.callback", slug=slug, _external=True)


def _start(item: Provider, intent: str, user_id: int | None = None) -> str:
    """Remember a new sign-in in the session; the address of the school's sign-in page."""
    document = discovery(item)
    verifier, challenge = _pkce_pair()
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    from .auth import safe_next

    flows = dict(session.get("oidc_flows") or {})
    flows = dict(sorted(flows.items(), key=lambda pair: pair[1].get("started", 0))[-(MAX_FLOWS - 1):])
    flows[state] = {"slug": item.slug, "nonce": nonce, "verifier": verifier, "intent": intent, "user_id": user_id,
                    "next": safe_next("/account" if intent == "link" else "/"), "started": now_seconds()}
    session["oidc_flows"] = flows
    query = {"response_type": "code", "client_id": item.client_id, "redirect_uri": _redirect_uri(item.slug),
             "scope": item.scopes, "state": state, "nonce": nonce, "code_challenge": challenge,
             "code_challenge_method": "S256"}
    return document["authorization_endpoint"] + "?" + urlencode(query)


def _refuse(message: str, reason: str, slug: str, status: int = 401):
    security.record("oidc_sign_in", target_type="identity_provider", target_id=slug, outcome="refused",
                    metadata={"reason": reason}, actor=None)
    if request.accept_mimetypes.best == "application/json":
        return jsonify({"error": message, "code": reason}), status
    return render_template("auth_message.html", title=say("identity", "School sign-in did not work"), message=message), status


@bp.get("/auth/oidc/<slug>/login")
def login(slug: str):
    item = provider(slug)
    if item is None:
        return _refuse("This school sign-in is not set up.", "unknown_provider", slug, 404)
    try:
        return redirect(_start(item, "login"))
    except (OidcError, ValueError, requests.RequestException):
        return _refuse("The school's sign-in service could not be reached. Try again later.", "unreachable", slug, 502)


@bp.post("/auth/identities/<slug>/link")
def link(slug: str):
    """Start linking a school account to the signed-in account (Account page).

    Answers {"redirect": url}: the page then goes to the school's sign-in.
    """
    from .auth import current_principal

    principal = current_principal()
    if principal.token_scopes is not None:
        return jsonify({**message_body(say("identity", "linking a school account needs a browser sign-in"))}), 403
    item = provider(slug)
    if item is None:
        return _refuse("This school sign-in is not set up.", "unknown_provider", slug, 404)
    if not principal.authenticated:
        return jsonify({**message_body(say("identity", "Please sign in first"))}), 401
    try:
        return jsonify({"redirect": _start(item, "link", principal.id)})
    except (OidcError, ValueError, requests.RequestException):
        return _refuse("The school's sign-in service could not be reached. Try again later.", "unreachable", slug, 502)


def _token_request(item: Provider, document: dict[str, Any], code: str, verifier: str) -> dict[str, Any]:
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": _redirect_uri(item.slug),
            "client_id": item.client_id, "code_verifier": verifier}
    secret = item.secret()
    auth = None
    if secret:
        methods = document.get("token_endpoint_auth_methods_supported") or ["client_secret_basic"]
        if "client_secret_basic" in methods:
            auth = (item.client_id, secret)
        else:
            data["client_secret"] = secret
    status, answer = http("POST", document["token_endpoint"], data=data, auth=auth)
    if status != 200 or not isinstance(answer, dict) or not answer.get("id_token"):
        raise OidcError(say("identity", "the school's sign-in service did not accept the sign-in"))
    return answer


@bp.get("/auth/oidc/<slug>/callback")
def callback(slug: str):
    from .auth import principal_from_user, sign_in

    state = request.args.get("state", "")
    flows = dict(session.get("oidc_flows") or {})
    flow = flows.pop(state, None) if state else None
    session["oidc_flows"] = flows   # a state works once
    if flow is None or flow.get("slug") != slug:
        return _refuse("This sign-in link is not valid any more. Start again.", "bad_state", slug, 400)
    if now_seconds() - float(flow.get("started", 0)) > FLOW_SECONDS:
        return _refuse("The sign-in took too long. Start again.", "expired_flow", slug, 400)
    if request.args.get("error"):
        return _refuse("The school sign-in was cancelled or refused.", "provider_error", slug, 401)
    item = provider(slug)
    if item is None:
        return _refuse("This school sign-in is not set up.", "unknown_provider", slug, 404)
    try:
        document = discovery(item)
        tokens = _token_request(item, document, request.args.get("code", ""), flow["verifier"])
        claims = verify_id_token(tokens["id_token"], item, document["jwks_uri"], flow["nonce"])
    except OidcError as error:
        return _refuse(str(error)[:1].upper() + str(error)[1:] + ".", "invalid_token", slug)
    except (ValueError, requests.RequestException):
        return _refuse("The school's sign-in service could not be reached. Try again later.", "unreachable", slug, 502)
    issuer, subject = claims["iss"], claims["sub"]
    if flow.get("intent") == "link":
        return _finish_link(item, flow, issuer, subject, claims)
    try:
        user, created = complete_external_sign_in(
            provider_slug=slug, issuer=issuer, subject=subject, email=str(claims.get("email") or ""),
            username=str(claims.get("preferred_username") or ""), kit_role=academic_role(claims, item),
            allowed_domains=item.allowed_domains)
    except SignInRefused as refusal:
        return _refuse(str(refusal), refusal.reason, slug, 403)
    principal = principal_from_user(user)
    from . import privacy

    privacy.record_notice(principal.id, "school_sign_in", slug)   # ADR-0022
    sign_in(principal)
    session["auth_via"] = slug   # signing out ends the kit session only (see auth.logout)
    security.record("oidc_sign_in", target_type="identity_provider", target_id=slug, actor=principal,
                    metadata={"account_created": created, "kit_role": user.kit_role})
    return redirect(flow.get("next") or "/")


def _finish_link(item: Provider, flow: dict[str, Any], issuer: str, subject: str, claims: dict[str, Any]):
    from .auth import current_principal

    principal = current_principal()
    if not principal.authenticated or principal.id != flow.get("user_id"):
        return _refuse("Sign in to your kit account before linking a school account.", "link_not_signed_in",
                       item.slug, 403)
    existing = db.session.scalar(select(ExternalIdentity).where(ExternalIdentity.issuer == issuer,
                                                                ExternalIdentity.subject == subject))
    if existing is not None and existing.user_id != principal.id:
        return _refuse("This school account is already linked to another kit account.", "identity_in_use",
                       item.slug, 409)
    if existing is None:
        db.session.add(ExternalIdentity(user_id=principal.id, provider=item.slug, issuer=issuer, subject=subject,
                                        email=str(claims.get("email") or "")))
        db.session.commit()
    security.record("identity_link", target_type="user", target_id=principal.id,
                    metadata={"provider": item.slug, "issuer": issuer})
    return redirect(flow.get("next") or "/account")


@bp.get("/auth/identities")
def list_identities():
    from .auth import current_principal

    principal = current_principal()
    if not principal.authenticated:
        return jsonify({**message_body(say("identity", "Please sign in first"))}), 401
    return jsonify({"identities": identities_of(principal.id),
                    "providers": [{"slug": item.slug, "name": item.name} for item in providers()]})


@bp.delete("/auth/identities/<int:identity_id>")
def unlink(identity_id: int):
    from .auth import User, current_principal

    principal = current_principal()
    if not principal.authenticated:
        return jsonify({**message_body(say("identity", "Please sign in first"))}), 401
    row = db.session.scalar(select(ExternalIdentity).where(ExternalIdentity.id == identity_id,
                                                           ExternalIdentity.user_id == principal.id))
    if row is None:
        return jsonify({**message_body(say("identity", "not found"))}), 404
    user = db.session.get(User, principal.id)
    others = db.session.scalar(select(db.func.count()).select_from(ExternalIdentity)
                               .where(ExternalIdentity.user_id == principal.id, ExternalIdentity.id != identity_id))
    if not user.password_hash and not others:
        return jsonify({**message_body(say("identity", "This is your only way to sign in: set a password first."))}), 400
    db.session.delete(row)
    db.session.commit()
    security.record("identity_unlink", target_type="user", target_id=principal.id,
                    metadata={"provider": row.provider, "issuer": row.issuer})
    return jsonify({"ok": True})


# --- administrators: the providers ---------------------------------------------------

def _validated(data: dict[str, Any], existing: IdentityProvider | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if existing is None:
        slug = str(data.get("slug") or "").strip().lower()
        if not SLUG_RE.fullmatch(slug):
            raise ValueError(say("identity", "slug must be 2-32 lowercase letters, digits or dashes, starting with a letter"))
        if slug == "oidc" and _environment_provider() is not None:
            raise ValueError(say("identity", "the slug oidc is used by the PRG32_OIDC_* provider"))
        out["slug"] = slug
    for key in ("name", "issuer", "client_id"):
        if key in data or existing is None:
            value = str(data.get(key) or "").strip()
            if not value:
                raise ValueError(say("identity", "{key} is required", key=key))
            out[key] = value
    if "issuer" in out:
        check_endpoint(out["issuer"])
    if "client_secret_ref" in data:
        reference = str(data.get("client_secret_ref") or "").strip()
        resolve_secret(reference)  # checks the form; never stores a secret itself
        out["client_secret_ref"] = reference
    if "scopes" in data:
        scopes = str(data.get("scopes") or "").split()
        if "openid" not in scopes:
            raise ValueError(say("identity", "scopes must include openid"))
        out["scopes"] = " ".join(scopes)
    if "role_claim" in data:
        out["role_claim"] = str(data.get("role_claim") or "").strip()
    if "role_map" in data:
        role_map = data.get("role_map") or {}
        if not isinstance(role_map, dict) or any(value not in ACADEMIC_ROLES for value in role_map.values()):
            raise ValueError("role_map values must be academic roles: " + ", ".join(ACADEMIC_ROLES)
                             + " (a provider can never grant admin or publisher)")
        out["role_map"] = json.dumps({str(key): value for key, value in role_map.items()}, sort_keys=True)
    if "new_account_role" in data:
        if data["new_account_role"] not in ACADEMIC_ROLES:
            raise ValueError("new_account_role must be one of: " + ", ".join(ACADEMIC_ROLES))
        out["new_account_role"] = data["new_account_role"]
    if "allowed_domains" in data:
        domains = data.get("allowed_domains") or []
        domains = domains.split() if isinstance(domains, str) else domains
        out["allowed_domains"] = " ".join(str(domain).strip().lower().lstrip("@") for domain in domains if domain)
    if "enabled" in data:
        out["enabled"] = 1 if data["enabled"] else 0
    return out


@bp.route("/api/admin/identity_providers", methods=["GET", "POST"])
def admin_providers():
    from .auth import current_principal

    if not current_principal().is_admin:
        return jsonify({**message_body(say("identity", "Only teachers with the admin role can do this"))}), 403
    if request.method == "GET":
        rows = {row.slug: row.enabled for row in db.session.scalars(select(IdentityProvider))}
        return jsonify({"providers": [{**item.public(), "enabled": bool(rows.get(item.slug, 1))}
                                      for item in providers(enabled_only=False)]})
    values = _validated(request.get_json(silent=True) or {}, None)
    if db.session.scalar(select(IdentityProvider.id).where(IdentityProvider.slug == values["slug"])):
        raise ValueError(say("identity", "a provider with this slug already exists"))
    row = IdentityProvider(**values)
    db.session.add(row)
    db.session.commit()
    forget_caches()
    security.record("identity_provider_create", target_type="identity_provider", target_id=row.slug,
                    metadata={"issuer": row.issuer})
    return jsonify(_from_row(row).public()), 201


@bp.route("/api/admin/identity_providers/<slug>", methods=["PUT", "DELETE"])
def admin_provider(slug: str):
    from .auth import current_principal

    if not current_principal().is_admin:
        return jsonify({**message_body(say("identity", "Only teachers with the admin role can do this"))}), 403
    row = db.session.scalar(select(IdentityProvider).where(IdentityProvider.slug == slug))
    if row is None:
        return jsonify({**message_body(say("identity", "provider not found (providers from PRG32_OIDC_* are changed there)"))}), 404
    if request.method == "DELETE":
        db.session.delete(row)
        db.session.commit()
        forget_caches()
        security.record("identity_provider_delete", target_type="identity_provider", target_id=slug)
        return jsonify({"deleted": True})
    for key, value in _validated(request.get_json(silent=True) or {}, row).items():
        setattr(row, key, value)
    row.updated_at = utcnow()
    db.session.commit()
    forget_caches()
    security.record("identity_provider_update", target_type="identity_provider", target_id=slug,
                    metadata={"issuer": row.issuer, "enabled": bool(row.enabled)})
    return jsonify({**_from_row(row).public(), "enabled": bool(row.enabled)})


@bp.get("/admin/identity")
def admin_identity_page():
    from .auth import auth_failure, current_principal

    if not current_principal().is_admin:
        return auth_failure("Only teachers with the admin role can do this", 403)
    return render_template("admin_identity.html", redirect_example=url_for("identity.callback", slug="SLUG",
                                                                            _external=True))


@bp.errorhandler(ValueError)
def bad_value(error: ValueError):
    return jsonify({"error": str(error), **message_fields(error)}), 400


def init_app(app) -> None:
    app.register_blueprint(bp)
