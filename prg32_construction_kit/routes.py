from __future__ import annotations

import hashlib
import io
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import (Blueprint, Response, current_app, jsonify, redirect, render_template, request, send_file,
                   send_from_directory, url_for)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .db import (
    RESOURCE_COLUMNS,
    ProjectRevision,
    VersionConflict,
    db,
    add_revision,
    create_resource,
    delete_resource,
    get_resource,
    get_revision,
    list_resources,
    list_revisions,
    release_connection,
    restore_project_state,
    set_project_deleted,
    update_if_unchanged,
    update_resource,
)
from . import (audio_studio, audio_studio_api, build_budget, project_format, publishing, retention, secrets_at_rest,
               security, sso, storage_policy, store_contract)
from .auth import Principal, current_principal, role_at_least
from .build_check import builds_available, toolchain_present
from .db import utcnow
from .build_sandbox import settings_from_config
from .provenance import build_provenance
from .build_slots import BuildServerBusy, build_slot
from .classes import supervises
from .asm_generator import ir_to_asm
from .py_generator import from_blocks, ir_to_python
from .debug_info import unavailable as debug_unavailable
from .generator import blocks_to_c, ir_to_c, sprite_to_c
from .source_maps import project_source_map
from . import python_project
from .packager import SUPPORTED_ARCHITECTURES, check_source, prepare_package
from .publisher import StorePublishFailed, publish_bundle
from .store_policy import StoreRefused, check_url, policy_from_config
from .sample_data import example_catalog
from .source_project import validate_asm_source, validate_c_source, validate_features
from . import settings as site_settings
from .auth import guest_workspace_open as auth_guest_workspace_open

bp = Blueprint("kit", __name__)


class Refusal(str):
    """A refusal's message, carrying its problem when there is one: a stable code and the exact
    place in the source ({"code", "line", "column", "end_line", "end_column", ...}), so the IDE can
    underline it and show it in the reader's language."""

    problem: dict[str, Any] | None = None

    @classmethod
    def of(cls, message: str, problem: dict[str, Any] | None) -> "Refusal":
        refusal = cls(message)
        refusal.problem = problem
        return refusal


def problem_fields(message: Any) -> dict[str, Any]:
    """{"code", "problems"} for a Refusal that names its problem; {} for a plain message."""
    problem = getattr(message, "problem", None)
    return {"code": problem["code"], "problems": [problem]} if problem else {}


def json_error(message: str, status: int = 400) -> tuple[Response, int]:
    return jsonify({"error": message, **problem_fields(message)}), status


@bp.errorhandler(audio_studio.AudioStudioError)
def handle_audio_invalid(exc: audio_studio.AudioStudioError):
    return jsonify({"error": str(exc), "code": "audio_invalid"}), 400


@bp.errorhandler(ValueError)
def handle_bad_value(exc: ValueError):
    return json_error(str(exc), 400)


@bp.errorhandler(IntegrityError)
def handle_integrity_error(_exc: IntegrityError):
    return json_error("That id already exists, or a linked project/sprite/artifact id does not exist", 409)


def request_json() -> dict[str, Any]:
    if request.is_json:
        data = request.get_json(silent=True)
        if data is None:
            if request.get_data():
                raise ValueError("Request body is not valid JSON")
            return {}
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object")
        return data
    if request.form:
        return dict(request.form)
    return {}


# --- who may see and change what ----------------------------------------------
# Every item belongs to the user who made it. Items without an owner are shared
# classroom items (the starter games, the default publish profile): everybody
# who is signed in can read them, only admins can change them. Admins can see
# and change everything.

def can_read(item: dict[str, Any] | None, principal: Principal | None = None, supervised: bool = True) -> bool:
    """Own, shared (no owner) or, for teachers and facilitators, a student's in their class (ADR-0016)."""
    principal = principal or current_principal()
    if item is None or not principal.authenticated:
        return False
    if principal.is_admin or item.get("owner_id") in (None, principal.id):
        return True
    return supervised and supervises(principal, item.get("owner_id"))


def can_write(item: dict[str, Any] | None, principal: Principal | None = None) -> bool:
    principal = principal or current_principal()
    if item is None or not principal.authenticated:
        return False
    return principal.is_admin or item.get("owner_id") == principal.id


def readable(resource: str, item_id: Any, supervised: bool = True) -> dict[str, Any] | None:
    """The item, or None when it does not exist or the user may not see it.

    ``supervised=False``: only the user's own and shared items (what they may act on as themselves).
    """
    if not item_id:
        return None
    item = get_resource(resource, str(item_id))
    return item if can_read(item, supervised=supervised) else None


def viewer_id() -> int | None:
    principal = current_principal()
    return None if principal.is_admin else principal.id


def owned(payload: dict[str, Any]) -> dict[str, Any]:
    """Make a new item belong to the current user."""
    return {**payload, "owner_id": current_principal().id}


LINKS = {"project_id": "projects", "sprite_id": "sprites", "c_artifact_id": "artifacts", "bundle_artifact_id": "artifacts"}


