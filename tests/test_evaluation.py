"""Evaluate: the PRG32 performance protocol, its dataset, statistics, exports and charts (EVAL-01).

The targets are tests/fake_prg32.py, whose performance broker reports numbers made from the run
number (FakePrg32.frame_us), so every statistic here can be checked by hand. The cartridge is
made through the real package API from the protocol's own source, with a stand-in compiler.
"""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from fake_prg32 import FakePrg32, cartridge
from prg32_construction_kit import charts, deploy, evaluation

ROOT = Path(__file__).resolve().parent.parent
STUDENT_PASSWORD = "student-password-1"


@pytest.fixture()
def device():
    fake = FakePrg32()
    yield fake
    fake.stop()


@pytest.fixture(autouse=True)
def quick(app, monkeypatch):
    app.config["DEPLOY_INLINE"] = True
    monkeypatch.setattr(deploy, "POLL_SECONDS", 0.05)
    monkeypatch.setattr(evaluation, "RUN_TIMEOUT", 2.0)


def evaluation_cartridge(client, monkeypatch, source: str | None = None, name: str = "PRG32 Evaluation") -> dict:
    """The protocol's project, packaged with a stand-in compiler: its esp32c6 and qemu cartridges."""
    def fake_builder(command, **_kwargs):
        Path(command[command.index("--out") + 1]).write_bytes(cartridge(name))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder)
    monkeypatch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: True)
    the_protocol = client.get("/api/evaluation/protocol").get_json()
    project = client.post("/api/projects", json={"title": the_protocol["cartridge"]["title"], "game_json": {
        "source_mode": "c", "source_c": source or the_protocol["cartridge"]["source_text"],
        "required_features": the_protocol["cartridge"]["required_features"]}}).get_json()
    answer = client.post(f"/api/projects/{project['id']}/package", json={}).get_json()
    return {"project": project, **{item["metadata"]["architecture"]: item for item in answer["cartridge_artifacts"]}}


def register(client, fake, kind="prg32", name="Class console") -> dict:
    return client.post("/api/admin/deploy_targets", json={"name": name, "kind": kind, "address": fake.url}).get_json()


def evaluate(client, target, artifact, slot="cart2", **extra):
    probe = client.post(f"/api/deploy/targets/{target['id']}/probe", json={"artifact_id": artifact["id"]}).get_json()
    seen = next(item for item in probe["slots"] if item["slot"] == slot)
    payload = {"artifact_id": artifact["id"], "target": target["id"], "slot": slot, "confirm": True,
               "expect": {"fingerprint": probe["fingerprint"], "slot_content": deploy.slot_content(seen)},
               "repetitions": 3, "warm_up": 1, **extra}
    return client.post("/api/evaluations", json=payload)


# --- the protocol is one fixed, hashed thing --------------------------------------------------

def test_the_protocol_names_its_cartridge_source_by_hash_and_its_cases_match_the_source():
    the_protocol = evaluation.protocol()
    source = (ROOT / the_protocol["cartridge"]["source"]).read_text()
    assert hashlib.sha256(source.encode()).hexdigest() == the_protocol["cartridge"]["source_sha256"]
    in_source = re.findall(r'case \d: return "([a-z-]+)";|default: return "([a-z-]+)";', source)
    names = [first or second for first, second in in_source][:5]
    assert names == [case["name"] for case in the_protocol["cartridge"]["cases"]]
    assert f"#define FRAMES {the_protocol['cartridge']['cases'][0]['frames']}u" in source
    assert {target for target in ("prg32", "prg32qt", "qemu")} <= set(the_protocol["timing_source"])
    assert "not the times of a PRG32 console" in the_protocol["caveat"]
    page = (ROOT / "templates" / "evaluate.html").read_text()
    assert re.findall(r'<option value="([a-z0-9_]+)">', page) == [metric["name"] for metric in the_protocol["metrics"]]


# --- a run, its dataset and its numbers ---------------------------------------------------------

