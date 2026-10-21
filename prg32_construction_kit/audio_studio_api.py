"""AudioStudio's page and API (docs/audio_studio.md, ADR-0021).

A project's sound lives in one asset of kind "audio_studio" (its document, see
audio_studio.py); recorded samples are artifacts of kind "audio_sample" (8-bit 22050 Hz
sound files), so large sound never sits in a database row. Everything follows the
project's rules: only its owner (or an administrator) changes it, a teacher supervising
the class reads it, saves name the version they started from, quotas apply.

    GET  /audio-studio/<project_id>                 the AudioStudio page
    GET  /api/projects/<id>/audio                   {document, version, asset_id, missing_samples}
    PUT  /api/projects/<id>/audio                   {document, expected_version} -> saved, or 409
    POST /api/projects/<id>/audio/preview           {document?, muted?: [voices]} -> the AUD0 block
    POST /api/projects/<id>/audio/samples           a WAV file (form field "file", "name") -> the sample
    GET  /api/projects/<id>/audio/export            the document with its sounds, to take elsewhere
    POST /api/projects/<id>/audio/import            {export, expected_version} -> saved
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, render_template, request
from sqlalchemy import select

from . import audio_studio, security
from .storage_policy import QuotaExceeded
from .audio_studio import AudioStudioError
from .db import Asset, VersionConflict, create_resource, db, get_resource, update_resource

KIND = "audio_studio"
SAMPLE_KIND = "audio_sample"
CONTENT_TYPE = "application/vnd.prg32.audio-studio+json"
SAMPLE_CONTENT_TYPE = "application/vnd.prg32.audio-u8"

bp = Blueprint("audio_studio", __name__)


class AudioRefused(Exception):
    def __init__(self, message: str, status: int = 400, **details: Any):
        super().__init__(message)
        self.status, self.details = status, details


@bp.errorhandler(AudioRefused)
def refused(error: AudioRefused):
    return jsonify({"error": str(error), **error.details}), error.status


@bp.errorhandler(AudioStudioError)
def invalid(error: AudioStudioError):
    return jsonify({"error": str(error), "code": "audio_invalid"}), 400


@bp.errorhandler(QuotaExceeded)
def _quota_exceeded(error: QuotaExceeded):
    from .routes import quota_exceeded

    return quota_exceeded(error)    # the same 413 answer as every other save (ADR-0017)


def _project(project_id: str, write: bool) -> dict[str, Any]:
    from .routes import can_write, readable

    project = readable("projects", project_id)
    if project is None:
        raise AudioRefused("Project not found", 404)
    if write and not can_write(project):
        raise AudioRefused("Only the owner of a project can change its sound", 403)
    return project


def audio_asset(project_id: str) -> Asset | None:
    return db.session.scalar(select(Asset).where(Asset.project_id == project_id, Asset.kind == KIND)
                             .order_by(Asset.created_at))


def document_of(project_id: str) -> tuple[dict[str, Any] | None, Asset | None]:
    row = audio_asset(project_id)
    if row is None:
        return None, None
    try:
        return audio_studio.validate_document(json.loads(row.data or "{}")), row
    except (ValueError, AudioStudioError):
        return None, row


def sample_sounds(project: dict[str, Any], document: dict[str, Any]) -> tuple[dict[str, bytes], list[str]]:
    """artifact id -> sound for the document's samples that this project's owner has; and the missing names."""
    sounds, missing = {}, []
    for sample in document.get("samples", []):
        artifact = get_resource("artifacts", sample["artifact_id"])
        path = Path(artifact["path"]) if artifact and artifact.get("path") else None
        if (artifact is None or artifact.get("kind") != SAMPLE_KIND or artifact.get("owner_id") != project.get("owner_id")
                or path is None or not path.is_file()):
            missing.append(sample["name"])
            continue
        sounds[sample["artifact_id"]] = path.read_bytes()[: audio_studio.audio_block.MAX_SAMPLE_BYTES]
    return sounds, missing


def archive_samples(project: dict[str, Any]) -> list[dict[str, Any]]:
    """The samples to put in the project archive (and in a copy): ``{"artifact_id", "name", "pcm"}``."""
    document, _row = document_of(project["id"])
    if document is None:
        return []
    sounds, _missing = sample_sounds(project, document)
    return [{"artifact_id": sample["artifact_id"], "name": sample["name"], "pcm": sounds[sample["artifact_id"]]}
            for sample in document["samples"] if sample["artifact_id"] in sounds]


def store_sample(project: dict[str, Any], name: str, sound: bytes) -> dict[str, Any]:
    """Keep an 8-bit sound as the project owner's audio_sample artifact (a file named by its hash)."""
    digest = hashlib.sha256(sound).hexdigest()
    folder = Path(current_app.config["ARTIFACT_ROOT"]) / "audio" / str(project.get("owner_id") or "shared")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{digest}.u8"
    path.write_bytes(sound)
    return create_resource("artifacts", {"owner_id": project.get("owner_id"), "project_id": project["id"],
                                         "kind": SAMPLE_KIND, "name": name[:32], "content_type": SAMPLE_CONTENT_TYPE,
                                         "path": str(path),
                                         "metadata": {"frames": len(sound), "sample_rate": 22050, "sha256": digest}})


