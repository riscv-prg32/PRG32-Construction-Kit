"""Disk budgets for builds (build_budget.py, build_guard.py --disk-budget; docs/build_sandbox.md).

- All builds together: a build reserves its maximum before it starts, under one lock,
  so builds starting together cannot promise more space than the budget; reservations
  of crashed processes are freed; a full build area answers 507 and writes nothing.
- One build: the guard stops a build whose folder grows beyond its budget.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_build_sandbox import guard, run_build

from prg32_construction_kit import build_budget, build_guard, build_sandbox, packager
from prg32_construction_kit.build_budget import BuildDiskFull, reserve

MB = 1024 * 1024


def fill(folder: Path, megabytes: int) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "old-build.bin").write_bytes(b"0" * megabytes * MB)


def test_a_build_that_fits_reserves_and_frees_its_space(tmp_path):
    fill(tmp_path / "build_old", 2)
    with reserve(tmp_path, 3 * MB, 10 * MB):
        assert len(list((tmp_path / ".budget").glob("*.reservation"))) == 1
    assert list((tmp_path / ".budget").glob("*.reservation")) == []


def test_a_build_that_does_not_fit_is_refused(tmp_path):
    fill(tmp_path / "build_old", 8)
    with pytest.raises(BuildDiskFull):
        with reserve(tmp_path, 3 * MB, 10 * MB):
            pass
    assert list((tmp_path / ".budget").glob("*.reservation")) == []


def test_no_budget_means_no_check(tmp_path):
    fill(tmp_path / "build_old", 3)
    with reserve(tmp_path, 100 * MB, 0):
        pass


def test_running_builds_count_with_their_whole_reservation(tmp_path):
    with reserve(tmp_path, 6 * MB, 10 * MB):
        with pytest.raises(BuildDiskFull):
            with reserve(tmp_path, 6 * MB, 10 * MB):
                pass
    with reserve(tmp_path, 6 * MB, 10 * MB):    # the first one finished
        pass


def test_builds_starting_together_never_overcommit(tmp_path):
    started, refused, lock = [], [], threading.Lock()
    gate = threading.Barrier(8)
    release = threading.Event()

    def build():
        gate.wait()
        try:
            with reserve(tmp_path, 3 * MB, 10 * MB):
                with lock:
                    started.append(1)
                release.wait(10)
        except BuildDiskFull:
            with lock:
                refused.append(1)

    threads = [threading.Thread(target=build) for _ in range(8)]
    for thread in threads:
        thread.start()
    while len(started) + len(refused) < 8 and not (len(started) == 3 and len(refused) == 5):
        threading.Event().wait(0.05)
    assert len(started) == 3 and len(refused) == 5      # 3 x 3 MB fit in 10 MB, a fourth does not
    release.set()
    for thread in threads:
        thread.join()


def test_a_reservation_left_by_a_crashed_process_is_freed(tmp_path):
    script = (f"import sys; sys.path.insert(0, {str(Path(__file__).resolve().parent.parent)!r})\n"
              "from pathlib import Path\nfrom prg32_construction_kit.build_budget import reserve\n"
              f"with reserve(Path({str(tmp_path)!r}), 8 * 1024 * 1024, 10 * 1024 * 1024):\n"
              "    import os; os._exit(0)   # dies while holding it\n")
    subprocess.run([sys.executable, "-c", script], check=True, timeout=60)
    assert len(list((tmp_path / ".budget").glob("*.reservation"))) == 1   # left behind
    with reserve(tmp_path, 8 * MB, 10 * MB):    # its lock died with it: not counted
        pass
    assert list((tmp_path / ".budget").glob("*.reservation")) == []


# --- one build: the guard's folder budget ------------------------------------------------

def test_the_guard_stops_a_build_whose_folder_grows_too_big(tmp_path):
    script = ("import time\nfor n in range(200):\n"
              "    open(f'part{n}.bin', 'wb').write(b'0' * 1024 * 1024)\n    time.sleep(0.02)\n")
    result = guard(tmp_path, sys.executable, "-c", script, disk_budget=5 * MB, watch=str(tmp_path))
    assert result.returncode == build_guard.DISK_EXIT and "grew beyond 5 MB" in result.stderr
    written = build_budget.folder_bytes(tmp_path)
    assert written < 30 * MB      # stopped within a fraction of a second, not after 200 MB


def test_a_build_inside_its_budget_is_not_disturbed(tmp_path):
    result = guard(tmp_path, sys.executable, "-c", "open('small.bin', 'wb').write(b'0' * 1024)",
                   disk_budget=5 * MB, watch=str(tmp_path))
    assert result.returncode == 0


def test_every_build_runs_with_its_folder_watched(tmp_path):
    work = tmp_path / "builds" / "build_1"
    args = build_sandbox.guard_arguments(build_sandbox.SandboxSettings(build_disk_bytes=7 * MB), 10, "guard.py", work)
    assert args[args.index("--disk-budget") + 1] == str(7 * MB) and args[args.index("--watch") + 1] == str(work)


def test_the_real_build_path_reports_a_disk_stop(tmp_path):
    script = ("import time\nfor n in range(200):\n"
              "    open(f'junk{n}.bin', 'wb').write(b'0' * 1024 * 1024)\n    time.sleep(0.02)\n")
    ok, log, _work = run_build(tmp_path, script, mode="rlimit", build_disk_bytes=4 * MB)
    assert not ok and "PRG32_BUILD_MAX_MB" in log


# --- the API --------------------------------------------------------------------------------

def test_a_full_build_area_refuses_with_507_and_writes_nothing(app, client, monkeypatch):
    from prg32_construction_kit.sample_data import default_blocks

    calls = []
    monkeypatch.setattr(packager.subprocess, "run", lambda *a, **k: calls.append(a) or SimpleNamespace(
        returncode=0, stdout="", stderr=""))
    fill(Path(app.config["BUILD_ROOT"]) / "build_old", 3)
    app.config.update(PRG32_BUILD_ROOT_MAX_MB=4, PRG32_BUILD_MAX_MB=2)
    project = client.post("/api/projects", json={"title": "Full", "blocks_json": default_blocks()}).get_json()
    builds = lambda: sorted(p.name for p in Path(app.config["BUILD_ROOT"]).iterdir() if not p.name.startswith("."))  # noqa: E731
    before = builds()
    answer = client.post(f"/api/projects/{project['id']}/package", json={"architectures": ["qemu"]})
    assert answer.status_code == 507 and answer.get_json()["code"] == "build_disk_full"
    assert calls == []
    assert client.get(f"/api/builds?project_id={project['id']}").get_json()["builds"] == []
    assert builds() == before          # no build folder was made