def checked_payload(resource: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Stop students from editing fields that only the server (or an admin) may set."""
    principal = current_principal()
    payload = dict(payload)
    if not principal.is_admin:
        payload.pop("owner_id", None)
        # Artifact files are written by the server; a hand-made path could reach another user's build.
        if resource == "artifacts":
            payload.pop("path", None)
    if resource == "publish_profiles":
        payload.pop("token_set_at", None)          # set by the server when a token is put in
        if "bearer_token" in payload:
            payload["token_set_at"] = utcnow() if payload["bearer_token"] else ""
            # Encrypted at rest (S-1): only the publish step reads it back, to send it to the Store.
            payload["bearer_token"] = secrets_at_rest.seal(str(payload["bearer_token"] or ""))
    if resource == "publish_profiles" and "store_url" in payload:
        # Only Stores the administrator approved (ADR-0008); StoreRefused is a 400 with a student-safe reason.
        check_url(str(payload["store_url"] or ""), policy_from_config(site_settings.view()))
    for column, target in LINKS.items():
        if payload.get(column) and column in RESOURCE_COLUMNS[resource]:
            linked = get_resource(target, str(payload[column]))
            if linked is None and target == "projects" and get_resource(target, str(payload[column]), include_deleted=True):
                raise PermissionError(f"Project {payload[column]} is in Recently deleted: restore it first")
            if linked is None:
                continue  # the database refuses links to missing items with a clear 409
            if not can_read(linked) or (target == "projects" and not can_write(linked)):
                raise PermissionError(f"You cannot link to {target} {payload[column]}")
    if resource == "projects" and isinstance(payload.get("game_json"), dict):
        payload["game_json"] = _checked_python(payload["game_json"])
    return payload


def _checked_python(game_json: dict[str, Any]) -> dict[str, Any]:
    """A Python project names the PRG32 Python version it is written in (ADR-0026).

    The source itself may be unfinished while a student works: the compiler checks it when it
    is generated, run or compiled. A version this kit does not know is refused, never guessed.
    """
    if game_json.get("source_mode") != "python":
        return game_json
    if not isinstance(game_json.get("source_python", ""), str):
        raise ValueError("source_python must be text")
    version = game_json.get("python_language_version", python_project.LANGUAGE_VERSION)
    if version != python_project.LANGUAGE_VERSION or isinstance(version, bool):
        raise ValueError(f"This project is written in PRG32 Python version {version}; this kit knows version "
                         f"{python_project.LANGUAGE_VERSION}")
    return {**game_json, "python_language_version": python_project.LANGUAGE_VERSION}


@bp.errorhandler(PermissionError)
def handle_forbidden(exc: PermissionError):
    return json_error(str(exc) or "Forbidden", 403)


def _token_expires_on(profile: dict[str, Any]) -> str:
    """The date after which the kit stops using this profile's Store token ("" = never or no token)."""
    days = int(site_settings.get("STORE_TOKEN_MAX_DAYS") or 0)
    if not profile.get("bearer_token") or not days or not profile.get("token_set_at"):
        return ""
    from datetime import datetime, timedelta

    try:
        return (datetime.fromisoformat(profile["token_set_at"]) + timedelta(days=days)).date().isoformat()
    except ValueError:
        return ""


def public(resource: str, item: dict[str, Any] | None) -> dict[str, Any] | None:
    """Hide server-only values before an item leaves the server.

    Artifact paths are implementation details, just like publish bearer tokens.
    Browsers use the artifact download route and never need to learn the host's
    directory layout.
    """
    if item is None:
        return item
    shown = dict(item)
    shown["can_edit"] = can_write(item)
    if resource == "artifacts":
        shown.pop("path", None)
        metadata = shown.get("metadata")
        if isinstance(metadata, dict):
            shown["metadata"] = {key: value for key, value in metadata.items() if key != "work_dir"}
    if resource == "publish_profiles":
        shown.pop("bearer_token", None)
        shown["has_token"] = bool(item.get("bearer_token"))
        shown["token_expires_on"] = _token_expires_on(item)
        # Publishing to the synced Cartridge Store needs no token: it happens as the signed-in user.
        shown["uses_sso"] = not item.get("bearer_token") and sso.same_service(item.get("store_url", ""))
    return shown


def public_build_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return package details useful to a browser without host filesystem paths."""
    shown = {key: value for key, value in result.items()
             if key not in {"bundle_path", "work_dir", "source_path", "debug_maps"}}
    # The maps themselves come from GET /api/artifacts/<id>/debug; here only whether there is one.
    shown["debug_info"] = {arch: debug_map.get("status") for arch, debug_map in (result.get("debug_maps") or {}).items()}
    return shown


def stored_file(path_value: str | None) -> Path | None:
    """Return an artifact file only if it lives in the build or artifact folders.

    Anyone can create an artifact row with any ``path``, so the SQLite database
    (which holds publish bearer tokens) must never be served, even when an
    administrator points BUILD_ROOT or ARTIFACT_ROOT at the data folder.
    """
    if not path_value:
        return None
    path = Path(path_value).resolve()
    roots = [current_app.config[key] for key in ("BUILD_ROOT", "ARTIFACT_ROOT")]
    if not any(path.is_relative_to(Path(root).resolve()) for root in roots):
        return None
    database = Path(current_app.config["DB_PATH"]).resolve()
    if path.name.startswith(database.name) and path.parent == database.parent:
        return None  # the database and its -wal / -shm / -journal files
    data_dir = Path(current_app.config["DATA_DIR"])
    if path in ((data_dir / "secret_key").resolve(), (data_dir / "initial_admin_password").resolve()):
        return None  # the key that signs sign-in cookies, and the first admin's random password
    return path if path.is_file() else None


# A project id as it appears in page addresses (the same shape auth.GUEST_PAGES accepts).
PAGE_PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def open_project(project_id: str | None) -> dict[str, str] | None:
    """The project the top menu works on (base.html), or None. Only its id: the menu's links."""
    if not project_id or not PAGE_PROJECT_ID.match(project_id):
        return None
    return {"id": project_id}


@bp.get("/")
def index():
    # The Projects page: no project is open, so the top menu shows the kit's own items.
    return render_template("index.html")


@bp.get("/projects/<project_id>")
def project_editor(project_id: str):
    """The classic editor is gone (ADR-0024): old links open the project in the IDE."""
    return redirect(url_for("kit.project_ide", project_id=project_id), 302)


@bp.get("/ide/<project_id>")
def project_ide(project_id: str):
    """The IDE: project tree, tabs, Monaco and Blockly, panels, command palette (ADR-0013, ADR-0024)."""
    signed_in = current_principal().authenticated
    project = readable("projects", project_id) if signed_in else None
    # A guest's project is in their browser (theirs to change); a missing or someone else's
    # project is reported by the page itself, and its tools open read-only.
    can_edit = can_write(project) if project is not None else not signed_in
    return render_template("ide.html", project_id=project_id, can_edit=can_edit, nav_project=open_project(project_id))


@bp.get("/sprites")
def sprite_editor():
    """The Sprite Lab menu item: choose a project, then Sprite Lab opens in its IDE (ADR-0024)."""
    return render_template("audio_studio_pick.html", tool="sprites")


@bp.get("/artifacts")
def artifacts_page():
    return render_template("artifacts.html")


@bp.get("/player")
def player_page():
    """Run a .prg32 cartridge in the browser (the PRG32-QT core compiled to WebAssembly).

    /player?project=<id> plays that project's newest compiled cartridge (player.js).
    """
    return render_template("player.html", nav_project=open_project(request.args.get("project")))


@bp.get("/publish")
def publish_page():
    # Only for showing or hiding buttons; the API checks the role itself (ADR-0009).
    return render_template("publish.html", can_publish=role_at_least(current_principal().role, "publisher"))


@bp.get("/service-worker.js")
def service_worker():
    """The service worker at the root, so its scope covers every page (it caches static files only)."""
    response = send_from_directory(Path(current_app.static_folder), "service-worker.js", mimetype="text/javascript")
    response.headers["Service-Worker-Allowed"] = "/"  # Cache-Control: no-store, like every non-static answer
    return response


@bp.get("/documentation")
def documentation_page():
    docs_dir = Path(current_app.root_path).parent / "docs"
    docs = sorted(str(path.relative_to(docs_dir)) for path in docs_dir.rglob("*.md")) if docs_dir.exists() else []
    return render_template("documentation.html", docs=docs)


@bp.get("/docs/<path:filename>")
def docs_file(filename: str):
    docs_dir = Path(current_app.root_path).parent / "docs"
    return send_from_directory(docs_dir, filename)


@bp.get("/.well-known/prg32-construction-kit.json")
def discovery():
    root = request.url_root.rstrip("/")
    return jsonify(
        {
            "abi": "prg32-construction-kit-discovery-1.0",
            "name": "PRG32-Construction-Kit",
            "services": {
                "projects": f"{root}/api/projects",
                "sprites": f"{root}/api/sprites",
                "assets": f"{root}/api/assets",
                "artifacts": f"{root}/api/artifacts",
                "builds": f"{root}/api/builds",
                "publish_profiles": f"{root}/api/publish_profiles",
                "publish": f"{root}/api/publish",
                "login": f"{root}/auth/login",
                "me": f"{root}/auth/me",
            },
            "auth": {"required": True, "token_header": "Authorization: Bearer <token>"},
            "sso": {"enabled": sso.enabled(), "abi": sso.protocol.SSO_ABI},
            # False means Compile Cartridge makes source bundles only (docs/install_cartridge_build.md).
            "cartridge_builds": {"available": builds_available(current_app.config["PRG32_BUILD_COMMAND"]),
                                 "architectures": list(SUPPORTED_ARCHITECTURES)},
            # "local": guests may make games kept in their own browser only; "off": no guest entry (ADR-0017).
            "guest_mode": site_settings.get("PRG32_GUEST_MODE"),
            # True: the kit opens without an account, games kept in the browser (ADR-0023).
            "guest_workspace": auth_guest_workspace_open(),
        }
    )


@bp.route("/api/<resource>", methods=["GET"])
def api_list(resource: str):
    if resource not in RESOURCE_COLUMNS:
        return json_error(f"Unknown resource: {resource}", 404)
    filters = {key: value for key, value in request.args.items() if key in {"project_id", "sprite_id", "kind", "status"}}
    # GET /api/projects?deleted=1 lists the user's "Recently deleted" projects instead.
    deleted = resource == "projects" and request.args.get("deleted") in ("1", "true")
    items = list_resources(resource, filters, viewer_id=viewer_id(), deleted=deleted)
    return jsonify({resource: [public(resource, item) for item in items]})


def _size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def quota(adding_bytes: int = 0, adding_projects: int = 0) -> None:
    """Refuse (413) a change that takes the current account over its limits (ADR-0017)."""
    storage_policy.check(current_principal(), site_settings.view(), adding_bytes=adding_bytes,
                         adding_projects=adding_projects)


@bp.errorhandler(storage_policy.QuotaExceeded)
def quota_exceeded(error: storage_policy.QuotaExceeded):
    security.record("quota_exceeded", target_type="user", target_id=current_principal().id, outcome="denied",
                    metadata={"bytes": error.usage["bytes"], "projects": error.usage["projects"]})
    return jsonify({"error": str(error), "code": "quota_exceeded", "usage": error.usage}), 413


@bp.get("/api/storage")
def api_storage():
    """This account's usage and limits (ADR-0017)."""
    principal = current_principal()
    answer = storage_policy.usage(principal.id, site_settings.view())
    if principal.is_admin:
        answer.update(quota_bytes=0, quota_projects=0)  # administrators have no limit
    return jsonify(answer)


@bp.route("/api/<resource>", methods=["POST"])
def api_create(resource: str):
    if resource not in RESOURCE_COLUMNS:
        return json_error(f"Unknown resource: {resource}", 404)
    payload = checked_payload(resource, request_json())
    if "owner_id" not in payload or payload["owner_id"] in (None, ""):
        payload = owned(payload)
    if resource == "assets" and payload.get("kind") == audio_studio_api.KIND:
        payload["data"] = audio_studio.validate_document(payload.get("data"))   # the same rules as AudioStudio
    quota(adding_bytes=_size(payload), adding_projects=1 if resource == "projects" else 0)
    item = create_resource(resource, payload)
    return jsonify(public(resource, item)), 201


@bp.route("/api/<resource>/<item_id>", methods=["GET", "PUT", "DELETE"])
def api_item(resource: str, item_id: str):
    if resource not in RESOURCE_COLUMNS:
        return json_error(f"Unknown resource: {resource}", 404)
    if resource == "projects" and request.method == "DELETE" and request.args.get("purge") in ("1", "true"):
        return _purge_project(item_id)
    existing = readable(resource, item_id)
    if existing is None:
        return json_error("Not found", 404)
    if request.method == "GET":
        return jsonify(public(resource, existing))
    if not can_write(existing):
        return json_error("This is a shared classroom item: make your own copy to change it", 403)
    if request.method == "DELETE":
        if resource == "projects":
            # Projects go to "Recently deleted" first, so a wrong click can be undone.
            set_project_deleted(item_id, True)
        elif resource == "artifacts":
            from .retention import delete_artifact

            if not delete_artifact(item_id):   # the uploaded file goes with it (ADR-0022)
                return json_error("Not found", 404)
        elif not delete_resource(resource, item_id):
            return json_error("Not found", 404)
        return jsonify({"deleted": True, "id": item_id})
    payload = checked_payload(resource, request_json())
    expected = payload.pop("expected_version", None) if resource in ("projects", "assets") else None
    if resource == "assets" and existing.get("kind") == audio_studio_api.KIND and "data" in payload:
        payload["data"] = audio_studio.validate_document(payload["data"])   # the same rules as AudioStudio
    autosave = bool(payload.pop("autosave", False)) if resource == "projects" else False
    if expected is not None and (not isinstance(expected, int) or isinstance(expected, bool)):
        return json_error("expected_version must be a whole number")
    if expected is not None and expected != existing.get("version", 0):
        if resource == "assets":
            return jsonify({"error": "This item was saved elsewhere after you opened it. Nothing was overwritten.",
                            "code": "version_conflict", "current": public("assets", existing)}), 409
        return _version_conflict(existing)
    if resource == "projects" and "game_json" in payload and project_type(payload["game_json"]) != project_type(existing.get("game_json")):
        return _type_locked(existing)
    changed = {key: value for key, value in payload.items() if key in RESOURCE_COLUMNS[resource]}
    quota(adding_bytes=_size(changed) - _size({key: existing.get(key) for key in changed}))
    if resource == "projects" and _source_changes(existing, payload) and (not autosave or _history_is_old(item_id)):
        # Keep the version that is about to be replaced in the project's history.
        # Autosaves do so only now and then, so they do not fill it (ADR-0017).
        save_revision(existing, "autosave" if autosave else "save")
    try:
        item = update_resource(resource, item_id, payload, expected_version=expected)
    except VersionConflict:
        if resource == "assets":
            return jsonify({"error": "This item was saved elsewhere after you opened it. Nothing was overwritten.",
                            "code": "version_conflict"}), 409
        return _version_conflict(get_resource("projects", item_id))
    if item is None:
        return json_error("Not found", 404)
    return jsonify(public(resource, item))


# --- project types (ADR-0024) ---------------------------------------------------------------
# A project is written in Blocks, C, assembly or PRG32 Python (ADR-0026), chosen when it is made.
# The type never changes, except once from Blocks to C or assembly (convert_to): a save or a
# restore that would change it is refused.
PROJECT_TYPES = {"blocks": "Blocks", "c": "C", "asm": "Assembly (RISC-V)", "python": "Python (PRG32 Python)"}


def project_type(game_json: Any) -> str:
    mode = game_json.get("source_mode") if isinstance(game_json, dict) else None
    return mode if mode in ("c", "asm", "python") else "blocks"


def _type_locked(project: dict[str, Any]):
    kind = project_type(project.get("game_json"))
    hint = (" A Blocks project can be converted to C or assembly once (Convert), and never back."
            if kind == "blocks" else "")
    return jsonify({"error": f"This project is written in {PROJECT_TYPES[kind]}; its type cannot change.{hint}",
                    "code": "type_locked", "project_type": kind}), 409


@bp.post("/api/projects/<project_id>/convert_to")
def api_convert_project_type(project_id: str):
    """Convert a Blocks project to C or assembly, for good: {"language": "c"|"asm", "expected_version"?}.

    The code is the generated code, explained, now the student's own; the Blocks version is kept
    in History (it can be downloaded, not restored over the converted project)."""
    from .sample_data import blocks_as_code

    payload = request_json()
    language = payload.get("language")
    if language not in ("c", "asm"):
        return json_error("language must be c or asm")
    project = readable("projects", project_id)
    if project is None:
        return json_error("Project not found", 404)
    if not can_write(project):
        return json_error("This is a shared classroom project: make your own copy to convert it", 403)
    if project_type(project.get("game_json")) != "blocks":
        return _type_locked(project)
    expected = payload.get("expected_version")
    if expected is not None and expected != project.get("version", 0):
        return _version_conflict(project)
    try:
        game_json = blocks_as_code({**project, "audio_studio": audio_studio_api.document_of(project_id)[0]}, language)
    except Exception as exc:  # noqa: BLE001 - blocks that do not generate cannot be converted
        return json_error(f"These blocks cannot be converted yet: {exc}")
    save_revision(project, "convert")
    try:
        item = update_resource("projects", project_id, {"game_json": game_json}, expected_version=project.get("version", 0))
    except VersionConflict:
        return _version_conflict(get_resource("projects", project_id))
    security.record("project_convert", target_type="project", target_id=project_id, metadata={"language": language})
    return jsonify(public("projects", item))


def _version_conflict(current: dict[str, Any] | None):
    """409: somebody saved this project after the version this save started from. Nothing was changed."""
    return jsonify({"error": "This project was saved in another window (or by someone else) after you opened it. "
                             "Nothing was overwritten: keep your version as a copy, or load the saved one.",
                    "code": "version_conflict", "current": public("projects", current)}), 409


def _history_is_old(project_id: str) -> bool:
    newest = db.session.scalars(select(ProjectRevision.created_at).where(ProjectRevision.project_id == project_id)
                                .order_by(ProjectRevision.seq.desc()).limit(1)).first()
    if newest is None:
        return True
    minutes = int(site_settings.get("PRG32_KIT_AUTOSAVE_SNAPSHOT_MINUTES"))
    age = datetime.now(timezone.utc) - datetime.fromisoformat(newest)
    return age.total_seconds() >= minutes * 60


def _project_children(project_id: str, everyone: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The sprites and assets of a project that the current user may see (all of them with ``everyone``).

    They are sorted by name and content, never by id or time, so the archive
    of a project (and of its imported copy) always lists them in the same order.
    """
    def by_content(resource: str) -> list[dict[str, Any]]:
        rows = list_resources(resource, {"project_id": project_id}, viewer_id=None if everyone else viewer_id())
        fields = project_format.SPRITE_FIELDS if resource == "sprites" else project_format.ASSET_FIELDS
        return sorted(rows, key=lambda row: (str(row.get("name") or ""),
                                             json.dumps([row.get(field) for field in fields], sort_keys=True)))
    return by_content("sprites"), by_content("assets")


def _create_from_contents(contents: dict[str, Any], title: str | None = None) -> dict[str, Any]:
    """Store an imported (or copied) project with its sprites and assets for the current user.

    Everything was checked before this point; if storing still fails half way,
    the parts already made are removed again so no half project is left.
    """
    fields = dict(contents["project"])
    if title:
        fields["title"] = title
    samples = contents.get("audio_samples") or []
    quota(adding_bytes=_size({key: value for key, value in contents.items() if key != "audio_samples"})
          + sum(len(sample["pcm"]) for sample in samples), adding_projects=1)
    project = create_resource("projects", owned(fields))
    made: list[tuple[str, str]] = []
    try:
        # AudioStudio samples become the new owner's own sounds; the document names the new copies.
        new_ids = {}
        for sample in samples:
            artifact = audio_studio_api.store_sample(project, sample["name"], sample["pcm"])
            made.append(("artifacts", artifact["id"]))
            new_ids[sample["artifact_id"]] = artifact["id"]
        for resource in ("sprites", "assets"):
            for row in contents[resource]:
                if resource == "assets" and row.get("kind") == audio_studio_api.KIND:
                    row = {**row, "data": audio_studio_api.renamed_samples(row.get("data"), new_ids)}
                child = create_resource(resource, owned({**row, "project_id": project["id"]}))
                made.append((resource, child["id"]))
    except Exception:
        for resource, child_id in reversed(made):
            delete_resource(resource, child_id)
        delete_resource("projects", project["id"])
        raise
    return project


@bp.get("/api/projects/<project_id>/manifest")
def api_project_manifest(project_id: str):
    """The project's prg32.project.json, as it would be written into the archive."""
    project = readable("projects", project_id)
    if project is None:
        return json_error("Project not found", 404)
    sprites, assets = _project_children(project_id)
    return jsonify(project_format.build_manifest(project, sprites, assets))


@bp.get("/api/projects/<project_id>/archive")
def api_project_archive(project_id: str):
    """Download the portable project archive (.prg32project.zip)."""
    project = readable("projects", project_id)
    if project is None:
        return json_error("Project not found", 404)
    sprites, assets = _project_children(project_id)
    data = project_format.export_archive(project, sprites, assets, audio_studio_api.archive_samples(project))
    return send_file(io.BytesIO(data), mimetype=project_format.ARCHIVE_CONTENT_TYPE, as_attachment=True,
                     download_name=project_format.archive_filename(project))


@bp.post("/api/projects/<project_id>/duplicate")
def api_duplicate_project(project_id: str):
    """Make the current user's own copy of a project, including its sprites and assets."""
    project = readable("projects", project_id)
    if project is None:
        return json_error("Project not found", 404)
    payload = request_json()
    title = payload.get("title")
    if title is not None and (not isinstance(title, str) or not title.strip() or len(title) > 200):
        return json_error("title must be text of at most 200 characters")
    sprites, assets = _project_children(project_id)
    contents = project_format.contents_from_files(project_format.project_files(
        project, sprites, assets, audio_studio_api.archive_samples(project)))
    copy = _create_from_contents(contents, title=(title or f"{project['title']} (copy)").strip())
    return jsonify(public("projects", copy)), 201


# --- "Recently deleted" -------------------------------------------------------

@bp.post("/api/projects/<project_id>/restore")
def api_restore_deleted_project(project_id: str):
    """Bring a project back from "Recently deleted"."""
    project = get_resource("projects", project_id, include_deleted=True)
    if not can_read(project):
        return json_error("Project not found", 404)
    if not can_write(project):
        return json_error("This is a shared classroom item: only a teacher can restore it", 403)
    if project.get("deleted_at"):
        project = set_project_deleted(project_id, False)
    return jsonify(public("projects", project))


def _purge_project(project_id: str):
    """DELETE /api/projects/<id>?purge=1: remove a project for good (admins only).

    Its revisions, assets and builds go with it; sprites and artifacts stay
    but are no longer linked to it (the database does this, see db.py).
    """
    project = get_resource("projects", project_id, include_deleted=True)
    if not can_read(project):
        return json_error("Not found", 404)
    if not current_principal().is_admin:
        return json_error("Only a teacher (admin) can delete a project for good", 403)
    retention.purge_project(project_id, current_app.config["BUILD_ROOT"])  # with its builds, artifacts and folders
    return jsonify({"deleted": True, "id": project_id, "purged": True})


@bp.post("/api/admin/retention")
def api_retention():
    """Apply the retention policy (ADR-0017). {"dry_run": true} (the default) only reports."""
    if not current_principal().is_admin:
        return json_error("Only teachers with the admin role can do this", 403)
    dry_run = request_json().get("dry_run", True) is not False
    report = retention.apply(site_settings.view(), dry_run=dry_run)
    if not dry_run:
        security.record("retention_run", target_type="storage", metadata={
            "purged_projects": len(report["purged_projects"]), "pruned_builds": len(report["pruned_builds"]),
            "removed_folders": len(report["removed_folders"])})
    return jsonify(report)


# --- revisions: the History menu -------------------------------------------------
# Before a save replaces a project's source, the old version is kept as a
# revision. A revision holds the same files as a project archive.

def _source_changes(project: dict[str, Any], payload: dict[str, Any]) -> bool:
    """True when a PUT would change the Blocks program, the Advanced C, the assembly or the Python."""
    def typed_source(game_json: Any) -> tuple[Any, Any, Any, Any]:
        saved = game_json if isinstance(game_json, dict) else {}
        return saved.get("source_mode"), saved.get("source_c"), saved.get("source_asm"), saved.get("source_python")
    if "blocks_json" in payload and payload["blocks_json"] != project.get("blocks_json"):
        return True
    return "game_json" in payload and typed_source(payload["game_json"]) != typed_source(project.get("game_json"))


def save_revision(project: dict[str, Any], reason: str) -> dict[str, Any] | None:
    """Keep the project as it is now as a revision (None if it equals the newest one)."""
    sprites, assets = _project_children(project["id"], everyone=True)
    files = project_format.project_files(project, sprites, assets)
    # The manifest lists the sprite files, then the asset files, in the order of these rows.
    entries = json.loads(files[project_format.MANIFEST_NAME])["assets"]
    child_ids = {entry["path"]: row["id"] for entry, row in zip(entries, [*sprites, *assets])}
    return add_revision(project, files, reason, keep=site_settings.get("PRG32_KIT_MAX_REVISIONS"),
                        child_ids=child_ids)


def restore_plan(revision: dict[str, Any], contents: dict[str, Any], project_id: str) -> dict[str, dict[str, Any]]:
    """Decide, for each sprite/asset of a revision, which current row it goes back into.

    Identity rules (docs/project_history.md):
    1. the row the revision recorded for that file (``child_ids``), if it still
       belongs to this project and is the same kind of item;
    2. otherwise (older revisions, or the row was deleted) the first unused
       current row of the same kind with the same name;
    3. otherwise a new row.
    Current rows that no file claims are deleted. Rows of other projects are never touched.
    """
    entries = [entry for entry in contents["manifest"].get("assets", [])]
    recorded = revision.get("child_ids", {})
    current_sprites, current_assets = _project_children(project_id, everyone=True)
    plan: dict[str, dict[str, Any]] = {}
    for resource, kind, rows, current in (("sprites", "sprite", contents["sprites"], current_sprites),
                                          ("assets", "asset", contents["assets"], current_assets)):
        paths = [entry["path"] for entry in entries if entry.get("kind") == kind]
        available = {row["id"]: row for row in current}
        update, create = [], []
        pending: list[tuple[str, dict[str, Any]]] = []
        for path, values in zip(paths, rows):
            row_id = recorded.get(path)
            if row_id in available:
                update.append((row_id, values))
                del available[row_id]
            else:
                pending.append((path, values))
        for _path, values in pending:
            same_name = next((row_id for row_id, row in available.items() if row.get("name") == values.get("name")),
                             None)
            if same_name is not None:
                update.append((same_name, values))
                del available[same_name]
            else:
                create.append(values)
        plan[resource] = {"update": update, "create": create, "delete": list(available)}
    return plan


def _own_project(project_id: str) -> tuple[dict[str, Any] | None, tuple[Response, int] | None]:
    """The project if the current user owns it (or is an admin); else an error response."""
    project = readable("projects", project_id)
    if project is None:
        return None, json_error("Project not found", 404)
    if not can_write(project):
        return None, json_error("Only the owner of a project (or a teacher) can see its history", 403)
    return project, None


@bp.get("/api/projects/<project_id>/revisions")
def api_project_revisions(project_id: str):
    project, error = _own_project(project_id)
    if error:
        return error
    return jsonify({"project_id": project_id, "revisions": list_revisions(project_id)})


@bp.get("/api/projects/<project_id>/revisions/<revision_id>/archive")
def api_revision_archive(project_id: str, revision_id: str):
    """Download one revision as a .prg32project.zip, like the project archive."""
    project, error = _own_project(project_id)
    if error:
        return error
    revision = get_revision(project_id, revision_id)
    if revision is None:
        return json_error("Revision not found", 404)
    name = project_format.archive_filename({"title": revision["title"]}).replace(
        project_format.ARCHIVE_SUFFIX, f"-revision-{revision['number']}{project_format.ARCHIVE_SUFFIX}")
    return send_file(io.BytesIO(project_format.write_archive(revision["files"])),
                     mimetype=project_format.ARCHIVE_CONTENT_TYPE, as_attachment=True, download_name=name)


@bp.post("/api/projects/<project_id>/revisions/<revision_id>/restore")
def api_restore_revision(project_id: str, revision_id: str):
    """Go back to a revision. The current version is kept as a revision first, so nothing is lost."""
    project, error = _own_project(project_id)
    if error:
        return error
    revision = get_revision(project_id, revision_id)
    if revision is None:
        return json_error("Revision not found", 404)
    try:
        contents = project_format.contents_from_files(revision["files"])
    except project_format.ProjectFormatError as exc:
        return json_error(f"This saved version cannot be restored: {exc}", 422)
    if project_type(contents["project"].get("game_json")) != project_type(project.get("game_json")):
        # A Blocks version of a converted project: it can be downloaded, never restored over it.
        return _type_locked(project)
    plan = restore_plan(revision, contents, project_id)
    saved = save_revision(project, "restore")
    fields = contents["project"]
    # Project fields, changed sprites/assets (same rows, same ids), new ones and removed
    # ones are all stored in one transaction: if anything fails, nothing changes.
    updated = restore_project_state(
        project_id, {key: fields[key] for key in ("title", "description", "author", "tags", "blocks_json", "game_json")},
        plan, new_owner_id=project.get("owner_id"))
    return jsonify({"project": public("projects", updated), "restored_revision": revision_id,
                    "saved_revision": saved["id"] if saved else None})


@bp.post("/api/projects/import")
def api_import_project():
    payload: Any
    if "file" in request.files:
        data = request.files["file"].read(project_format.MAX_ARCHIVE_BYTES + 1)
        if project_format.is_archive(data):
            contents = project_format.import_archive(data)
            project = _create_from_contents(contents)
            return jsonify({**public("projects", project), "ignored_files": contents["ignored"]}), 201
        try:
            payload = json.loads(data.decode("utf-8"))
        except Exception as exc:
            return json_error(f"Could not parse JSON import: {exc}")
    else:
        payload = request_json()
    if isinstance(payload, dict) and payload.get("abi") == project_format.LEGACY_EXPORT_ABI:
        # The kit's own older export: read it through the project-format migrations.
        return jsonify(public("projects", _create_from_contents(project_format.import_legacy_export(payload)))), 201
    if isinstance(payload, dict) and "project" in payload:
        payload = payload["project"]
    if not isinstance(payload, dict):
        return json_error("Import file must contain a JSON object with a project")
    item = create_resource(
        "projects",
        owned({
            "title": payload.get("title", "Imported PRG32 Game"),
            "description": payload.get("description", "Imported from JSON."),
            "author": payload.get("author", "Student"),
            "tags": payload.get("tags", ["imported"]),
            "blocks_json": payload.get("blocks_json") or payload.get("blocks") or {},
            "game_json": payload.get("game_json") or payload.get("game_ir") or {},
        }),
    )
    return jsonify(public("projects", item)), 201


@bp.get("/api/examples")
def api_list_examples():
    """List the complete Blocks games and the short Blocks sketches of the upstream PRG32 examples."""
    return jsonify(
        {
            "examples": [
                {"slug": item["slug"], "title": item["title"], "description": item["description"], "kind": item["kind"]}
                for item in example_catalog()
            ]
        }
    )


@bp.get("/api/starters/<kind>")
def api_starter(kind: str):
    """A new project's starting point: Blocks, C or assembly (?title= gives the entry names). Stores nothing."""
    from .sample_data import starter_project

    title = str(request.args.get("title") or "My PRG32 Game")[:200]
    try:
        return jsonify(starter_project(kind, title))
    except ValueError as error:
        return json_error(str(error), 404)


@bp.post("/api/examples/<slug>/import")
def api_import_example(slug: str):
    for item in example_catalog():
        if item["slug"] == slug:
            quota(adding_bytes=_size(item["project"]), adding_projects=1)
            return jsonify(public("projects", create_resource("projects", owned(item["project"])))), 201
    return json_error("Example not found", 404)


@bp.get("/api/projects/<project_id>/export")
def api_export_project(project_id: str):
    project = readable("projects", project_id)
    if project is None:
        return json_error("Project not found", 404)
    body = json.dumps({"abi": "prg32-construction-kit-project-1.0", "project": project}, indent=2)
    return Response(
        body,
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{project_id}.blocks.json"'},
    )


def _generate_project(project_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None, tuple[Response, int] | None]:
    project = readable("projects", project_id)
    if project is None:
        return None, None, None, json_error("Project not found", 404)
    if not can_write(project):
        return project, None, None, json_error("This is a shared classroom project: make your own copy to build it", 403)
    # Its AudioStudio document: sound-effect and soundtrack blocks become fixed numbers from it.
    project = {**project, "audio_studio": audio_studio_api.document_of(project_id)[0]}
    game_ir, c_source, message = generate_sources(project)
    if message is not None:
        return project, None, None, json_error(message)
    assert game_ir is not None
    if project_type(game_ir) == "blocks":
        # Store the IR only if no other browser saved the project since we read it;
        # otherwise we would overwrite that newer save (for example Advanced C source).
        update_if_unchanged("projects", project_id,
                            {"blocks_json": project.get("blocks_json"), "game_json": project.get("game_json")},
                            {"game_json": game_ir})
    return project, game_ir, c_source, None


def generate_sources(project: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None, str | None]:
    """Validated game IR and C for a project (stored or a guest's): (game_ir, c_source, refusal).

    Pure: it reads nothing and stores nothing, so the guest workspace uses it too (guest_api.py).
    ``project["audio_studio"]`` is the project's AudioStudio document, or None.
    """
    saved = project.get("game_json") or {}
    if isinstance(saved, dict) and saved.get("source_mode") == "c":
        source = saved.get("source_c", "")
        try:
            prefix = validate_c_source(source, project.get("title") or "")
            required_features = validate_features(saved.get("required_features", []))
        except ValueError as exc:
            return None, None, str(exc)
        return {"abi": "prg32-construction-kit-c-1.0", "entry_prefix": prefix,
                "source_mode": "c", "source_c": source,
                "required_features": required_features, "warnings": []}, source, None
    if isinstance(saved, dict) and saved.get("source_mode") == "asm":
        # Handwritten assembly: checked (docs/adr/0004-handwritten-assembly-mode.md), then built as written.
        source = saved.get("source_asm", "")
        try:
            prefix = validate_asm_source(source, project.get("title") or "")
            required_features = validate_features(saved.get("required_features", []))
        except ValueError as exc:
            return None, None, str(exc)
        return {"abi": "prg32-construction-kit-asm-1.0", "entry_prefix": prefix,
                "source_mode": "asm", "source_asm": source,
                "required_features": required_features, "warnings": []}, "", None
    if isinstance(saved, dict) and saved.get("source_mode") == "python":
        # PRG32 Python (ADR-0026): parsed and checked, never run, then the same IR as the Blocks.
        try:
            game_ir = python_project.python_to_ir(saved.get("source_python", ""), project)
        except python_project.PythonError as exc:
            return None, None, Refusal.of(str(exc), exc.as_problem())
        return game_ir, ir_to_c(game_ir), None
    try:
        game_ir, c_source = blocks_to_c(project.get("blocks_json") or {}, project)
    except Exception as exc:
        return None, None, f"Conversion failed: {exc}"
    return game_ir, c_source, None


def _changed_elsewhere(project: dict[str, Any], payload: dict[str, Any]) -> bool:
    """True when the browser expected a different saved version than the one on the server.

    The editor saves, then asks for a build. If another browser window (or a
    classmate sharing the project) saved in between, the cartridge would
    silently contain their version. The editor sends what it saved so the
    server can notice and say so instead.
    """
    if "expected_blocks_json" in payload and payload["expected_blocks_json"] != project.get("blocks_json"):
        return True
    if "expected_source_python" in payload:
        saved = project.get("game_json") or {}
        saved_python = saved.get("source_python") if isinstance(saved, dict) and saved.get("source_mode") == "python" \
            else None
        return payload["expected_source_python"] != saved_python
    if "expected_source_asm" in payload:
        saved = project.get("game_json") or {}
        saved_asm = saved.get("source_asm") if isinstance(saved, dict) and saved.get("source_mode") == "asm" else None
        return payload["expected_source_asm"] != saved_asm
    if "expected_source_c" in payload:
        saved = project.get("game_json") or {}
        saved_c = saved.get("source_c") if isinstance(saved, dict) and saved.get("source_mode") == "c" else None
        return payload["expected_source_c"] != saved_c
    return False


# Which generated source files a student asks for: C, RISC-V assembly, or both.
SOURCE_LANGUAGES = ("c", "asm", "both")
_SOURCE_KINDS = {
    "c": ("c_source", "generated C", "text/x-csrc"),
    "asm": ("asm_source", "generated assembly", "text/x-asm"),
}


def _source_language(payload: dict[str, Any], game_ir: dict[str, Any]) -> tuple[str, tuple[Response, int] | None]:
    if game_ir.get("source_mode") == "asm":
        # An assembly project has no C: it always builds the assembly the student wrote.
        if payload.get("source_language", "asm") != "asm":
            return "asm", json_error("An assembly project builds the assembly you wrote; it has no C to generate.")
        return "asm", None
    language = payload.get("source_language", "c")
    if language not in SOURCE_LANGUAGES:
        return "c", json_error("source_language must be one of: " + ", ".join(SOURCE_LANGUAGES))
    if language != "c" and game_ir.get("source_mode") == "c":
        return "c", json_error("Assembly is generated from Blocks. An Advanced C project compiles the C you wrote.")
    return language, None


def _generated_sources(language: str, game_ir: dict[str, Any], c_source: str) -> dict[str, str]:
    """The source files for one request, C first: {"c": ..., "asm": ...}."""
    sources: dict[str, str] = {}
    if language in ("c", "both"):
        sources["c"] = c_source
    if language in ("asm", "both"):
        handwritten = game_ir.get("source_mode") == "asm"
        sources["asm"] = game_ir["source_asm"] if handwritten else ir_to_asm(game_ir)
    return sources


def _source_artifact(project_id: str, project: dict[str, Any], language: str, text: str,
                     metadata: dict[str, Any]) -> dict[str, Any]:
    kind, label, content_type = _SOURCE_KINDS[language]
    return create_resource("artifacts", owned({
        "project_id": project_id,
        "kind": kind,
        "name": f"{project['title']} {label}",
        "content_type": content_type,
        "text_content": text,
        "metadata": metadata,
    }))


@bp.post("/api/projects/<project_id>/convert")
def api_convert_project(project_id: str):
    # Optional: {"source_language": "c" | "asm" | "both"} (default "c").
    payload = request_json()
    project, game_ir, c_source, error = _generate_project(project_id)
    if error:
        return error
    assert project and game_ir is not None and c_source is not None
    language, error = _source_language(payload, game_ir)
    if error:
        return error
    sources = _generated_sources(language, game_ir, c_source)
    metadata = {"entry_prefix": game_ir.get("entry_prefix"), "warnings": game_ir.get("warnings", [])}
    artifacts = {lang: _source_artifact(project_id, project, lang, text, metadata) for lang, text in sources.items()}
    body: dict[str, Any] = {"project": public("projects", get_resource("projects", project_id)), "game_ir": game_ir,
                            "source_language": language,
                            "artifact": public("artifacts", next(iter(artifacts.values()))),
                            "artifacts": [public("artifacts", artifact) for artifact in artifacts.values()]}
    if "c" in sources:
        body["c_source"] = sources["c"]
    if "asm" in sources:
        body["asm_source"] = sources["asm"]
        body["asm_artifact"] = public("artifacts", artifacts["asm"])
    if from_blocks(game_ir):
        # The same game in PRG32 Python, to read beside game.c (py_generator.py); it is never built.
        body["python_source"] = ir_to_python(game_ir)
    return jsonify(body)


@bp.post("/api/projects/<project_id>/package")
def api_package_project(project_id: str):
    # Optional: {"architectures": ["esp32c6"]} builds only the cartridges a student asked for.
    payload = request_json()
    requested = payload.get("architectures")
    if requested is not None:
        if (not isinstance(requested, list) or not requested
                or any(arch not in SUPPORTED_ARCHITECTURES for arch in requested)):
            return json_error("architectures must be a non-empty list of: " + ", ".join(SUPPORTED_ARCHITECTURES))
        requested = list(dict.fromkeys(requested))
    project, game_ir, c_source, error = _generate_project(project_id)
    if error:
        return error
    assert project and game_ir is not None and c_source is not None
    # Optional: {"source_language": "asm"} compiles the generated assembly instead of the
    # C; "both" compiles the C and puts both files in the bundle.
    language, error = _source_language(payload, game_ir)
    if error:
        return error
    if _changed_elsewhere(project, payload):
        return json_error("This project was changed in another browser window after you saved it. "
                          "Reload the project to see the newest version, then compile again.", 409)
    quota(adding_bytes=1)  # a full account cannot add cartridges and bundles
    try:
        audio = audio_studio_api.project_audio(project)   # the AudioStudio sound for every cartridge
    except audio_studio_api.AudioRefused as refused:
        return jsonify({"error": str(refused), **refused.details}), refused.status
    except audio_studio.AudioStudioError as invalid:
        return json_error(f"The project's AudioStudio sound cannot be packed: {invalid}")
    # Every build gets its own id and its own folder, so many students (or one
    # student in several browser windows) can build at the same time without
    # touching each other's files. Build slots keep the number of compilers
    # running at once under control; the database connection is handed back
    # while a build waits or compiles so other requests are never starved.
    release_connection()
    try:
        with build_slot(current_app.config["BUILD_ROOT"] / ".slots",
                        site_settings.get("PRG32_MAX_PARALLEL_BUILDS"),
                        site_settings.get("PRG32_BUILD_QUEUE_TIMEOUT")), \
                build_budget.reserve(current_app.config["BUILD_ROOT"],
                                     site_settings.get("PRG32_BUILD_MAX_MB") * 1024 * 1024,
                                     site_settings.get("PRG32_BUILD_ROOT_MAX_MB") * 1024 * 1024):
            return _run_package_build(project_id, project, game_ir, _generated_sources(language, game_ir, c_source),
                                      requested, audio)
    except BuildServerBusy as exc:
        response, status = json_error(str(exc), 503)
        response.headers["Retry-After"] = "10"
        return response, status
    except build_budget.BuildDiskFull as exc:
        security.record("build_disk_full", target_type="project", target_id=project_id, outcome="refused")
        return jsonify({"error": str(exc), "code": "build_disk_full"}), 507


def _cartridge_fingerprint(result: dict[str, Any], architecture: str) -> dict[str, Any]:
    for cartridge in result.get("cartridges", []):
        if cartridge["architecture"] == architecture:
            return {"sha256": cartridge["sha256"], "bytes": cartridge["bytes"]}
    return {}


@bp.post("/api/projects/<project_id>/run")
def api_run_project(project_id: str):
    """Build the saved project for the IDE's simulator and keep nothing (run_build.py, ADR-0024).

    Anyone who can read the project may run it (a shared classroom game too); nothing is
    stored, so no quota applies. The answer carries the cartridge (base64) and its debug maps."""
    from . import run_build

    project = readable("projects", project_id)
    if project is None:
        return json_error("Project not found", 404)
    project = {**project, "audio_studio": audio_studio_api.document_of(project_id)[0]}
    try:
        audio = audio_studio_api.project_audio(project)
        return jsonify(run_build.run(project, audio))
    except audio_studio_api.AudioRefused as refused:
        return jsonify({"error": str(refused), **refused.details}), refused.status
    except audio_studio.AudioStudioError as invalid:
        return json_error(f"The project's AudioStudio sound cannot be packed: {invalid}")
    except run_build.RunRefused as refused:
        response = jsonify({"error": str(refused), "code": refused.code,
                            **({"problems": refused.details["problems"]} if refused.details.get("problems") else {})})
        if refused.details.get("retry_after"):
            response.headers["Retry-After"] = str(refused.details["retry_after"])
        return response, refused.status


@bp.post("/api/projects/<project_id>/check")
def api_check_project(project_id: str):
    """Compile the saved project with the real PRG32 toolchain and report the compiler's messages.

    The IDE's compiler check (ADR-0014): {"source_language": "c" | "asm"}. The source is the
    saved, validated one (never text the browser sends); the compiler runs in the build sandbox
    like a build, takes a build slot and the disk budget, and nothing is kept. Without the
    toolchain the answer is {"available": false}."""
    payload = request_json()
    project, game_ir, c_source, error = _generate_project(project_id)
    if error:
        return error
    assert project and game_ir is not None and c_source is not None
    language, error = _source_language(payload, game_ir)
    if error:
        return error
    if language == "both":
        return json_error("Check one language at a time: c or asm")
    build_command = current_app.config["PRG32_BUILD_COMMAND"]
    if not toolchain_present(build_command):
        return jsonify({"available": False, "source_language": language})
    quota(adding_bytes=1)
    source = _generated_sources(language, game_ir, c_source)[language]
    release_connection()
    try:
        with build_slot(current_app.config["BUILD_ROOT"] / ".slots",
                        site_settings.get("PRG32_MAX_PARALLEL_BUILDS"),
                        site_settings.get("PRG32_BUILD_QUEUE_TIMEOUT")), \
                build_budget.reserve(current_app.config["BUILD_ROOT"],
                                     site_settings.get("PRG32_BUILD_MAX_MB") * 1024 * 1024,
                                     site_settings.get("PRG32_BUILD_ROOT_MAX_MB") * 1024 * 1024):
            ok, log = check_source(build_root=current_app.config["BUILD_ROOT"], project=project, game_ir=game_ir,
                                   source=source, language=language, build_command=build_command,
                                   cart_ram_kib=site_settings.get("PRG32_CART_RAM_KIB"),
                                   timeout=site_settings.get("PRG32_BUILD_TIMEOUT"),
                                   sandbox=settings_from_config(site_settings.view()))
    except BuildServerBusy as exc:
        response, status = json_error(str(exc), 503)
        response.headers["Retry-After"] = "10"
        return response, status
    except build_budget.BuildDiskFull as exc:
        return jsonify({"error": str(exc), "code": "build_disk_full"}), 507
    return jsonify({"available": True, "ok": ok, "source_language": language, "log": log,
                    "project_version": project.get("version")})


def _run_package_build(project_id: str, project: dict[str, Any], game_ir: dict[str, Any], sources: dict[str, str],
                       requested: list[str] | None, audio: tuple[bytes, dict[str, Any]] | None = None):
    built_from = "c" if "c" in sources else "asm"
    artifacts = {lang: _source_artifact(project_id, project, lang, text,
                                        {"entry_prefix": game_ir.get("entry_prefix"), "source": "package"})
                 for lang, text in sources.items()}
    c_artifact, asm_artifact = artifacts.get("c"), artifacts.get("asm")
    build = create_resource("builds", owned({
        "project_id": project_id, "status": "running", "c_artifact_id": c_artifact["id"] if c_artifact else None,
        "metadata": {"project_updated_at": project.get("updated_at"), "built_from": built_from,
                     "asm_artifact_id": asm_artifact["id"] if asm_artifact else None}}))
    release_connection()
    build_command = current_app.config["PRG32_BUILD_COMMAND"]
    targets = list(requested or SUPPORTED_ARCHITECTURES)

    def provenance(status: str, result: dict[str, Any] | None) -> dict[str, Any]:
        return build_provenance(build_id=build["id"], started_at=started_at, finished_at=utcnow(), status=status,
                                build_command=build_command, game_ir=game_ir, sources=sources,
                                built_from=built_from, requested=targets,
                                cart_ram_kib=site_settings.get("PRG32_CART_RAM_KIB"),
                                cartridges=(result or {}).get("cartridges", []),
                                attempts=(result or {}).get("attempts", []),
                                sandbox=(result or {}).get("sandbox", "not run"),
                                python_source=(project.get("game_json") or {}).get("source_python"))

    started_at = utcnow()
    try:
        result = prepare_package(
            data_dir=current_app.config["DATA_DIR"],
            build_root=current_app.config["BUILD_ROOT"],
            project=project,
            game_ir=game_ir,
            c_source=sources.get("c"),
            asm_source=sources.get("asm"),
            build_language=built_from,
            build_id=build["id"],
            build_command=build_command,
            cart_ram_kib=site_settings.get("PRG32_CART_RAM_KIB"),
            project_json=project,
            architectures=requested,
            build_timeout=site_settings.get("PRG32_BUILD_TIMEOUT"),
            sandbox=settings_from_config(site_settings.view()),
            debug_info_enabled=site_settings.get("PRG32_DEBUG_INFO"),
            audio=audio,
        )
    except Exception as exc:
        current_app.logger.exception("Packaging failed for %s", project_id)
        update_resource("builds", build["id"], {"status": "failed", "log": f"Packaging failed: {exc}",
                                                "metadata": {**build["metadata"],
                                                             "provenance": provenance("failed", None)}})
        return json_error(f"Packaging failed: {exc}", 500)
    # "ready": at least one cartridge. With working build tools but no cartridge, the
    # compiler refused the source: that is "failed", not a harmless "source-only" bundle.
    if result["status"] != "ready" and toolchain_present(build_command):
        result["status"] = "failed"
    bundle_artifact = create_resource(
        "artifacts",
        owned({
            "project_id": project_id,
            "kind": "store_bundle" if result["publishable"] else "source_bundle",
            "name": Path(result["bundle_path"]).name,
            "content_type": "application/zip",
            "path": result["bundle_path"],
            "metadata": {
                "manifest": result["manifest"],
                "architectures": result["architectures"],
                "cart_ram_kib": result["cart_ram_kib"],
                "publishable": result["publishable"],
                "work_dir": result["work_dir"],
            },
        }),
    )
    cartridge_artifacts = []
    for architecture in result["architectures"]:
        cartridge_path = Path(result["work_dir"]) / architecture["file"]
        cartridge_artifacts.append(
            create_resource(
                "artifacts",
                owned({
                    "project_id": project_id,
                    "kind": "prg32_cartridge",
                    "name": architecture["file"],
                    "content_type": "application/vnd.prg32.cartridge",
                    "path": str(cartridge_path),
                    "metadata": {"architecture": architecture["id"], "portable": True, "build_id": build["id"],
                                 "cart_ram_kib": result["cart_ram_kib"],
                                 **_cartridge_fingerprint(result, architecture["id"])},
                }),
            )
        )
    _save_debug_artifacts(project_id, project, build["id"], result, built_from, sources, cartridge_artifacts)
    build = update_resource(
        "builds",
        build["id"],
        {
            "status": result["status"],
            "log": result["log"],
            "bundle_artifact_id": bundle_artifact["id"],
            "metadata": {
                "manifest": result["manifest"],
                "architectures": result["architectures"],
                "cart_ram_kib": result["cart_ram_kib"],
                "publishable": result["publishable"],
                "project_updated_at": project.get("updated_at"),
                "built_from": built_from,
                "asm_artifact_id": asm_artifact["id"] if asm_artifact else None,
                "audio_block_sha256": hashlib.sha256(audio[0]).hexdigest() if audio else None,
                "provenance": provenance(result["status"], result),
            },
        },
    )
    # Keep the project's newest builds only (ADR-0017); this one is the newest.
    retention.prune_builds(project_id, site_settings.get("PRG32_KIT_KEEP_BUILDS"), current_app.config["BUILD_ROOT"])
    return jsonify({
        "build": public("builds", build),
        "c_artifact": public("artifacts", c_artifact) if c_artifact else None,
        "asm_artifact": public("artifacts", asm_artifact) if asm_artifact else None,
        "bundle_artifact": public("artifacts", bundle_artifact),
        "cartridge_artifacts": [public("artifacts", artifact) for artifact in cartridge_artifacts],
        "result": public_build_result(result),
    })


def _save_debug_artifacts(project_id: str, project: dict[str, Any], build_id: str, result: dict[str, Any],
                          built_from: str, sources: dict[str, str], cartridges: list[dict[str, Any]]) -> None:
    """Save each cartridge's debug map and the build's block map as artifacts (ADR-0015).

    The cartridge artifact's metadata gets their ids, so the Player can find them.
    """
    debug_dir = Path(result["work_dir"]) / "debug"
    source_map_id = None
    saved = project.get("game_json") or {}
    if result.get("debug_maps") and project_type(saved) in ("blocks", "python"):
        try:
            _, text, source_map = project_source_map(project, built_from)
        except Exception:  # noqa: BLE001 - no block map means the Player shows source and addresses only
            current_app.logger.exception("No source map for %s", project_id)
            text, source_map = None, None
        if source_map and text == sources.get(built_from):  # the map describes exactly the file that was built
            path = debug_dir / "source_map.json"
            path.write_text(json.dumps(source_map, sort_keys=True), encoding="utf-8")
            source_map_id = create_resource("artifacts", owned({
                "project_id": project_id, "kind": "source_map", "name": "source_map.json",
                "content_type": "application/json", "path": str(path),
                "metadata": {"build_id": build_id, "language": built_from}}))["id"]
    for artifact in cartridges:
        architecture = artifact["metadata"]["architecture"]
        debug_map = (result.get("debug_maps") or {}).get(architecture)
        if debug_map is None:
            continue
        path = debug_dir / f"{architecture}.map.json"
        path.write_text(json.dumps(debug_map, sort_keys=True), encoding="utf-8")
        map_artifact = create_resource("artifacts", owned({
            "project_id": project_id, "kind": "debug_map", "name": f"{architecture}.map.json",
            "content_type": "application/json", "path": str(path),
            "metadata": {"build_id": build_id, "architecture": architecture, "status": debug_map.get("status"),
                         "cartridge_artifact_id": artifact["id"]}}))
        artifact["metadata"] = {**artifact["metadata"], "debug_map_artifact_id": map_artifact["id"],
                                "source_map_artifact_id": source_map_id, "built_from": built_from}
        update_resource("artifacts", artifact["id"], {"metadata": artifact["metadata"]})


def _json_artifact(artifact_id: Any) -> dict[str, Any] | None:
    artifact = readable("artifacts", artifact_id) if artifact_id else None
    path = stored_file(artifact.get("path")) if artifact else None
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@bp.get("/api/artifacts/<artifact_id>/debug")
def api_artifact_debug(artifact_id: str):
    """Everything the Player needs to debug one cartridge at source and block level (ADR-0015).

    Missing pieces are null, and the Player falls back to address-level debugging.
    """
    artifact = readable("artifacts", artifact_id)
    if artifact is None or artifact.get("kind") != "prg32_cartridge":
        return json_error("Cartridge not found", 404)
    metadata = artifact.get("metadata") or {}
    debug_map = _json_artifact(metadata.get("debug_map_artifact_id")) or debug_unavailable(
        "this cartridge was built without debug information")
    source_map = _json_artifact(metadata.get("source_map_artifact_id"))
    build = readable("builds", metadata.get("build_id"))
    source = None
    blocks_json = None
    python_source = None
    if build is not None:
        built_from = metadata.get("built_from") or (build.get("metadata") or {}).get("built_from") or "c"
        source_id = build.get("c_artifact_id") if built_from == "c" else (build.get("metadata") or {}).get("asm_artifact_id")
        source_artifact = readable("artifacts", source_id)
        if source_artifact is not None:
            source = {"file": "game.c" if built_from == "c" else "game.S", "language": built_from,
                      "text": source_artifact.get("text_content") or ""}
        if source_map is not None:
            bundle = readable("artifacts", build.get("bundle_artifact_id"))
            work_dir = ((bundle or {}).get("metadata") or {}).get("work_dir")
            snapshot = stored_file(str(Path(work_dir) / "project.blocks.json")) if work_dir else None
            if snapshot is not None:
                built = json.loads(snapshot.read_text(encoding="utf-8"))
                python_source = debug_python_source(built, source_map)
                blocks_json = None if python_source is not None else built.get("blocks_json")
    if source is None or (source_map and source_map.get("source_sha256") != _sha256_text(source["text"])):
        source_map, blocks_json, python_source = None, None, None  # a map is only good for exactly its source
    return jsonify({"cartridge": public("artifacts", artifact), "debug_map": debug_map, "source_map": source_map,
                    "source": source, "blocks_json": blocks_json, "python_source": python_source})


def debug_python_source(project: dict[str, Any], source_map: dict[str, Any] | None) -> dict[str, str] | None:
    """game.py for the debugger, only when the source map was made from exactly this text."""
    saved = project.get("game_json") if isinstance(project.get("game_json"), dict) else {}
    if not source_map or saved.get("source_mode") != "python":
        return None
    text = str(saved.get("source_python") or "")
    if source_map.get("python_sha256") != _sha256_text(text):
        return None
    return {"file": python_project.SOURCE_FILE, "text": text}


def _sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@bp.post("/api/sprites/<sprite_id>/convert")
def api_convert_sprite(sprite_id: str):
    sprite = readable("sprites", sprite_id)
    if sprite is None:
        return json_error("Sprite not found", 404)
    c_source = sprite_to_c(sprite)
    linked_project = readable("projects", sprite.get("project_id"))
    artifact = create_resource(
        "artifacts",
        owned({
            "sprite_id": sprite_id,
            "project_id": sprite.get("project_id") if can_write(linked_project) else None,
            "kind": "sprite_c_source",
            "name": f"{sprite['name']} sprite C",
            "content_type": "text/x-csrc",
            "text_content": c_source,
            "metadata": {"width": sprite.get("width"), "height": sprite.get("height")},
        }),
    )
    return jsonify({"sprite": public("sprites", sprite), "c_source": c_source,
                    "artifact": public("artifacts", artifact)})


@bp.post("/api/artifacts/upload")
def api_upload_artifact():
    if "file" not in request.files:
        return json_error("Missing file field")
    uploaded = request.files["file"]
    if not uploaded.filename:
        return json_error("Missing filename")
    safe_name = "".join(ch if ch.isalnum() or ch in ".-_" else "_" for ch in uploaded.filename)[-120:].lstrip(".") or "upload"
    artifact_dir = current_app.config["ARTIFACT_ROOT"] / "uploads"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    # A short unique prefix keeps two uploads with the same name from overwriting each other.
    path = artifact_dir / f"{uuid.uuid4().hex[:8]}-{safe_name}"
    project_id = request.form.get("project_id") or None
    if project_id and not can_write(readable("projects", project_id)):
        return json_error("You can only add files to your own projects", 403)
    quota(adding_bytes=request.content_length or 1)
    uploaded.save(path)
    artifact = create_resource(
        "artifacts",
        owned({
            "project_id": project_id,
            "kind": request.form.get("kind") or "upload",
            "name": safe_name,
            "content_type": uploaded.mimetype or "application/octet-stream",
            "path": str(path),
            "metadata": {"uploaded": True},
        }),
    )
    return jsonify(public("artifacts", artifact)), 201


@bp.get("/api/artifacts/<artifact_id>/download")
def api_download_artifact(artifact_id: str):
    artifact = readable("artifacts", artifact_id)
    if artifact is None:
        return json_error("Artifact not found", 404)
    name = artifact.get("name") or artifact_id
    path = stored_file(artifact.get("path"))
    if path is not None:
        return send_file(path, mimetype=artifact.get("content_type") or None, as_attachment=True, download_name=name)
    if artifact.get("path") and not artifact.get("text_content"):
        return json_error("Artifact file is missing or outside the kit data folder", 404)
    text = artifact.get("text_content") or ""
    return send_file(io.BytesIO(text.encode("utf-8")), mimetype=artifact.get("content_type") or "text/plain",
                     as_attachment=True, download_name=name)


def _audit_publish(outcome: str, payload: dict[str, Any], profile: dict[str, Any] | None, **extra: Any) -> None:
    """Every publish attempt goes in the audit log: which bundle, which store host, what happened."""
    from urllib.parse import urlparse

    store_host = urlparse(str((profile or {}).get("store_url") or "")).hostname or ""
    security.record("publish", target_type="artifact", target_id=payload.get("bundle_artifact_id") or "",
                    outcome=outcome, metadata={"store_host": store_host,
                                               "profile_id": str(payload.get("profile_id") or ""), **extra})


def _publish_refusal(stage_action: str, payload: dict[str, Any], profile: dict[str, Any] | None,
                     reason: str, message: str, status: int, outcome: str = "refused"):
    if stage_action == "publish_review":
        security.record("publish_review", target_type="artifact", target_id=payload.get("bundle_artifact_id") or "",
                        outcome=outcome, metadata={"reason": reason, "profile_id": str(payload.get("profile_id") or "")})
    else:
        _audit_publish(outcome, payload, profile, stage="refused", reason=reason)
    return jsonify({"error": message, "reason": reason}), status


def _prepare_publish(payload: dict[str, Any], stage_action: str):
    """Everything the review and the confirm step check, in the same order.

    Returns (summary, profile, artifact, path, target) or (None, ..., error response).
    """
    principal = current_principal()
    if not role_at_least(principal.role, "publisher"):
        return None, None, None, None, None, _publish_refusal(
            stage_action, payload, None, "not_publisher", publishing.MESSAGES["not_publisher"], 403, outcome="denied")
    # A teacher may read a student's bundle, but publishes only their own (or shared) work.
    profile = readable("publish_profiles", payload.get("profile_id", ""), supervised=False)
    artifact = readable("artifacts", payload.get("bundle_artifact_id", ""), supervised=False)
    if profile is None:
        return None, None, None, None, None, _publish_refusal(stage_action, payload, None, "profile_not_found",
                                                              "Publish profile not found", 404)
    if artifact is None:
        return None, profile, None, None, None, _publish_refusal(stage_action, payload, profile, "bundle_not_found",
                                                                 "Bundle artifact not found", 404)
    if artifact.get("kind") not in {"store_bundle", "source_bundle"}:
        return None, profile, artifact, None, None, _publish_refusal(
            stage_action, payload, profile, "not_a_bundle", publishing.MESSAGES["not_a_bundle"], 400)
    path = stored_file(artifact.get("path"))
    if path is None:
        return None, profile, artifact, None, None, _publish_refusal(stage_action, payload, profile, "bundle_missing",
                                                                     "Bundle file is missing on disk", 404)
    metadata = artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}
    if artifact.get("kind") != "store_bundle" or metadata.get("publishable") is not True:
        return None, profile, artifact, path, None, _publish_refusal(
            stage_action, payload, profile, "not_publishable", publishing.MESSAGES["not_publishable"], 400)
    # The Store must be approved now (ADR-0008), not only when the profile was saved.
    try:
        target = check_url(profile.get("store_url", ""), policy_from_config(site_settings.view()))
    except StoreRefused as refused:
        return None, profile, artifact, path, None, _publish_refusal(stage_action, payload, profile,
                                                                     refused.reason, str(refused), 400)
    builds = [build for build in list_resources("builds", {"project_id": artifact.get("project_id") or ""})
              if build.get("bundle_artifact_id") == artifact["id"]] if artifact.get("project_id") else []
    build = builds[0] if builds else None
    provenance = (build or {}).get("metadata", {}).get("provenance") if build else None
    try:
        inspected = publishing.inspect_bundle(path, provenance)
    except publishing.PublishRefused as refused:
        return None, profile, artifact, path, target, _publish_refusal(stage_action, payload, profile,
                                                                       refused.reason, str(refused), 400)
    try:
        # Last: checked like the Store checks it (contracts/), so nothing half-valid is ever uploaded.
        store_contract.validate_bundle(path.read_bytes())
    except store_contract.ContractViolation as violation:
        return None, profile, artifact, path, target, _publish_refusal(
            stage_action, payload, profile, "contract_" + violation.code,
            "This bundle does not meet the Store contract: " + str(violation), 400)
    expires_on = _token_expires_on(profile)
    if expires_on and expires_on < utcnow()[:10]:
        return None, profile, artifact, path, target, _publish_refusal(
            stage_action, payload, profile, "token_too_old", publishing.MESSAGES["token_too_old"], 400)
    if profile.get("bearer_token"):
        authentication = "token"
    elif sso.same_service(profile.get("store_url", "")):
        authentication = "single_sign_on"
    else:
        authentication = "none"
    summary = publishing.build_summary(target=target, authentication=authentication, profile=profile,
                                       artifact=artifact, inspected=inspected,
                                       build_id=build["id"] if build else None)
    earlier = publishing.submitted_version(summary)
    if earlier is not None and earlier.bundle_sha256 != summary["bundle"]["sha256"]:
        return None, profile, artifact, path, target, _publish_refusal(
            stage_action, payload, profile, "version_already_published",
            publishing.MESSAGES["version_already_published"], 409)
    return summary, profile, artifact, path, target, None


@bp.post("/api/publish/review")
def api_publish_review():
    """Step 1: what would be published, and a review token to confirm it (ADR-0009)."""
    payload = request_json()
    summary, profile, _artifact, _path, _target, error = _prepare_publish(payload, "publish_review")
    if error:
        return error
    token = publishing.make_review_token(current_app.config["SECRET_KEY"], summary, current_principal().id)
    from . import privacy

    privacy.record_notice(current_principal().id, "publishing", summary["store"]["host"])   # ADR-0022
    summary["privacy_notice"] = privacy.notices()["publishing"]["summary"]
    security.record("publish_review", target_type="artifact", target_id=summary["bundle"]["artifact_id"],
                    metadata={"store_host": summary["store"]["host"], "profile_id": profile["id"],
                              "cartridge": summary["cartridge"]["id"], "version": summary["cartridge"]["version"]})
    return jsonify({"summary": summary, "review_token": token, "expires_in": publishing.REVIEW_SECONDS})


@bp.post("/api/publish")
def api_publish():
    """Step 2: send the reviewed bundle. Needs {"review_token", "confirm": true} from step 1."""
    payload = request_json()
    summary, profile, artifact, path, _target, error = _prepare_publish(payload, "publish")
    if error:
        return error
    if not payload.get("review_token") or payload.get("confirm") is not True:
        _audit_publish("refused", payload, profile, stage="refused", reason="not_confirmed")
        return jsonify({"error": "Review the bundle first (POST /api/publish/review), then confirm.",
                        "reason": "not_confirmed"}), 428
    user_id = current_principal().id
    problem = publishing.check_review_token(current_app.config["SECRET_KEY"], payload["review_token"], summary, user_id)
    if problem:
        _audit_publish("refused", payload, profile, stage="refused", reason="review_mismatch")
        return jsonify({"error": problem, "reason": "review_mismatch"}), 409
    digest = publishing.summary_digest(summary)
    earlier = publishing.submitted_version(summary)
    if earlier is not None:   # the same files were already accepted there (another review, another artifact)
        _audit_publish("success", payload, profile, stage="duplicate")
        return jsonify({"state": "submitted", "duplicate": True, "summary": summary,
                        "result": json.loads(earlier.result or "{}")})
    state, previous = publishing.start_attempt(digest, user_id, profile["id"], artifact["id"], summary)
    if state == "submitted":
        _audit_publish("success", payload, profile, stage="duplicate")
        return jsonify({"state": "submitted", "duplicate": True, "summary": summary, "result": previous})
    if state == "busy":
        return jsonify({"error": "This bundle is being sent right now. Wait a moment.", "reason": "in_progress",
                        "state": "uploading"}), 409
    _audit_publish("success", payload, profile, stage="upload", cartridge=summary["cartridge"]["id"],
                   version=summary["cartridge"]["version"])
    token = secrets_at_rest.unseal(profile.get("bearer_token", ""))
    if token is None:
        publishing.finish_attempt(digest, "failed", {"ok": False, "reason": "token_unreadable"})
        return jsonify({"error": "The Store token of this profile cannot be read any more (the kit's secret key "
                                 "changed). Enter the token again in the profile.", "reason": "token_unreadable",
                        "state": "failed"}), 400
    if not token and summary["store"]["authentication"] == "single_sign_on":
        # Single sign-on: publish as the signed-in student with a one-time ticket.
        token = sso.make_ticket(current_principal().email, "api")
    try:
        result = publish_bundle(profile.get("store_url", ""), token, path)
    except StoreRefused as refused:
        # Address checks (private network, DNS) and redirects: refused, nothing more sent.
        publishing.finish_attempt(digest, "failed", {"ok": False, "reason": refused.reason})
        _audit_publish("refused", payload, profile, stage="failed", reason=refused.reason)
        return jsonify({"error": str(refused), "reason": refused.reason, "state": "failed"}), 400
    except StorePublishFailed as failed:
        publishing.finish_attempt(digest, "failed", {"ok": False, "reason": failed.reason})
        _audit_publish("failed", payload, profile, stage="failed", reason=failed.reason)
        return jsonify({"error": str(failed), "reason": failed.reason, "state": "failed"}), 502
    except Exception as exc:  # never echo the exception: it may name internal addresses
        current_app.logger.warning("Publishing failed: %s", type(exc).__name__)
        publishing.finish_attempt(digest, "failed", {"ok": False, "reason": "error"})
        _audit_publish("failed", payload, profile, stage="failed", reason=type(exc).__name__)
        return jsonify({"error": "Publishing failed. Try again later or ask your teacher.", "reason": "error",
                        "state": "failed"}), 502
    state = "submitted" if result.get("ok") else "failed"
    publishing.finish_attempt(digest, state, result)
    _audit_publish("success" if state == "submitted" else "failed", payload, profile, stage=state,
                   status_code=result.get("status_code"))
    return jsonify({"state": state, "duplicate": False, "summary": summary,
                    "profile": public("publish_profiles", profile), "artifact": public("artifacts", artifact),
                    "result": result})
