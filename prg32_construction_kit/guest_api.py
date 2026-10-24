"""What the server does for visitors without an account (ADR-0023, docs/guest_mode.md).

A guest's games, sprites and sounds live in their own browser (IndexedDB, guest_store.js);
the server keeps none of them. A few things only the server can do, so it does them here
**without storing anything**: the browser sends what it needs, gets the answer back, and
nothing of the request is kept or logged.

    GET  /api/guest/examples/<slug>   an example game, to copy into the browser
    POST /api/guest/convert           {project, audio_studio?, source_language?} -> game IR, C, assembly
    POST /api/guest/audio             {document?} -> the checked AudioStudio document and its sound ids
    POST /api/guest/audio/preview     {document, muted?} -> the AUD0 block to listen to
    POST /api/guest/sprites/convert   {sprite} -> the sprite as C
    POST /api/guest/convert_to        {project, language, audio_studio?} -> the game as C or assembly (one way)
    POST /api/guest/run               {project, audio_studio?} -> a cartridge for the simulator (run_build.py)

The generated code comes from the same validators and generators as for an account
(routes.generate_sources), so it is identical for the same blocks. Building a cartridge,
publishing, classes and samples need an account. Each address may make a limited number of
these requests per hour (security.LIMITS["guest_api"]).
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, jsonify, request

from . import audio_studio, security
from .audio_studio import AudioStudioError

bp = Blueprint("guest_api", __name__)

# Paths a visitor without an account may use (auth.guard_request), when the kit allows guests.
GUEST_API_PREFIX = "/api/guest/"


def _refused(message: str, status: int = 400, **extra: Any):
    return jsonify({"error": message, **extra}), status


@bp.before_request
def _throttle():
    try:
        security.check_and_hit("guest_api", security.client_address())
    except security.Throttled as error:
        return _refused("Too many requests: wait a little and try again.", 429, retry_after=error.retry_after)
    return None


def _payload() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _document(value: Any) -> dict[str, Any]:
    """A guest's AudioStudio document, checked; samples need an account (their sound is a server file)."""
    document = audio_studio.validate_document(value) if value is not None else audio_studio.default_document()
    if document.get("samples"):
        raise AudioStudioError("Recorded samples need an account: sign in to use them.")
    return document


@bp.get("/api/guest/examples/<slug>")
def example(slug: str):
    from .sample_data import example_catalog

    for item in example_catalog():
        if item["slug"] == slug:
            return jsonify({"project": item["project"]})
    return _refused("Example not found", 404)


@bp.post("/api/guest/convert")
def convert():
    from .asm_generator import ir_to_asm
    from .py_generator import from_blocks, ir_to_python
    from .routes import SOURCE_LANGUAGES, generate_sources

    payload = _payload()
    given = payload.get("project")
    if not isinstance(given, dict):
        return _refused("send {\"project\": {title, blocks_json, game_json}}")
    project = {"title": str(given.get("title") or "Untitled game")[:200],
               "blocks_json": given.get("blocks_json") or {}, "game_json": given.get("game_json") or {}}
    try:
        project["audio_studio"] = _document(payload["audio_studio"]) if payload.get("audio_studio") else None
    except (ValueError, AudioStudioError) as error:
        return _refused(str(error))
    game_ir, c_source, message = generate_sources(project)
    if message is not None:
        return _refused(message)
    assert game_ir is not None and c_source is not None
    handwritten = game_ir.get("source_mode") == "asm"
    language = "asm" if handwritten else payload.get("source_language", "c")
    if language not in SOURCE_LANGUAGES:
        return _refused("source_language must be one of: " + ", ".join(SOURCE_LANGUAGES))
    if language != "c" and game_ir.get("source_mode") == "c":
        return _refused("Assembly is generated from Blocks. An Advanced C project compiles the C you wrote.")
    body: dict[str, Any] = {"game_ir": game_ir, "source_language": language}
    if language in ("c", "both"):
        body["c_source"] = c_source
    if language in ("asm", "both"):
        body["asm_source"] = game_ir["source_asm"] if handwritten else ir_to_asm(game_ir)
    if from_blocks(game_ir):
        body["python_source"] = ir_to_python(game_ir)   # to read beside game.c; never built
    return jsonify(body)


