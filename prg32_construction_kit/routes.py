from __future__ import annotations

import io
import json
import uuid
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, render_template, request, send_file, send_from_directory
from sqlalchemy.exc import IntegrityError

from .db import (
    RESOURCE_COLUMNS,
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
from . import project_format, publishing, security, sso
from .auth import Principal, current_principal, role_at_least
from .build_check import builds_available, toolchain_present
from .db import utcnow
from .build_sandbox import settings_from_config
from .provenance import build_provenance
from .build_slots import BuildServerBusy, build_slot
from .asm_generator import ir_to_asm
from .generator import blocks_to_c, sprite_to_c
from .packager import SUPPORTED_ARCHITECTURES, prepare_package
from .publisher import StorePublishFailed, publish_bundle
from .store_policy import StoreRefused, check_url, policy_from_config
from .sample_data import example_catalog
from .source_project import validate_asm_source, validate_c_source, validate_features

bp = Blueprint("kit", __name__)


def json_error(message: str, status: int = 400) -> tuple[Response, int]:
    return jsonify({"error": message}), status


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

def can_read(item: dict[str, Any] | None, principal: Principal | None = None) -> bool:
    principal = principal or current_principal()
    if item is None or not principal.authenticated:
        return False
    return principal.is_admin or item.get("owner_id") in (None, principal.id)


def can_write(item: dict[str, Any] | None, principal: Principal | None = None) -> bool:
    principal = principal or current_principal()
    if item is None or not principal.authenticated:
        return False
    return principal.is_admin or item.get("owner_id") == principal.id


def readable(resource: str, item_id: Any) -> dict[str, Any] | None:
    """The item, or None when it does not exist or the user may not see it."""
    if not item_id:
        return None
    item = get_resource(resource, str(item_id))
    return item if can_read(item) else None


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
    if resource == "publish_profiles" and "store_url" in payload:
        # Only Stores the administrator approved (ADR-0008); StoreRefused is a 400 with a student-safe reason.
        check_url(str(payload["store_url"] or ""), policy_from_config(current_app.config))
    for column, target in LINKS.items():
        if payload.get(column) and column in RESOURCE_COLUMNS[resource]:
            linked = get_resource(target, str(payload[column]))
            if linked is None and target == "projects" and get_resource(target, str(payload[column]), include_deleted=True):
                raise PermissionError(f"Project {payload[column]} is in Recently deleted: restore it first")
            if linked is None:
                continue  # the database refuses links to missing items with a clear 409
            if not can_read(linked) or (target == "projects" and not can_write(linked)):
                raise PermissionError(f"You cannot link to {target} {payload[column]}")
    return payload


@bp.errorhandler(PermissionError)
def handle_forbidden(exc: PermissionError):
    return json_error(str(exc) or "Forbidden", 403)


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
        # Publishing to the synced Cartridge Store needs no token: it happens as the signed-in user.
        shown["uses_sso"] = not item.get("bearer_token") and sso.same_service(item.get("store_url", ""))
    return shown


def public_build_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return package details useful to a browser without host filesystem paths."""
    return {key: value for key, value in result.items() if key not in {"bundle_path", "work_dir", "source_path"}}


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


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/projects/<project_id>")
def project_editor(project_id: str):
    return render_template("editor.html", project_id=project_id)


@bp.get("/sprites")
def sprite_editor():
    return render_template("sprite_editor.html")


@bp.get("/artifacts")
def artifacts_page():
    return render_template("artifacts.html")


@bp.get("/player")
def player_page():
    """Run a .prg32 cartridge in the browser (the PRG32-QT core compiled to WebAssembly)."""
    return render_template("player.html")


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


@bp.route("/api/<resource>", methods=["POST"])
def api_create(resource: str):
    if resource not in RESOURCE_COLUMNS:
        return json_error(f"Unknown resource: {resource}", 404)
    payload = checked_payload(resource, request_json())
    if "owner_id" not in payload or payload["owner_id"] in (None, ""):
        payload = owned(payload)
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
        elif not delete_resource(resource, item_id):
            return json_error("Not found", 404)
        return jsonify({"deleted": True, "id": item_id})
    payload = checked_payload(resource, request_json())
    if resource == "projects" and _source_changes(existing, payload):
        # Keep the version that is about to be replaced in the project's history.
        save_revision(existing, "save")
    item = update_resource(resource, item_id, payload)
    if item is None:
        return json_error("Not found", 404)
    return jsonify(public(resource, item))


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
    project = create_resource("projects", owned(fields))
    made: list[tuple[str, str]] = []
    try:
        for resource in ("sprites", "assets"):
            for row in contents[resource]:
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
    data = project_format.export_archive(project, sprites, assets)
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
    contents = project_format.contents_from_files(project_format.project_files(project, sprites, assets))
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
    delete_resource("projects", project_id)
    return jsonify({"deleted": True, "id": project_id, "purged": True})


# --- revisions: the History menu -------------------------------------------------
# Before a save replaces a project's source, the old version is kept as a
# revision. A revision holds the same files as a project archive.

def _source_changes(project: dict[str, Any], payload: dict[str, Any]) -> bool:
    """True when a PUT would change the Blocks program, the Advanced C or the handwritten assembly."""
    def typed_source(game_json: Any) -> tuple[Any, Any, Any]:
        saved = game_json if isinstance(game_json, dict) else {}
        return saved.get("source_mode"), saved.get("source_c"), saved.get("source_asm")
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
    return add_revision(project, files, reason, keep=current_app.config["PRG32_KIT_MAX_REVISIONS"],
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


@bp.post("/api/examples/<slug>/import")
def api_import_example(slug: str):
    for item in example_catalog():
        if item["slug"] == slug:
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
    saved = project.get("game_json") or {}
    if isinstance(saved, dict) and saved.get("source_mode") == "c":
        source = saved.get("source_c", "")
        try:
            prefix = validate_c_source(source, project.get("title") or "")
            required_features = validate_features(saved.get("required_features", []))
        except ValueError as exc:
            return project, None, None, json_error(str(exc))
        return project, {"abi": "prg32-construction-kit-c-1.0", "entry_prefix": prefix,
                         "source_mode": "c", "source_c": source,
                         "required_features": required_features, "warnings": []}, source, None
    if isinstance(saved, dict) and saved.get("source_mode") == "asm":
        # Handwritten assembly: checked (docs/adr/0004-handwritten-assembly-mode.md), then built as written.
        source = saved.get("source_asm", "")
        try:
            prefix = validate_asm_source(source, project.get("title") or "")
            required_features = validate_features(saved.get("required_features", []))
        except ValueError as exc:
            return project, None, None, json_error(str(exc))
        return project, {"abi": "prg32-construction-kit-asm-1.0", "entry_prefix": prefix,
                         "source_mode": "asm", "source_asm": source,
                         "required_features": required_features, "warnings": []}, "", None
    try:
        game_ir, c_source = blocks_to_c(project.get("blocks_json") or {}, project)
    except Exception as exc:
        return project, None, None, json_error(f"Conversion failed: {exc}")
    # Store the IR only if no other browser saved the project since we read it;
    # otherwise we would overwrite that newer save (for example Advanced C source).
    update_if_unchanged("projects", project_id,
                        {"blocks_json": project.get("blocks_json"), "game_json": project.get("game_json")},
                        {"game_json": game_ir})
    return project, game_ir, c_source, None


def _changed_elsewhere(project: dict[str, Any], payload: dict[str, Any]) -> bool:
    """True when the browser expected a different saved version than the one on the server.

    The editor saves, then asks for a build. If another browser window (or a
    classmate sharing the project) saved in between, the cartridge would
    silently contain their version. The editor sends what it saved so the
    server can notice and say so instead.
    """
    if "expected_blocks_json" in payload and payload["expected_blocks_json"] != project.get("blocks_json"):
        return True
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
    # Every build gets its own id and its own folder, so many students (or one
    # student in several browser windows) can build at the same time without
    # touching each other's files. Build slots keep the number of compilers
    # running at once under control; the database connection is handed back
    # while a build waits or compiles so other requests are never starved.
    release_connection()
    try:
        with build_slot(current_app.config["BUILD_ROOT"] / ".slots",
                        current_app.config["PRG32_MAX_PARALLEL_BUILDS"],
                        current_app.config["PRG32_BUILD_QUEUE_TIMEOUT"]):
            return _run_package_build(project_id, project, game_ir, _generated_sources(language, game_ir, c_source),
                                      requested)
    except BuildServerBusy as exc:
        response, status = json_error(str(exc), 503)
        response.headers["Retry-After"] = "10"
        return response, status


def _cartridge_fingerprint(result: dict[str, Any], architecture: str) -> dict[str, Any]:
    for cartridge in result.get("cartridges", []):
        if cartridge["architecture"] == architecture:
            return {"sha256": cartridge["sha256"], "bytes": cartridge["bytes"]}
    return {}


def _run_package_build(project_id: str, project: dict[str, Any], game_ir: dict[str, Any], sources: dict[str, str],
                       requested: list[str] | None):
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
                                cart_ram_kib=current_app.config["PRG32_CART_RAM_KIB"],
                                cartridges=(result or {}).get("cartridges", []),
                                attempts=(result or {}).get("attempts", []),
                                sandbox=(result or {}).get("sandbox", "not run"))

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
            cart_ram_kib=current_app.config["PRG32_CART_RAM_KIB"],
            project_json=project,
            architectures=requested,
            build_timeout=current_app.config["PRG32_BUILD_TIMEOUT"],
            sandbox=settings_from_config(current_app.config),
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
                "provenance": provenance(result["status"], result),
            },
        },
    )
    return jsonify({
        "build": public("builds", build),
        "c_artifact": public("artifacts", c_artifact) if c_artifact else None,
        "asm_artifact": public("artifacts", asm_artifact) if asm_artifact else None,
        "bundle_artifact": public("artifacts", bundle_artifact),
        "cartridge_artifacts": [public("artifacts", artifact) for artifact in cartridge_artifacts],
        "result": public_build_result(result),
    })


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
    profile = readable("publish_profiles", payload.get("profile_id", ""))
    artifact = readable("artifacts", payload.get("bundle_artifact_id", ""))
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
        target = check_url(profile.get("store_url", ""), policy_from_config(current_app.config))
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
    if profile.get("bearer_token"):
        authentication = "token"
    elif sso.same_service(profile.get("store_url", "")):
        authentication = "single_sign_on"
    else:
        authentication = "none"
    summary = publishing.build_summary(target=target, authentication=authentication, profile=profile,
                                       artifact=artifact, inspected=inspected,
                                       build_id=build["id"] if build else None)
    return summary, profile, artifact, path, target, None


@bp.post("/api/publish/review")
def api_publish_review():
    """Step 1: what would be published, and a review token to confirm it (ADR-0009)."""
    payload = request_json()
    summary, profile, _artifact, _path, _target, error = _prepare_publish(payload, "publish_review")
    if error:
        return error
    token = publishing.make_review_token(current_app.config["SECRET_KEY"], summary, current_principal().id)
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
    state, previous = publishing.start_attempt(digest, user_id, profile["id"], artifact["id"])
    if state == "submitted":
        _audit_publish("success", payload, profile, stage="duplicate")
        return jsonify({"state": "submitted", "duplicate": True, "summary": summary, "result": previous})
    if state == "busy":
        return jsonify({"error": "This bundle is being sent right now. Wait a moment.", "reason": "in_progress",
                        "state": "uploading"}), 409
    _audit_publish("success", payload, profile, stage="upload", cartridge=summary["cartridge"]["id"],
                   version=summary["cartridge"]["version"])
    token = profile.get("bearer_token", "")
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
