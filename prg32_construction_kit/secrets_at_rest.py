"""Secrets the kit must send on later, kept encrypted in the database (S-1, ADR-0022).

The Cartridge Store bearer token of a publish profile has to be sent to the Store, so it
cannot be a hash like a password. It is encrypted with Fernet under a key derived from the
installation's secret key (the same approach as cloud tokens, a different key). A stored
value starts with ``enc1:``; older databases' plain values are encrypted at start-up
(``seal_plain_store_tokens``). If the secret key changes, a stored token cannot be read any
more and the student enters it again.
"""

from __future__ import annotations

import base64

from flask import current_app

PREFIX = "enc1:"


def _fernet():
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    secret = str(current_app.config["SECRET_KEY"]).encode()
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"prg32-construction-kit", info=b"store-tokens").derive(secret)
    return Fernet(base64.urlsafe_b64encode(key))


def is_sealed(value: str) -> bool:
    return str(value or "").startswith(PREFIX)


def seal(value: str) -> str:
    """Encrypt a secret for the database ("" stays "", an already sealed value stays as it is)."""
    value = str(value or "")
    if not value or is_sealed(value):
        return value
    return PREFIX + _fernet().encrypt(value.encode()).decode()


def unseal(value: str) -> str | None:
    """The secret in clear; None when it cannot be read (the secret key changed)."""
    from cryptography.fernet import InvalidToken

    value = str(value or "")
    if not is_sealed(value):
        return value          # nothing stored ("" ), or a value from before encryption
    try:
        return _fernet().decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken:
        return None


def seal_plain_store_tokens() -> int:
    """Encrypt the Store tokens an older database kept in clear. Idempotent; returns how many."""
    from sqlalchemy import select

    from .db import PublishProfile, db

    changed = 0
    for profile in db.session.scalars(select(PublishProfile).where(PublishProfile.bearer_token != "")).all():
        if not is_sealed(profile.bearer_token):
            profile.bearer_token = seal(profile.bearer_token)
            changed += 1
    if changed:
        db.session.commit()
    return changed
