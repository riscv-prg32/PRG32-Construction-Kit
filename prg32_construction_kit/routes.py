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
from .build_slots import BuildServerBusy, build_slot
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


def public(resource: str, item: dict[str, Any] | None) -> dict[str, Any] | None:
    """Hide secrets before an item leaves the server (bearer tokens are write-only)."""
    if item is None or resource != "publish_profiles":
        return item
    shown = {key: value for key, value in item.items() if key != "bearer_token"}
    shown["has_token"] = bool(item.get("bearer_token"))
    return shown


def stored_file(path_value: str | None) -> Path | None:
    """Return an artifact file only if it lives inside the kit's own data folders."""
    if not path_value:
        return None
    path = Path(path_value).resolve()
    roots = [current_app.config[key] for key in ("DATA_DIR", "BUILD_ROOT", "ARTIFACT_ROOT")]
    if not any(path.is_relative_to(Path(root).resolve()) for root in roots):
        return None
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
            },
        }
    )


@bp.route("/api/<resource>", methods=["GET"])
def api_list(resource: str):
    if resource not in RESOURCE_COLUMNS:
        return json_error(f"Unknown resource: {resource}", 404)
    filters = {key: value for key, value in request.args.items() if key in {"project_id", "sprite_id", "kind", "status"}}
    return jsonify({resource: [public(resource, item) for item in list_resources(resource, filters)]})


@bp.route("/api/<resource>", methods=["POST"])
def api_create(resource: str):
    if resource not in RESOURCE_COLUMNS:
        return json_error(f"Unknown resource: {resource}", 404)
    item = create_resource(resource, request_json())
    return jsonify(public(resource, item)), 201


@bp.route("/api/<resource>/<item_id>", methods=["GET", "PUT", "DELETE"])
def api_item(resource: str, item_id: str):
    if resource not in RESOURCE_COLUMNS:
        return json_error(f"Unknown resource: {resource}", 404)
    if request.method == "GET":
        item = get_resource(resource, item_id)
        if item is None:
            return json_error("Not found", 404)
        return jsonify(public(resource, item))
    if request.method == "DELETE":
        if not delete_resource(resource, item_id):
            return json_error("Not found", 404)
        return jsonify({"deleted": True, "id": item_id})
    item = update_resource(resource, item_id, request_json())
    if item is None:
        return json_error("Not found", 404)
    return jsonify(public(resource, item))


@bp.post("/api/projects/import")
def api_import_project():
    payload: dict[str, Any]
    if "file" in request.files:
        try:
            payload = json.loads(request.files["file"].read().decode("utf-8"))
        except Exception as exc:
            return json_error(f"Could not parse JSON import: {exc}")
    else:
        payload = request_json()
    if isinstance(payload, dict) and "project" in payload:
        payload = payload["project"]
    if not isinstance(payload, dict):
        return json_error("Import file must contain a JSON object with a project")
    item = create_resource(
        "projects",
        {
            "title": payload.get("title", "Imported PRG32 Game"),
            "description": payload.get("description", "Imported from JSON."),
            "author": payload.get("author", "Student"),
            "tags": payload.get("tags", ["imported"]),
            "blocks_json": payload.get("blocks_json") or payload.get("blocks") or {},
            "game_json": payload.get("game_json") or payload.get("game_ir") or {},
        },
    )
    return jsonify(item), 201


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
            return jsonify(create_resource("projects", item["project"])), 201
    return json_error("Example not found", 404)


@bp.get("/api/projects/<project_id>/export")
def api_export_project(project_id: str):
    project = get_resource("projects", project_id)
    if project is None:
        return json_error("Project not found", 404)
    body = json.dumps({"abi": "prg32-construction-kit-project-1.0", "project": project}, indent=2)
    return Response(
        body,
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{project_id}.blocks.json"'},
    )


def _generate_project(project_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None, tuple[Response, int] | None]:
    project = get_resource("projects", project_id)
    if project is None:
        return None, None, None, json_error("Project not found", 404)
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


@bp.post("/api/projects/<project_id>/convert")
def api_convert_project(project_id: str):
    project, game_ir, c_source, error = _generate_project(project_id)
    if error:
        return error
    assert project and game_ir is not None and c_source is not None
    artifact = create_resource(
        "artifacts",
        {
            "project_id": project_id,
            "kind": "c_source",
            "name": f"{project['title']} generated C",
            "content_type": "text/x-csrc",
            "text_content": c_source,
            "metadata": {"entry_prefix": game_ir.get("entry_prefix"), "warnings": game_ir.get("warnings", [])},
        },
    )
    return jsonify({"project": get_resource("projects", project_id), "game_ir": game_ir, "c_source": c_source, "artifact": artifact})


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
            return _run_package_build(project_id, project, game_ir, c_source, requested)
    except BuildServerBusy as exc:
        response, status = json_error(str(exc), 503)
        response.headers["Retry-After"] = "10"
        return response, status


