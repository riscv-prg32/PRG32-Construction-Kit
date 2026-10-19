"""Put the committed Pong debug fixture (tests/fixtures/debug) into a kit, as a compile would.

Used by the source-debugger tests, which then run without a RISC-V toolchain: the
cartridge, its debug map and its block map are the files tools/build_debug_fixtures.py
made with the real one.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from prg32_construction_kit.source_maps import build_source_map

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "debug"
PONG = ROOT / "examples" / "games" / "pong.json"


def pong_project() -> dict:
    data = json.loads(PONG.read_text(encoding="utf-8"))
    return data.get("project", data)


def seed_pong(client, build_root: Path, *, with_maps: bool = True) -> dict:
    """Create the Pong project, its build and its cartridge artifacts; return their ids."""
    project = pong_project()
    created = client.post("/api/projects", json={"title": project["title"], "blocks_json": project["blocks_json"],
                                                 "game_json": project.get("game_json", {})}).get_json()
    _, c_source, _ = build_source_map(project["blocks_json"], created, "c")
    work = Path(build_root) / ("seed-" + created["id"])
    (work / "debug").mkdir(parents=True)
    shutil.copyfile(FIXTURES / "pong.prg32", work / "pong-qemu.prg32")
    (work / "project.blocks.json").write_text(json.dumps(created), encoding="utf-8")

    def artifact(**fields):
        response = client.post("/api/artifacts", json={"project_id": created["id"], **fields})
        assert response.status_code == 201, response.get_json()
        return response.get_json()

    c_artifact = artifact(kind="c_source", name="Pong generated C", content_type="text/x-csrc", text_content=c_source)
    bundle = artifact(kind="source_bundle", name="bundle", metadata={"work_dir": str(work)})
    build = client.post("/api/builds", json={"project_id": created["id"], "status": "ready",
                                             "c_artifact_id": c_artifact["id"], "bundle_artifact_id": bundle["id"],
                                             "metadata": {"built_from": "c"}}).get_json()
    metadata = {"architecture": "qemu", "portable": True, "build_id": build["id"], "built_from": "c"}
    if with_maps:
        shutil.copyfile(FIXTURES / "pong.map.json", work / "debug" / "qemu.map.json")
        shutil.copyfile(FIXTURES / "pong.source_map.json", work / "debug" / "source_map.json")
        debug_map = artifact(kind="debug_map", name="qemu.map.json", content_type="application/json",
                             path=str(work / "debug" / "qemu.map.json"))
        source_map = artifact(kind="source_map", name="source_map.json", content_type="application/json",
                              path=str(work / "debug" / "source_map.json"))
        metadata.update(debug_map_artifact_id=debug_map["id"], source_map_artifact_id=source_map["id"])
    cartridge = artifact(kind="prg32_cartridge", name="pong-qemu.prg32", content_type="application/vnd.prg32.cartridge",
                         path=str(work / "pong-qemu.prg32"), metadata=metadata)
    return {"project": created["id"], "build": build["id"], "cartridge": cartridge["id"]}
