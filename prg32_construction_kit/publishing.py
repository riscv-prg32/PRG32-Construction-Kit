"""Publishing as a two-step, reviewed action (docs/adr/0009-publish-authorization-and-confirmation.md).

1. **Review.** The server opens the bundle and writes a summary of exactly what
   would be sent: the Store, the cartridge id/title/version, every cartridge
   file with its size and SHA-256, and what the Store does next. It signs a
   *review token* that names that summary (by its SHA-256), the user, the
   profile and the bundle, valid for a few minutes.
2. **Confirm.** The student sends the token back with ``"confirm": true``.
   The server builds the summary again; if anything changed (another bundle,
   another Store address, a file edited) the token no longer matches and
   nothing is sent.

Each confirmed review is one *publish attempt* with a state:
``uploading`` -> ``submitted`` (the Store accepted it for review) or
``failed`` (try again). Confirming a review that was already submitted gives
back the earlier answer instead of uploading twice.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import UTC
from pathlib import Path
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from .db import db, new_id, utcnow
from .store_policy import StoreTarget

SUMMARY_SCHEMA = "prg32-kit-publish-review-1"
REVIEW_SECONDS = 15 * 60
# An upload still "uploading" after this long is treated as interrupted and may be retried.
STALE_UPLOAD_SECONDS = 5 * 60
METADATA_ABI = "prg32-metadata-1.0"
CARTRIDGE_MAGIC = b"PRG2"
MAX_BUNDLE_BYTES = 64 * 1024 * 1024
MAX_ENTRY_BYTES = 32 * 1024 * 1024
AFTER_UPLOAD = ("The Store receives it as a submission waiting for review. It becomes public only after "
                "an editor of the Store verifies it.")

MESSAGES = {
    "not_publisher": "Publishing needs the publisher role. Ask your teacher.",
    "not_a_bundle": "Only a Store bundle made with Compile Cartridge can be published.",
    "not_publishable": "This bundle has no compiled cartridge (it is source-only), so it cannot be published.",
    "bad_bundle": "The bundle is not a valid zip file.",
    "bad_manifest": "The bundle's manifest.json is missing or not a PRG32 cartridge manifest.",
    "missing_cartridge": "The bundle's manifest names a cartridge file that is not in the bundle.",
    "not_a_cartridge": "A file in the bundle is not a PRG32 cartridge.",
    "hash_mismatch": "A cartridge in the bundle is not the one the build made. Compile the cartridge again.",
    "too_large": "The bundle is too large to publish.",
    "version_already_published": "This version of the game was already sent to this Store with different files. "
                                 "Save the project (that gives it a new version), compile again, then publish.",
    "token_too_old": "The Store token of this publish profile is too old to use. Ask your teacher to make a new "
                     "token in the Store and put it in the publish profile.",
}


class PublishRefused(ValueError):
    def __init__(self, reason: str):
        super().__init__(MESSAGES[reason])
        self.reason = reason


class PublishAttempt(db.Model):
    """One confirmed review being sent (or sent) to a Store."""
    __tablename__ = "publish_attempts"
    id: Mapped[str] = mapped_column(db.Text, primary_key=True)
    digest: Mapped[str] = mapped_column(db.Text, nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(db.Text, nullable=False)
    artifact_id: Mapped[str] = mapped_column(db.Text, nullable=False)
    state: Mapped[str] = mapped_column(db.Text, nullable=False)
    result: Mapped[str] = mapped_column(db.Text, nullable=False, default="{}")
    # What was sent where, so one id/version never goes to a Store twice (contract versioning.kit_rule).
    store_host: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    cartridge_id: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    cartridge_version: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    bundle_sha256: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(db.Text, nullable=False)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect_bundle(path: Path, provenance: dict[str, Any] | None) -> dict[str, Any]:
    """Open a Store bundle and check it holds real cartridges; return the parts of the summary."""
    if path.stat().st_size > MAX_BUNDLE_BYTES:
        raise PublishRefused("too_large")
    data = path.read_bytes()
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise PublishRefused("bad_bundle") from None
    with archive:
        names = {info.filename: info for info in archive.infolist() if not info.is_dir()}
        if "manifest.json" not in names:
            raise PublishRefused("bad_manifest")
        try:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise PublishRefused("bad_manifest") from None
        architectures = manifest.get("architectures") if isinstance(manifest, dict) else None
        if (not isinstance(manifest, dict) or manifest.get("abi") != METADATA_ABI or not manifest.get("id")
                or not manifest.get("version") or not isinstance(architectures, list) or not architectures):
            raise PublishRefused("bad_manifest")
        cartridges = []
        for entry in architectures:
            if not isinstance(entry, dict) or not entry.get("id") or not entry.get("file"):
                raise PublishRefused("bad_manifest")
            info = names.get(str(entry["file"]))
            if info is None:
                raise PublishRefused("missing_cartridge")
            if info.file_size > MAX_ENTRY_BYTES:
                raise PublishRefused("too_large")
            content = archive.read(info)
            if not content.startswith(CARTRIDGE_MAGIC):
                raise PublishRefused("not_a_cartridge")
            cartridges.append({"id": str(entry["id"]), "file": str(entry["file"]), "bytes": len(content),
                               "sha256": _sha256(content)})
    # A bundle made by a kit build must contain exactly the cartridges that build made.
    if provenance:
        built = {item.get("architecture"): item.get("sha256") for item in provenance.get("cartridges", [])}
        for cartridge in cartridges:
            if cartridge["id"] in built and built[cartridge["id"]] != cartridge["sha256"]:
                raise PublishRefused("hash_mismatch")
    cartridges.sort(key=lambda item: item["id"])
    return {
        "cartridge": {"id": str(manifest["id"]), "title": str(manifest.get("title") or ""),
                      "version": str(manifest["version"])},
        "architectures": cartridges,
        "bundle_sha256": _sha256(data),
        "bundle_bytes": len(data),
    }


def build_summary(*, target: StoreTarget, authentication: str, profile: dict[str, Any], artifact: dict[str, Any],
                  inspected: dict[str, Any], build_id: str | None) -> dict[str, Any]:
    return {
        "schema": SUMMARY_SCHEMA,
        "store": {"origin": target.origin, "host": target.host, "authentication": authentication},
        "profile": {"id": profile["id"], "name": profile.get("name") or ""},
        "bundle": {"artifact_id": artifact["id"], "name": artifact.get("name") or "",
                   "sha256": inspected["bundle_sha256"], "bytes": inspected["bundle_bytes"], "build_id": build_id},
        "cartridge": inspected["cartridge"],
        "architectures": inspected["architectures"],
        "after_upload": AFTER_UPLOAD,
    }


def summary_digest(summary: dict[str, Any]) -> str:
    return _sha256(json.dumps(summary, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt="prg32-kit-publish-review")


def make_review_token(secret: str, summary: dict[str, Any], user_id: int) -> str:
    return _serializer(secret).dumps({"digest": summary_digest(summary), "user": user_id,
                                      "profile": summary["profile"]["id"],
                                      "artifact": summary["bundle"]["artifact_id"]})


def check_review_token(secret: str, token: str, summary: dict[str, Any], user_id: int) -> str | None:
    """None when the token matches this exact summary and user; otherwise a student-safe reason."""
    try:
        claims = _serializer(secret).loads(str(token or ""), max_age=REVIEW_SECONDS)
    except SignatureExpired:
        return "The review is too old. Review again before publishing."
    except BadSignature:
        return "The review is not valid. Review again before publishing."
    if not isinstance(claims, dict) or claims.get("user") != user_id:
        return "The review belongs to another user. Review again before publishing."
    if (claims.get("profile") != summary["profile"]["id"] or claims.get("artifact") != summary["bundle"]["artifact_id"]
            or claims.get("digest") != summary_digest(summary)):
        return "The bundle or the Store changed after the review. Review again before publishing."
    return None


# --- attempts ---------------------------------------------------------------------------

def _seconds_since(timestamp: str) -> float:
    from datetime import datetime

    try:
        then = datetime.fromisoformat(timestamp)
    except ValueError:
        return float("inf")
    return (datetime.now(UTC) - then).total_seconds()


def submitted_version(summary: dict[str, Any]) -> PublishAttempt | None:
    """An earlier accepted upload of this cartridge id and version to this Store, if any.

    The Cartridge Store accepts the same id/version twice and an approval then replaces
    the published files (contract versioning.known_store_gap), so the kit never sends a
    second bundle for one id/version: the same files answer with the first result, other
    files are refused (the student saves and compiles: a new version).
    """
    cartridge = summary.get("cartridge") or {}
    return db.session.scalar(select(PublishAttempt).where(
        PublishAttempt.state == "submitted", PublishAttempt.store_host == summary["store"]["host"],
        PublishAttempt.cartridge_id == str(cartridge.get("id") or ""),
        PublishAttempt.cartridge_version == str(cartridge.get("version") or "")).order_by(PublishAttempt.created_at))


def start_attempt(digest: str, user_id: int, profile_id: str, artifact_id: str,
                  summary: dict[str, Any] | None = None) -> tuple[str, dict[str, Any] | None]:
    """Claim this review for upload.

    Returns ("go", None) when the caller should upload now, ("submitted", result)
    when it was already accepted (do not upload again) or ("busy", None) when
    another request is uploading it right now.
    """
    now = utcnow()
    attempt = db.session.scalar(select(PublishAttempt).where(PublishAttempt.digest == digest))
    if attempt is None:
        sent = summary or {}
        db.session.add(PublishAttempt(id=new_id("publish"), digest=digest, user_id=user_id, profile_id=profile_id,
                                      artifact_id=artifact_id, state="uploading", created_at=now, updated_at=now,
                                      store_host=(sent.get("store") or {}).get("host", ""),
                                      cartridge_id=str((sent.get("cartridge") or {}).get("id") or ""),
                                      cartridge_version=str((sent.get("cartridge") or {}).get("version") or ""),
                                      bundle_sha256=(sent.get("bundle") or {}).get("sha256", "")))
        try:
            db.session.commit()
        except IntegrityError:  # another request claimed it a moment ago
            db.session.rollback()
            return "busy", None
        return "go", None
    if attempt.state == "submitted":
        return "submitted", json.loads(attempt.result or "{}")
    if attempt.state == "uploading" and _seconds_since(attempt.updated_at) < STALE_UPLOAD_SECONDS:
        return "busy", None
    # failed, or an interrupted upload: claim it again, but only if nobody else just did.
    claimed = db.session.execute(
        db.update(PublishAttempt).where(PublishAttempt.id == attempt.id, PublishAttempt.updated_at == attempt.updated_at)
        .values(state="uploading", updated_at=now))
    db.session.commit()
    return ("go", None) if claimed.rowcount == 1 else ("busy", None)


def finish_attempt(digest: str, state: str, result: dict[str, Any]) -> None:
    attempt = db.session.scalar(select(PublishAttempt).where(PublishAttempt.digest == digest))
    if attempt is None:
        return
    attempt.state = state
    attempt.result = json.dumps(result, sort_keys=True)
    attempt.updated_at = utcnow()
    db.session.commit()