@bp.post("/api/guest/audio")
def audio():
    try:
        document = _document(_payload().get("document"))
    except (ValueError, AudioStudioError) as error:
        return _refused(str(error))
    return jsonify({"document": document, "missing_samples": [],
                    "ids": {"effects": {effect["name"]: {"instrument": audio_studio.FIRST_EFFECT_INSTRUMENT + index,
                                                         "voice": effect["voice"], "note": effect["note"]}
                                        for index, effect in enumerate(document["effects"])},
                            "soundtracks": {track["name"]: index for index, track in enumerate(document["soundtracks"])}}})


@bp.post("/api/guest/audio/preview")
def audio_preview():
    payload = _payload()
    muted = payload.get("muted") or []
    if not isinstance(muted, list) or any(not isinstance(v, int) or not 0 <= v < 8 for v in muted):
        return _refused("muted must be a list of voices 0..7")
    try:
        document = _document(payload.get("document"))
    except (ValueError, AudioStudioError) as error:
        return _refused(str(error))
    block = audio_studio.pack_document(document, {}, set(muted))
    return Response(block, mimetype="application/octet-stream", headers={"Cache-Control": "no-store"})


@bp.post("/api/guest/convert_to")
def convert_to():
    """A guest's Blocks game as C or assembly (one way, ADR-0024); the browser stores the answer."""
    from .sample_data import blocks_as_code

    payload = _payload()
    given = payload.get("project")
    if not isinstance(given, dict) or payload.get("language") not in ("c", "asm"):
        return _refused("send {\"project\": {title, blocks_json}, \"language\": \"c\" | \"asm\"}")
    project = {"title": str(given.get("title") or "Untitled game")[:200], "blocks_json": given.get("blocks_json") or {}}
    try:
        project["audio_studio"] = _document(payload["audio_studio"]) if payload.get("audio_studio") else None
        return jsonify({"game_json": blocks_as_code(project, payload["language"])})
    except (ValueError, AudioStudioError) as error:
        return _refused(str(error))
    except Exception as error:  # noqa: BLE001 - blocks that do not generate cannot be converted
        return _refused(f"These blocks cannot be converted yet: {error}")


@bp.post("/api/guest/run")
def run():
    """Build a guest's game for the IDE's simulator (run_build.py): the cartridge comes back, nothing is kept."""
    from . import run_build

    try:
        security.check_and_hit("guest_run", security.client_address())
    except security.Throttled as error:
        return _refused("You have run many games in the last hour: wait a little, or sign in.", 429,
                        retry_after=error.retry_after)
    payload = _payload()
    given = payload.get("project")
    if not isinstance(given, dict):
        return _refused("send {\"project\": {title, blocks_json, game_json}}")
    project = {"id": None, "title": str(given.get("title") or "Untitled game")[:200],
               "blocks_json": given.get("blocks_json") or {}, "game_json": given.get("game_json") or {}}
    try:
        document = _document(payload["audio_studio"]) if payload.get("audio_studio") else None
        project["audio_studio"] = document
        audio = (audio_studio.pack_document(document, {}), document) if document else None
        return jsonify(run_build.run(project, audio))
    except run_build.RunRefused as refused:
        return _refused(str(refused), refused.status, code=refused.code)
    except (ValueError, AudioStudioError) as error:
        return _refused(str(error))


@bp.post("/api/guest/sprites/convert")
def sprite_convert():
    from .generator import sprite_to_c

    sprite = _payload().get("sprite")
    if not isinstance(sprite, dict):
        return _refused("send {\"sprite\": {name, width, height, pixels}}")
    try:
        return jsonify({"c_source": sprite_to_c(sprite)})
    except (ValueError, TypeError, KeyError) as error:
        return _refused(f"This sprite cannot be converted: {error}")