def test_warm_up_and_measured_runs_become_rows_and_the_statistics_are_over_measured_runs(client, monkeypatch, device):
    built = evaluation_cartridge(client, monkeypatch)
    target = register(client, device)
    answer = evaluate(client, target, built["esp32c6"])
    assert answer.status_code == 202, answer.get_json()
    item = client.get(f"/api/evaluations/{answer.get_json()['id']}").get_json()
    assert item["status"] == "complete" and item["physical_device"] is True
    assert [run["role"] for run in item["result"]["runs"]] == ["warm-up", "measured", "measured", "measured"]
    assert device.runs == 4 and device.uploads == [("cart2", built["esp32c6"]["metadata"]["bytes"])]
    clear = item["statistics"]["cases"]["clear-fill"]
    assert clear["values"] == [10020.0, 10030.0, 10040.0]            # runs 2-4; run 1 was the warm-up
    assert clear["n"] == 3 and clear["mean"] == pytest.approx(10030) and clear["sd"] == pytest.approx(10)
    half = 4.303 * 10 / math.sqrt(3)
    assert clear["ci95_low"] == pytest.approx(10030 - half) and clear["ci95_high"] == pytest.approx(10030 + half)
    assert clear["median"] == 10030 and clear["min"] == 10020 and clear["max"] == 10040
    dataset = client.get(f"/api/evaluations/{item['id']}/dataset.json").get_json()
    assert dataset["format"] == "prg32-evaluation-dataset-1" and len(dataset["rows"]) == 4 * 5 * 11
    assert dataset["about"]["cartridge_sha256"] == built["esp32c6"]["metadata"]["sha256"]
    assert dataset["about"]["evidence"] == "physical device" and dataset["about"]["firmware_version"] == "679dfb5"
    assert dataset["protocol"]["timing_source"].startswith("the console's microsecond timer")
    warm = [row for row in dataset["rows"] if row["role"] == "warm-up"]
    assert len(warm) == 55 and all(row["repetition"] == 1 for row in warm)


def test_the_statistics_are_the_textbook_ones():
    assert evaluation.describe([]) == {key: (0 if key == "n" else None) for key in evaluation.describe([])}
    single = evaluation.describe([5.0])
    assert single["n"] == 1 and single["mean"] == 5 and single["sd"] is None and single["ci95_low"] is None
    many = evaluation.describe([float(value) for value in range(1, 41)])
    assert many["ci95_high"] - many["mean"] == pytest.approx(1.960 * many["sem"])     # beyond the t table


def test_the_csv_has_every_row_with_dots_in_any_language(client, monkeypatch, device):
    built = evaluation_cartridge(client, monkeypatch)
    item = evaluate(client, register(client, device), built["esp32c6"]).get_json()
    english = client.get(f"/api/evaluations/{item['id']}/dataset.csv").data
    client.set_cookie("prg32_locale", "de")
    assert client.get(f"/api/evaluations/{item['id']}/dataset.csv").data == english
    lines = english.decode().splitlines()
    assert lines[0].split(",") == evaluation.protocol()["dataset"]["csv_columns"] and len(lines) == 1 + 4 * 5 * 11
    fps = next(line for line in lines[1:] if ",measured," in line and ",fps_mean," in line)
    assert re.search(r",\d+\.\d+,Hz$", fps)


def test_a_run_without_a_result_is_kept_as_failed_and_left_out_of_the_statistics(client, monkeypatch, device):
    built = evaluation_cartridge(client, monkeypatch)
    device.silent_runs = {3}                                        # the second measured run never finishes
    item = evaluate(client, register(client, device), built["esp32c6"]).get_json()
    item = client.get(f"/api/evaluations/{item['id']}").get_json()
    assert item["status"] == "complete"
    assert [run["status"] for run in item["result"]["runs"]] == ["ok", "ok", "failed", "ok"]
    assert item["statistics"]["cases"]["clear-fill"]["values"] == [10020.0, 10040.0]
    dataset = client.get(f"/api/evaluations/{item['id']}/dataset.json").get_json()
    assert [row for row in dataset["rows"] if row["role"] == "failed"] == [
        {"repetition": 3, "role": "failed", "run_id": "", "case": "", "metric": "", "value": None, "unit": ""}]
    assert any("Run 3 gave no result" in line["text"] for line in item["log"])


