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
    create_resource,
    delete_resource,
    get_resource,
    list_resources,
    release_connection,
    update_if_unchanged,
    update_resource,
)
from . import project_format, sso
from .auth import Principal, current_principal
from .build_check import builds_available
from .build_slots import BuildServerBusy, build_slot
from .asm_generator import ir_to_asm
from .generator import blocks_to_c, sprite_to_c
from .packager import SUPPORTED_ARCHITECTURES, prepare_package
from .publisher import publish_bundle
from .sample_data import example_catalog
from .source_project import validate_c_source, validate_features

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
    for column, target in LINKS.items():
        if payload.get(column) and column in RESOURCE_COLUMNS[resource]:
            linked = get_resource(target, str(payload[column]))
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
    return {key: value for key, value in result.items() if key not in {"bundle_path", "work_dir"}}


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
    if path == (Path(current_app.config["DATA_DIR"]) / "secret_key").resolve():
        return None  # the key that signs sign-in cookies
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


@bp.get("/publish")
def publish_page():
    return render_template("publish.html")


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
    items = list_resources(resource, filters, viewer_id=viewer_id())
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
    existing = readable(resource, item_id)
    if existing is None:
        return json_error("Not found", 404)
    if request.method == "GET":
        return jsonify(public(resource, existing))
    if not can_write(existing):
        return json_error("This is a shared classroom item: make your own copy to change it", 403)
    if request.method == "DELETE":
        if not delete_resource(resource, item_id):
            return json_error("Not found", 404)
        return jsonify({"deleted": True, "id": item_id})
    item = update_resource(resource, item_id, checked_payload(resource, request_json()))
    if item is None:
        return json_error("Not found", 404)
    return jsonify(public(resource, item))


def _project_children(project_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The sprites and assets of a project that the current user may see.

    They are sorted by name and content, never by id or time, so the archive
    of a project (and of its imported copy) always lists them in the same order.
    """
    def by_content(resource: str) -> list[dict[str, Any]]:
        rows = list_resources(resource, {"project_id": project_id}, viewer_id=viewer_id())
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
        sources["asm"] = ir_to_asm(game_ir)
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
            build_command=current_app.config["PRG32_BUILD_COMMAND"],
            cart_ram_kib=current_app.config["PRG32_CART_RAM_KIB"],
            project_json=project,
            architectures=requested,
            build_timeout=current_app.config["PRG32_BUILD_TIMEOUT"],
        )
    except Exception as exc:
        current_app.logger.exception("Packaging failed for %s", project_id)
        update_resource("builds", build["id"], {"status": "failed", "log": f"Packaging failed: {exc}"})
        return json_error(f"Packaging failed: {exc}", 500)
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
                                 "cart_ram_kib": result["cart_ram_kib"]},
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


@bp.post("/api/publish")
def api_publish():
    payload = request_json()
    profile = readable("publish_profiles", payload.get("profile_id", ""))
    artifact = readable("artifacts", payload.get("bundle_artifact_id", ""))
    if profile is None:
        return json_error("Publish profile not found", 404)
    if artifact is None:
        return json_error("Bundle artifact not found", 404)
    if artifact.get("kind") not in {"store_bundle", "source_bundle"}:
        return json_error("Artifact is not a bundle")
    path = stored_file(artifact.get("path"))
    if path is None:
        return json_error("Bundle file is missing on disk", 404)
    token = profile.get("bearer_token", "")
    if not token and sso.same_service(profile.get("store_url", "")):
        # Single sign-on: publish as the signed-in student with a one-time ticket.
        token = sso.make_ticket(current_principal().email, "api")
    try:
        result = publish_bundle(profile.get("store_url", ""), token, path)
    except Exception as exc:
        return json_error(f"Publish request failed: {exc}", 502)
    return jsonify({"profile": public("publish_profiles", profile), "artifact": public("artifacts", artifact), "result": result})