def _run_package_build(project_id: str, project: dict[str, Any], game_ir: dict[str, Any], c_source: str,
                       requested: list[str] | None):
    c_artifact = create_resource(
        "artifacts",
        {
            "project_id": project_id,
            "kind": "c_source",
            "name": f"{project['title']} generated C",
            "content_type": "text/x-csrc",
            "text_content": c_source,
            "metadata": {"entry_prefix": game_ir.get("entry_prefix"), "source": "package"},
        },
    )
    build = create_resource("builds", {"project_id": project_id, "status": "running", "c_artifact_id": c_artifact["id"],
                                       "metadata": {"project_updated_at": project.get("updated_at")}})
    release_connection()
    try:
        result = prepare_package(
            data_dir=current_app.config["DATA_DIR"],
            build_root=current_app.config["BUILD_ROOT"],
            project=project,
            game_ir=game_ir,
            c_source=c_source,
            build_id=build["id"],
            build_command=current_app.config["PRG32_BUILD_COMMAND"],
            cart_ram_kib=current_app.config["PRG32_CART_RAM_KIB"],
            project_json=project,
            architectures=requested,
        )
    except Exception as exc:
        current_app.logger.exception("Packaging failed for %s", project_id)
        update_resource("builds", build["id"], {"status": "failed", "log": f"Packaging failed: {exc}"})
        return json_error(f"Packaging failed: {exc}", 500)
    bundle_artifact = create_resource(
        "artifacts",
        {
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
        },
    )
    cartridge_artifacts = []
    for architecture in result["architectures"]:
        cartridge_path = Path(result["work_dir"]) / architecture["file"]
        cartridge_artifacts.append(
            create_resource(
                "artifacts",
                {
                    "project_id": project_id,
                    "kind": "prg32_cartridge",
                    "name": architecture["file"],
                    "content_type": "application/vnd.prg32.cartridge",
                    "path": str(cartridge_path),
                    "metadata": {"architecture": architecture["id"], "portable": True, "build_id": build["id"],
                                 "cart_ram_kib": result["cart_ram_kib"]},
                },
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
            },
        },
    )
    return jsonify({"build": build, "c_artifact": c_artifact, "bundle_artifact": bundle_artifact, "cartridge_artifacts": cartridge_artifacts, "result": result})


@bp.post("/api/sprites/<sprite_id>/convert")
def api_convert_sprite(sprite_id: str):
    sprite = get_resource("sprites", sprite_id)
    if sprite is None:
        return json_error("Sprite not found", 404)
    c_source = sprite_to_c(sprite)
    artifact = create_resource(
        "artifacts",
        {
            "sprite_id": sprite_id,
            "project_id": sprite.get("project_id"),
            "kind": "sprite_c_source",
            "name": f"{sprite['name']} sprite C",
            "content_type": "text/x-csrc",
            "text_content": c_source,
            "metadata": {"width": sprite.get("width"), "height": sprite.get("height")},
        },
    )
    return jsonify({"sprite": sprite, "c_source": c_source, "artifact": artifact})


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
    uploaded.save(path)
    artifact = create_resource(
        "artifacts",
        {
            "project_id": request.form.get("project_id") or None,
            "kind": request.form.get("kind") or "upload",
            "name": safe_name,
            "content_type": uploaded.mimetype or "application/octet-stream",
            "path": str(path),
            "metadata": {"uploaded": True},
        },
    )
    return jsonify(artifact), 201


@bp.get("/api/artifacts/<artifact_id>/download")
def api_download_artifact(artifact_id: str):
    artifact = get_resource("artifacts", artifact_id)
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
    profile = get_resource("publish_profiles", payload.get("profile_id", ""))
    artifact = get_resource("artifacts", payload.get("bundle_artifact_id", ""))
    if profile is None:
        return json_error("Publish profile not found", 404)
    if artifact is None:
        return json_error("Bundle artifact not found", 404)
    if artifact.get("kind") not in {"store_bundle", "source_bundle"}:
        return json_error("Artifact is not a bundle")
    path = stored_file(artifact.get("path"))
    if path is None:
        return json_error("Bundle file is missing on disk", 404)
    try:
        result = publish_bundle(profile.get("store_url", ""), profile.get("bearer_token", ""), path)
    except Exception as exc:
        return json_error(f"Publish request failed: {exc}", 502)
    return jsonify({"profile": public("publish_profiles", profile), "artifact": artifact, "result": result})