def renamed_samples(document: Any, new_ids: dict[str, str]) -> Any:
    """A copy of an AudioStudio document whose samples name their new artifacts."""
    if not isinstance(document, dict) or not isinstance(document.get("samples"), list):
        return document
    copy = json.loads(json.dumps(document))
    for sample in copy["samples"]:
        if isinstance(sample, dict) and sample.get("artifact_id") in new_ids:
            sample["artifact_id"] = new_ids[sample["artifact_id"]]
    return copy


def project_audio(project: dict[str, Any]) -> tuple[bytes, dict[str, Any]] | None:
    """The project's AUD0 block and document for packaging, None without one; AudioRefused if broken."""
    document, row = document_of(project["id"])
    if row is None:
        return None
    if document is None:
        raise AudioRefused("The project's AudioStudio sound is damaged: open AudioStudio and save it again.")
    sounds, missing = sample_sounds(project, document)
    if missing:
        raise AudioRefused("These AudioStudio samples have no sound: " + ", ".join(missing), 400,
                           code="audio_missing_samples", missing=missing)
    return audio_studio.pack_document(document, sounds), document


def _answer(project: dict[str, Any], document: dict[str, Any], row: Asset | None) -> dict[str, Any]:
    _, missing = sample_sounds(project, document)
    return {"document": document, "version": row.version if row else 0, "asset_id": row.id if row else None,
            "missing_samples": missing,
            "ids": {"effects": {effect["name"]: {"instrument": audio_studio.FIRST_EFFECT_INSTRUMENT + index,
                                                 "voice": effect["voice"], "note": effect["note"]}
                                for index, effect in enumerate(document["effects"])},
                    "soundtracks": {track["name"]: index for index, track in enumerate(document["soundtracks"])}}}


@bp.get("/audio-studio/<project_id>")
def page(project_id: str):
    project = _project(project_id, write=False)
    from .routes import can_write

    return render_template("audio_studio.html", project=project, can_edit=can_write(project))


@bp.get("/api/projects/<project_id>/audio")
def get_audio(project_id: str):
    project = _project(project_id, write=False)
    document, row = document_of(project_id)
    if row is not None and document is None:
        raise AudioRefused("The project's AudioStudio sound is damaged", 422, code="audio_damaged")
    return jsonify(_answer(project, document or audio_studio.default_document(), row))


