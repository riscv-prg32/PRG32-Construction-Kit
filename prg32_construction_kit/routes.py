from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, render_template, request, send_file, send_from_directory

from .db import (
    RESOURCE_COLUMNS,
    create_resource,
    delete_resource,
    get_resource,
    list_resources,
    update_resource,
)
from .generator import blocks_to_c, sprite_to_c
from .packager import prepare_package
from .publisher import publish_bundle

bp = Blueprint("kit", __name__)


def json_error(message: str, status: int = 400) -> tuple[Response, int]:
    return jsonify({"error": message}), status


def request_json() -> dict[str, Any]:
    if request.is_json:
        return request.get_json(silent=True) or {}
    if request.form:
        return dict(request.form)
    return {}


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
    return jsonify({resource: list_resources(resource, filters)})


@bp.route("/api/<resource>", methods=["POST"])
def api_create(resource: str):
    if resource not in RESOURCE_COLUMNS:
        return json_error(f"Unknown resource: {resource}", 404)
    item = create_resource(resource, request_json())
    return jsonify(item), 201


@bp.route("/api/<resource>/<item_id>", methods=["GET", "PUT", "DELETE"])
def api_item(resource: str, item_id: str):
    if resource not in RESOURCE_COLUMNS:
        return json_error(f"Unknown resource: {resource}", 404)
    if request.method == "GET":
        item = get_resource(resource, item_id)
        if item is None:
            return json_error("Not found", 404)
        return jsonify(item)
    if request.method == "DELETE":
        if not delete_resource(resource, item_id):
            return json_error("Not found", 404)
        return jsonify({"deleted": True, "id": item_id})
    item = update_resource(resource, item_id, request_json())
    if item is None:
        return json_error("Not found", 404)
    return jsonify(item)


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
    if "project" in payload:
        payload = payload["project"]
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


@bp.get("/api/projects/<project_id>/export")
def api_export_project(project_id: str):
    project = get_resource("projects", project_id)
    if project is None:
        return json_error("Project not found", 404)
    body = json.dumps({"abi": "prg32-construction-kit-project-1.0", "project": project}, indent=2)
    return Response(
        body,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={project_id}.blocks.json"},
    )


def _generate_project(project_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None, tuple[Response, int] | None]:
    project = get_resource("projects", project_id)
    if project is None:
        return None, None, None, json_error("Project not found", 404)
    try:
        game_ir, c_source = blocks_to_c(project.get("blocks_json") or {}, project)
    except Exception as exc:
        return project, None, None, json_error(f"Conversion failed: {exc}")
    update_resource("projects", project_id, {"game_json": game_ir})
    return project, game_ir, c_source, None


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
    return jsonify({"project": update_resource("projects", project_id, {"game_json": game_ir}), "game_ir": game_ir, "c_source": c_source, "artifact": artifact})


@bp.post("/api/projects/<project_id>/package")
def api_package_project(project_id: str):
    project, game_ir, c_source, error = _generate_project(project_id)
    if error:
        return error
    assert project and game_ir is not None and c_source is not None
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
    build = create_resource("builds", {"project_id": project_id, "status": "running", "c_artifact_id": c_artifact["id"], "metadata": {}})
    result = prepare_package(
        data_dir=current_app.config["DATA_DIR"],
        project=project,
        game_ir=game_ir,
        c_source=c_source,
        build_id=build["id"],
        build_command=current_app.config["PRG32_BUILD_COMMAND"],
        project_json=project,
    )
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
                "publishable": result["publishable"],
                "work_dir": result["work_dir"],
            },
        },
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
                "publishable": result["publishable"],
            },
        },
    )
    return jsonify({"build": build, "c_artifact": c_artifact, "bundle_artifact": bundle_artifact, "result": result})


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
    safe_name = "".join(ch if ch.isalnum() or ch in ".-_" else "_" for ch in uploaded.filename)
    artifact_dir = current_app.config["ARTIFACT_ROOT"] / "uploads"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / safe_name
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
    path = artifact.get("path")
    if path and Path(path).exists():
        return send_file(Path(path), mimetype=artifact.get("content_type") or None, as_attachment=True, download_name=artifact.get("name") or Path(path).name)
    text = artifact.get("text_content", "")
    return Response(
        text,
        mimetype=artifact.get("content_type") or "text/plain",
        headers={"Content-Disposition": f"attachment; filename={artifact.get('name', artifact_id)}"},
    )


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
    path = Path(artifact.get("path") or "")
    if not path.exists():
        return json_error("Bundle file is missing on disk", 404)
    try:
        result = publish_bundle(profile.get("store_url", ""), profile.get("bearer_token", ""), path)
    except Exception as exc:
        return json_error(f"Publish request failed: {exc}", 502)
    return jsonify({"profile": {k: v for k, v in profile.items() if k != "bearer_token"}, "artifact": artifact, "result": result})
