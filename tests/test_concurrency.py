"""Many students (or one student in several browser windows) building at once."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from prg32_construction_kit.build_slots import BuildServerBusy, build_slot
from prg32_construction_kit.db import get_resource, update_if_unchanged
from prg32_construction_kit.sample_data import default_blocks


class FakeCompiler:
    """Pretends to be the PRG32 toolchain and remembers how many ran at once."""

    def __init__(self, seconds: float = 0.05):
        self.seconds = seconds
        self.running = 0
        self.most_at_once = 0
        self.lock = threading.Lock()

    def __call__(self, command, **_kwargs):
        with self.lock:
            self.running += 1
            self.most_at_once = max(self.most_at_once, self.running)
        try:
            time.sleep(self.seconds)
            out_path = command[command.index("--out") + 1]
            # Each cartridge holds its own output path, so a mix-up would show.
            Path(out_path).write_bytes(out_path.encode("utf-8"))
            return SimpleNamespace(returncode=0, stdout="built\n", stderr="")
        finally:
            with self.lock:
                self.running -= 1


def test_parallel_builds_from_many_browsers_stay_separate(app, monkeypatch):
    app.config["PRG32_MAX_PARALLEL_BUILDS"] = 3
    compiler = FakeCompiler()
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", compiler)
    setup = app.test_client()
    projects = [
        setup.post("/api/projects", json={"title": f"Game {n}", "blocks_json": default_blocks()}).get_json()
        for n in range(4)
    ]
    # Twelve requests: four students, each building from three browser windows.
    jobs = [projects[n % 4] for n in range(12)]

    def build(project):
        client = app.test_client()  # one client per "browser"
        response = client.post(f"/api/projects/{project['id']}/package",
                               json={"architectures": ["qemu"], "expected_blocks_json": project["blocks_json"]})
        assert response.status_code == 200, response.get_json()
        cartridge = response.get_json()["cartridge_artifacts"][0]
        download = client.get(f"/api/artifacts/{cartridge['id']}/download")
        return project["id"], response.get_json()["build"], cartridge, download.data

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(build, jobs))

    build_ids = {item[1]["id"] for item in results}
    assert len(build_ids) == 12
    assert len({item[2]["path"] for item in results}) == 12
    for project_id, build, cartridge, data in results:
        assert build["project_id"] == project_id
        assert build["status"] == "ready"
        assert data == cartridge["path"].encode("utf-8")
        assert build["id"] in cartridge["path"]
    assert compiler.most_at_once <= 3


def test_builds_wait_for_a_free_slot_then_report_busy(app, client, monkeypatch):
    app.config.update(PRG32_MAX_PARALLEL_BUILDS=1, PRG32_BUILD_QUEUE_TIMEOUT=0.3)
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", FakeCompiler())
    project = client.post("/api/projects", json={"title": "Busy", "blocks_json": default_blocks()}).get_json()
    with build_slot(app.config["BUILD_ROOT"] / ".slots", 1, 0):
        response = client.post(f"/api/projects/{project['id']}/package", json={})
    assert response.status_code == 503
    assert response.headers["Retry-After"]
    assert "busy" in response.get_json()["error"]
    # Nothing half-made is left behind, and the next try works.
    assert client.get(f"/api/builds?project_id={project['id']}").get_json()["builds"] == []
    assert client.post(f"/api/projects/{project['id']}/package", json={}).status_code == 200


def test_build_slots_are_shared_between_threads(tmp_path):
    slots = tmp_path / "slots"
    with build_slot(slots, 2, 0) as first:
        with build_slot(slots, 2, 0) as second:
            assert {first, second} == {0, 1}
            try:
                with build_slot(slots, 2, 0):
                    raise AssertionError("a third build should not get a slot")
            except BuildServerBusy:
                pass
    with build_slot(slots, 1, 0) as again:
        assert again == 0


def test_build_notices_a_save_from_another_window(client, monkeypatch):
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", FakeCompiler(0))
    project = client.post("/api/projects", json={"title": "Two Windows", "blocks_json": default_blocks()}).get_json()
    mine = client.put(f"/api/projects/{project['id']}", json={"blocks_json": default_blocks()}).get_json()
    client.put(f"/api/projects/{project['id']}", json={"blocks_json": {"blocks": {"blocks": []}}})

    response = client.post(f"/api/projects/{project['id']}/package",
                           json={"expected_blocks_json": mine["blocks_json"]})
    assert response.status_code == 409
    assert "another browser window" in response.get_json()["error"]


def test_build_notices_changed_advanced_c(client, monkeypatch):
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", FakeCompiler(0))
    source = ("#include \"prg32.h\"\nvoid c_game_init(void) {}\nvoid c_game_update(void) {}\n"
              "void c_game_draw(void) {}\n")
    project = client.post("/api/projects", json={"title": "C Game", "game_json": {"source_mode": "c", "source_c": source}}).get_json()
    ok = client.post(f"/api/projects/{project['id']}/package", json={"expected_source_c": source})
    assert ok.status_code == 200
    stale = client.post(f"/api/projects/{project['id']}/package", json={"expected_source_c": source + "// old\n"})
    assert stale.status_code == 409


def test_generated_ir_never_overwrites_a_newer_save(app, client):
    project = client.post("/api/projects", json={"title": "Race", "blocks_json": default_blocks()}).get_json()
    # Another window switches the project to Advanced C after we read it.
    newer = {"source_mode": "c", "source_c": "void race_init(void) {}"}
    client.put(f"/api/projects/{project['id']}", json={"game_json": newer})
    with app.app_context():
        stored = update_if_unchanged("projects", project["id"],
                                     {"blocks_json": project["blocks_json"], "game_json": project["game_json"]},
                                     {"game_json": {"abi": "old"}})
        assert stored is False
        assert get_resource("projects", project["id"])["game_json"] == newer