def test_inputs_are_bounded_and_only_the_protocol_cartridge_is_evaluated(client, monkeypatch, device):
    built = evaluation_cartridge(client, monkeypatch)
    target = register(client, device)
    for runs in (0, 21, "5", True, 2.5):
        assert evaluate(client, target, built["esp32c6"], repetitions=runs).get_json()["code"] == "bad_runs", runs
    assert evaluate(client, target, built["esp32c6"], warm_up=4).get_json()["code"] == "bad_runs"
    changed = (ROOT / "examples/evaluation/prg32_evaluation.c").read_text() + "\n/* changed */\n"
    other = evaluation_cartridge(client, monkeypatch, source=changed)
    refused = evaluate(client, target, other["esp32c6"])
    assert refused.status_code == 409 and refused.get_json()["code"] == "not_the_protocol_cartridge"
    assert device.uploads == []


def test_an_evaluation_can_be_cancelled_and_keeps_what_it_measured(app, client, monkeypatch, device):
    import time

    app.config["DEPLOY_INLINE"] = False
    monkeypatch.setattr(evaluation, "RUN_TIMEOUT", 30.0)
    built = evaluation_cartridge(client, monkeypatch)
    device.silent_runs = {2}                                        # waits in the first measured run
    item = evaluate(client, register(client, device), built["esp32c6"]).get_json()
    deadline = time.monotonic() + 10
    while not any("Run 2 of 4" in line["text"] for line in client.get(f"/api/evaluations/{item['id']}").get_json()["log"]):
        assert time.monotonic() < deadline
        time.sleep(0.05)
    client.post(f"/api/evaluations/{item['id']}/cancel")
    while (done := client.get(f"/api/evaluations/{item['id']}").get_json())["status"] != "cancelled":
        assert time.monotonic() < deadline
        time.sleep(0.05)
    assert [run["role"] for run in done["result"]["runs"]] == ["warm-up"]
    assert client.get(f"/api/evaluations/{item['id']}/dataset.json").get_json()["rows"]


# --- charts ---------------------------------------------------------------------------------------

def test_a_chart_shows_every_measured_value_says_what_it_shows_and_is_deterministic(client, monkeypatch, device):
    built = evaluation_cartridge(client, monkeypatch)
    item = evaluate(client, register(client, device), built["esp32c6"]).get_json()
    svg = client.get(f"/api/evaluations/{item['id']}/chart.svg").data
    assert svg == client.get(f"/api/evaluations/{item['id']}/chart.svg").data
    text = svg.decode()
    assert 'role="img"' in text and "<title id=\"chart-title\">PRG32 evaluation: Frame time, mean</title>" in text
    assert "clear-fill mean 10030.0 (95% CI" in text and built["esp32c6"]["metadata"]["sha256"] in text
    assert text.count("<circle") == 3 * 5 + 1                       # every measured run of every case, and the legend
    assert "Frame time, mean (us)" in text and "not PRG32 console times" in text
    pdf = client.get(f"/api/evaluations/{item['id']}/chart.pdf").data
    assert pdf.startswith(b"%PDF-1.4") and pdf.endswith(b"%%EOF\n")
    offset = int(pdf.rsplit(b"startxref\n", 1)[1].split(b"\n")[0])
    assert pdf[offset:offset + 4] == b"xref"
    for number, line in enumerate(pdf[offset:].split(b"\n")[3:10], start=1):     # every object where the table says
        position = int(line.split()[0])
        assert pdf[position:position + len(f"{number} 0 obj")] == f"{number} 0 obj".encode()


