"""An OpenID Connect provider in the test process, for the identity tests (ADR-0016).

It signs real ID tokens (RS256, or ES256) with keys it can rotate, checks the PKCE
verifier against the challenge, the client secret and the redirect address at its
token endpoint, and lets a test tamper with any claim. identity.http is replaced by
FakeIdP.http, so nothing leaves the process.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa, utils


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _int(value: int, size: int | None = None) -> str:
    return b64(value.to_bytes(size or (value.bit_length() + 7) // 8, "big"))


class FakeIdP:
    def __init__(self, issuer: str = "https://idp.school.test", client_id: str = "kit", secret: str = "s3cret",
                 algorithm: str = "RS256"):
        self.issuer, self.client_id, self.secret, self.algorithm = issuer, client_id, secret, algorithm
        self.keys: list[tuple[str, object]] = []
        self.rotate()
        self.codes: dict[str, dict] = {}
        self.claims_patch: dict = {}
        self.header_patch: dict = {}
        self.sign_with = None            # a key id to sign with that the JWKS does not publish
        self.requests: list[tuple[str, str]] = []
        self.token_auth_methods = ["client_secret_basic"]

    # --- keys ------------------------------------------------------------------
    def rotate(self) -> str:
        kid = "key-" + secrets.token_hex(4)
        key = (ec.generate_private_key(ec.SECP256R1()) if self.algorithm == "ES256"
               else rsa.generate_private_key(public_exponent=65537, key_size=2048))
        self.keys.insert(0, (kid, key))
        return kid

    def jwks(self) -> dict:
        out = []
        for kid, key in self.keys:
            numbers = key.public_key().public_numbers()
            if self.algorithm == "ES256":
                out.append({"kty": "EC", "crv": "P-256", "kid": kid, "use": "sig",
                            "x": _int(numbers.x, 32), "y": _int(numbers.y, 32)})
            else:
                out.append({"kty": "RSA", "kid": kid, "use": "sig", "alg": "RS256",
                            "n": _int(numbers.n), "e": _int(numbers.e)})
        return {"keys": out}

    def sign(self, claims: dict, header: dict | None = None, key=None, kid=None) -> str:
        kid = kid or self.keys[0][0]
        key = key or self.keys[0][1]
        header = {"alg": self.algorithm, "typ": "JWT", "kid": kid, **(header or {})}
        signing_input = (b64(json.dumps(header).encode()) + "." + b64(json.dumps(claims).encode())).encode()
        if header["alg"] == "none":
            return signing_input.decode() + "."
        if header["alg"] == "HS256":
            import hmac

            signature = hmac.new(b"anything", signing_input, hashlib.sha256).digest()
        elif self.algorithm == "ES256":
            r, s = utils.decode_dss_signature(key.sign(signing_input, ec.ECDSA(hashes.SHA256())))
            signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        else:
            signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        return signing_input.decode() + "." + b64(signature)

    def private_pem(self) -> bytes:
        return self.keys[0][1].private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                              serialization.NoEncryption())

    # --- the browser at the school's sign-in page --------------------------------
    def authorize(self, authorize_url: str, subject: str, email: str = "", **claims) -> dict:
        """What the provider does when the person signs in: a code bound to this request."""
        query = {key: values[0] for key, values in parse_qs(urlsplit(authorize_url).query).items()}
        assert query["response_type"] == "code" and query["code_challenge_method"] == "S256"
        code = secrets.token_urlsafe(16)
        self.codes[code] = {"challenge": query["code_challenge"], "redirect_uri": query["redirect_uri"],
                            "client_id": query["client_id"], "nonce": query["nonce"], "subject": subject,
                            "email": email, "claims": claims}
        return {"code": code, "state": query["state"], "redirect_uri": query["redirect_uri"]}

    # --- HTTP (what identity.http does) --------------------------------------------
    def http(self, method: str, url: str, data=None, auth=None):
        self.requests.append((method, url))
        if url == self.issuer + "/.well-known/openid-configuration":
            return 200, {"issuer": self.issuer, "authorization_endpoint": self.issuer + "/authorize",
                         "token_endpoint": self.issuer + "/token", "jwks_uri": self.issuer + "/jwks",
                         "token_endpoint_auth_methods_supported": self.token_auth_methods}
        if url == self.issuer + "/jwks":
            return 200, self.jwks()
        if url == self.issuer + "/token" and method == "POST":
            return self.token(data or {}, auth)
        return 404, {"error": "not found"}

    def token(self, data: dict, auth) -> tuple[int, dict]:
        grant = self.codes.pop(data.get("code", ""), None)   # a code works once
        if grant is None:
            return 400, {"error": "invalid_grant"}
        client_id, secret = auth if auth else (data.get("client_id"), data.get("client_secret"))
        if client_id != self.client_id or secret != self.secret:
            return 401, {"error": "invalid_client"}
        if data.get("redirect_uri") != grant["redirect_uri"]:
            return 400, {"error": "invalid_grant", "error_description": "redirect_uri"}
        verifier = data.get("code_verifier", "")
        if b64(hashlib.sha256(verifier.encode()).digest()) != grant["challenge"]:
            return 400, {"error": "invalid_grant", "error_description": "PKCE"}
        now = int(time.time())
        claims = {"iss": self.issuer, "aud": self.client_id, "sub": grant["subject"], "iat": now, "exp": now + 300,
                  "nonce": grant["nonce"], **({"email": grant["email"]} if grant["email"] else {}),
                  **grant["claims"], **self.claims_patch}
        claims = {key: value for key, value in claims.items() if value is not None}
        if self.sign_with:
            unpublished = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            id_token = self.sign(claims, self.header_patch, key=unpublished, kid=self.sign_with)
        else:
            id_token = self.sign(claims, self.header_patch)
        return 200, {"access_token": "at-" + secrets.token_hex(4), "token_type": "Bearer", "id_token": id_token}