def _save(project: dict[str, Any], document: dict[str, Any], expected: Any) -> tuple[dict[str, Any], Asset]:
    from .routes import quota

    document = audio_studio.validate_document(document)
    text = json.dumps(document, sort_keys=True)
    if len(text) > audio_studio.MAX_DOCUMENT_BYTES:
        raise AudioRefused("The AudioStudio document is too big", 413)
    row = audio_asset(project["id"])
    if expected is not None and (not isinstance(expected, int) or isinstance(expected, bool)):
        raise AudioRefused("expected_version must be a whole number")
    if row is None:
        if expected not in (None, 0):
            raise AudioRefused("This project's sound changed in another window.", 409, code="audio_version_conflict")
        quota(adding_bytes=len(text))
        created = create_resource("assets", {"owner_id": project.get("owner_id"), "project_id": project["id"],
                                             "name": "AudioStudio", "kind": KIND, "content_type": CONTENT_TYPE,
                                             "data": document})
        row = db.session.get(Asset, created["id"])
        row.version = 1        # version 0 means "no sound saved yet": a second window starting from it conflicts
        db.session.commit()
        return document, row
    if expected is not None and expected != row.version:
        current, _ = document_of(project["id"])
        raise AudioRefused("This project's sound was saved in another window after you opened it. Nothing was "
                           "overwritten: keep yours as a copy (export), or load the saved one.", 409,
                           code="audio_version_conflict", current={"document": current, "version": row.version})
    quota(adding_bytes=len(text) - len(row.data or ""))
    try:
        update_resource("assets", row.id, {"data": document}, expected_version=expected)
    except VersionConflict:
        raise AudioRefused("This project's sound was saved in another window.", 409,
                           code="audio_version_conflict") from None
    db.session.refresh(row)
    return document, row


@bp.put("/api/projects/<project_id>/audio")
def put_audio(project_id: str):
    from .routes import request_json

    project = _project(project_id, write=True)
    payload = request_json()
    document, row = _save(project, payload.get("document"), payload.get("expected_version"))
    security.record("audio_save", target_type="project", target_id=project_id, metadata={"version": row.version})
    return jsonify(_answer(project, document, row))


@bp.post("/api/projects/<project_id>/audio/preview")
def preview(project_id: str):
    """The AUD0 block of the saved (or the given, unsaved) document, for AudioStudio's preview."""
    from .routes import request_json

    project = _project(project_id, write=False)
    payload = request_json()
    document = payload.get("document")
    if document is None:
        document, row = document_of(project_id)
        document = document or audio_studio.default_document()
    muted = payload.get("muted") or []
    if not isinstance(muted, list) or any(not isinstance(v, int) or not 0 <= v < 8 for v in muted):
        raise AudioRefused("muted must be a list of voices 0..7")
    document = audio_studio.validate_document(document)
    sounds, missing = sample_sounds(project, document)
    if missing:
        raise AudioRefused("These samples have no sound: " + ", ".join(missing), 400, code="audio_missing_samples",
                           missing=missing)
    block = audio_studio.pack_document(document, sounds, set(muted))
    return Response(block, mimetype="application/octet-stream", headers={"Cache-Control": "no-store"})


@bp.post("/api/projects/<project_id>/audio/samples")
def upload_sample(project_id: str):
    from .routes import quota

    project = _project(project_id, write=True)
    upload = request.files.get("file")
    if upload is None:
        raise AudioRefused("Choose a WAV file")
    data = upload.read(audio_studio.MAX_WAV_BYTES + 1)
    sound = audio_studio.wav_to_sample(data)
    quota(adding_bytes=len(sound))
    name = str(request.form.get("name") or Path(upload.filename or "sample").stem)[:32]
    artifact = store_sample(project, name, sound)
    return jsonify({"artifact_id": artifact["id"], "name": name, "frames": len(sound), "seconds": len(sound) / 22050}), 201


@bp.get("/api/projects/<project_id>/audio/export")
def export(project_id: str):
    project = _project(project_id, write=False)
    document, _row = document_of(project_id)
    document = document or audio_studio.default_document()
    sounds, _missing = sample_sounds(project, document)
    body = json.dumps(audio_studio.export_document(document, sounds), indent=1, sort_keys=True)
    return Response(body, mimetype="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{project_id}.prg32audio.json"'})


@bp.post("/api/projects/<project_id>/audio/import")
def import_audio(project_id: str):
    from .routes import quota, request_json

    project = _project(project_id, write=True)
    payload = request_json()
    document, sounds = audio_studio.read_export(payload.get("export"))
    quota(adding_bytes=sum(len(sound) for sound in sounds.values()))
    for sample in document["samples"]:
        artifact = store_sample(project, sample["name"], sounds[sample["artifact_id"]])
        sample["artifact_id"] = artifact["id"]      # the imported sound is this project's own copy
    document, row = _save(project, document, payload.get("expected_version"))
    security.record("audio_import", target_type="project", target_id=project_id)
    return jsonify(_answer(project, document, row))


def init_app(app) -> None:
    app.register_blueprint(bp)