def test_the_chart_is_made_again_from_the_downloaded_dataset_byte_for_byte(client, monkeypatch, device, tmp_path):
    built = evaluation_cartridge(client, monkeypatch)
    item = evaluate(client, register(client, device), built["esp32c6"]).get_json()
    (tmp_path / "dataset.json").write_bytes(client.get(f"/api/evaluations/{item['id']}/dataset.json").data)
    import importlib.util

    spec = importlib.util.spec_from_file_location("evaluation_charts", ROOT / "tools" / "evaluation_charts.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)          # in this process: the stand-in compiler has replaced subprocess.run
    assert tool.main([str(tmp_path / "dataset.json"), "--metric", "frame_us_p95", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "frame_us_p95.svg").read_bytes() == client.get(
        f"/api/evaluations/{item['id']}/chart.svg?metric=frame_us_p95").data
    assert (tmp_path / "frame_us_p95.pdf").read_bytes() == client.get(
        f"/api/evaluations/{item['id']}/chart.pdf?metric=frame_us_p95").data


def test_a_case_without_measurements_says_no_data_instead_of_zero():
    series = [{"name": "Console", "evidence": "physical device",
               "cases": {"a": {"values": [1.0, 2.0], **evaluation.describe([1.0, 2.0])}, "b": {"values": [], **evaluation.describe([])}}}]
    canvas = charts.bar_chart(series, ["a", "b"], {"label": "Frame time, mean", "unit": "us"}, "t", [], {})
    text = canvas.svg("t", "d", {}).decode()
    assert "no data" in text and text.count("<circle") == 2 + 1


def test_targets_are_compared_only_with_the_same_protocol_and_cartridge(client, monkeypatch, device):
    qt = FakePrg32(slots=4, host="qt", firmware_version="qt-1.0")
    try:
        built = evaluation_cartridge(client, monkeypatch)
        console = evaluate(client, register(client, device), built["esp32c6"]).get_json()
        emulator = evaluate(client, register(client, qt, kind="prg32qt", name="PRG32-QT"), built["qemu"]).get_json()
        compared = client.get(f"/api/evaluations/compare.json?ids={console['id']},{emulator['id']}").get_json()
        assert [item["evidence"] for item in compared["targets"]] == ["physical device", "emulator (PRG32-QT)"]
        assert compared["left_out"] == []
        svg = client.get(f"/api/evaluations/compare.svg?ids={console['id']},{emulator['id']}").data.decode()
        assert "Class console (physical device)" in svg and "PRG32-QT (emulator (PRG32-QT))" in svg
        assert svg.count("<rect") > svg.count("<circle") > 0
        csv = client.get(f"/api/evaluations/compare.csv?ids={console['id']},{emulator['id']}").data.decode().splitlines()
        assert len(csv) == 1 + 2 * 4 * 5 * 11
        # Another cartridge cannot share the chart.
        dataset = client.get(f"/api/evaluations/{emulator['id']}/dataset.json").get_json()
        dataset["about"]["cartridge_sha256"] = "0" * 64
        keep, left_out = evaluation.comparable([client.get(f"/api/evaluations/{console['id']}/dataset.json").get_json(), dataset])
        assert len(keep) == 1 and left_out == [{"evaluation_id": emulator["id"], "code": "cartridge",
                                             "reason": "another cartridge (different SHA-256)"}]
    finally:
        qt.stop()


# --- who may see what ---------------------------------------------------------------------------------

def test_evaluations_are_their_owner_s_and_erasure_removes_them(app, client, monkeypatch, device):
    assert client.post("/api/users", json={"username": "ann", "email": "ann@school.test",
                                           "password": STUDENT_PASSWORD}).status_code == 201
    ann = app.test_client(login=("ann", STUDENT_PASSWORD))
    built = evaluation_cartridge(client, monkeypatch)
    item = evaluate(client, register(client, device), built["esp32c6"]).get_json()
    for path in (f"/api/evaluations/{item['id']}", f"/api/evaluations/{item['id']}/dataset.csv",
                 f"/api/evaluations/{item['id']}/chart.svg", f"/api/evaluations/compare.json?ids={item['id']}"):
        assert ann.get(path).status_code == 404, path
    assert ann.get("/api/evaluations").get_json() == []
    folder = Path(app.config["DATA_DIR"]) / "evaluations" / item["id"]
    assert (folder / "dataset.json").is_file()
    with app.app_context():
        assert evaluation.delete_evaluations_of(1) == 1
    assert not folder.exists()
    from prg32_construction_kit.auth import required_scope

    assert required_scope("POST", "/api/evaluations") == "build"
