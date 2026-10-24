"""Deploy: a compiled PRG32 cartridge onto a console, PRG32-QT or QEMU (ADR-0028, docs/deploy.md).

The targets here are tests/fake_prg32.py, which answers like the console firmware's web API
(and like PRG32-QT with host "qt"). The cartridges are made through the real package API with
a stand-in compiler that writes a PRG2 v2 header, so the build records, hashes and staleness
are the real ones.
"""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from fake_prg32 import ABI_HASH, FakePrg32, cartridge
from prg32_construction_kit import deploy
from prg32_construction_kit.sample_data import default_blocks

STUDENT_PASSWORD = "student-password-1"


@pytest.fixture()
def device():
    fake = FakePrg32()
    yield fake
    fake.stop()


@pytest.fixture()
def qt():
    fake = FakePrg32(slots=4, host="qt", firmware_version="qt-1.0")
    yield fake
    fake.stop()


@pytest.fixture(autouse=True)
def quick(app, monkeypatch):
    app.config["DEPLOY_INLINE"] = True           # the steps run in the request, so the answer is final
    monkeypatch.setattr(deploy, "SETTLE_SECONDS", 1.5)
    monkeypatch.setattr(deploy, "MIN_FRAMES", 3)


def compiled(client, monkeypatch, title="Deploy Me", **header) -> dict:
    """Package a project with a stand-in compiler; the esp32c6 and qemu cartridge artifacts."""
    def fake_builder(command, **_kwargs):
        Path(command[command.index("--out") + 1]).write_bytes(cartridge(title, **header))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder)
    monkeypatch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: True)
    project = client.post("/api/projects", json={"title": title, "blocks_json": default_blocks()}).get_json()
    answer = client.post(f"/api/projects/{project['id']}/package", json={}).get_json()
    cartridges = {item["metadata"]["architecture"]: item for item in answer["cartridge_artifacts"]}
    return {"project": project, **cartridges}


def register(client, fake, kind="prg32", name="Class console") -> dict:
    answer = client.post("/api/admin/deploy_targets", json={"name": name, "kind": kind, "address": fake.url})
    assert answer.status_code == 201, answer.get_json()
    return answer.get_json()


def look(client, target, artifact=None) -> dict:
    answer = client.post(f"/api/deploy/targets/{target['id']}/probe",
                         json={"artifact_id": artifact["id"]} if artifact else {})
    assert answer.status_code == 200, answer.get_json()
    return answer.get_json()


def deploy_to(client, target, artifact, slot="cart3", probe=None, **extra):
    probe = probe or look(client, target, artifact)
    seen = next(item for item in probe["slots"] if item["slot"] == slot) if slot else {}
    payload = {"artifact_id": artifact["id"], "target": target["id"], "slot": slot, "confirm": True,
               "expect": {"fingerprint": probe["fingerprint"], "slot_content": deploy.slot_content(seen)}, **extra}
    return client.post("/api/deployments", json=payload)


# --- it works, and says what it proves ------------------------------------------------------

def test_a_cartridge_runs_on_a_console_with_every_step_recorded(client, monkeypatch, device):
    built = compiled(client, monkeypatch)
    target = register(client, device)
    probe = look(client, target, built["esp32c6"])
    assert probe["identity"]["firmware_version"] == "679dfb5" and probe["abi"]["hash"] == ABI_HASH
    assert [slot["slot"] for slot in probe["slots"]] == [f"cart{n}" for n in range(8)]
    assert probe["abi_problems"] == [] and all(slot["problems"] == [] for slot in probe["slots"])
    answer = deploy_to(client, target, built["esp32c6"], probe=probe)
    assert answer.status_code == 202
    item = client.get(f"/api/deployments/{answer.get_json()['id']}").get_json()
    assert item["status"] == "launched" and item["progress"] == 100
    assert item["physical_device"] is True and item["evidence"] == "physical device"
    assert device.uploads == [("cart3", built["esp32c6"]["metadata"]["bytes"])] and device.loaded == "cart3"
    assert item["result"]["cartridge"]["sha256"] == built["esp32c6"]["metadata"]["sha256"]
    assert item["result"]["target"]["fingerprint"] == probe["fingerprint"]
    texts = [line["text"] for line in item["log"]]
    assert texts[0].startswith("Asking Class console") and any("Sending" in text for text in texts)
    assert all(line.get("message_key", "").startswith("server.deploy.") for line in item["log"])
    picture = client.get(item["screenshot"])
    assert picture.status_code == 200 and picture.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_prg32_qt_is_an_emulator_run_never_physical_evidence(client, monkeypatch, qt):
    built = compiled(client, monkeypatch)
    target = register(client, qt, kind="prg32qt", name="PRG32-QT")
    assert target["evidence"] == "emulator (PRG32-QT)"
    probe = look(client, target, built["qemu"])
    assert [slot["slot"] for slot in probe["slots"]] == ["cart0", "cart1", "cart2", "cart3"]
    item = deploy_to(client, target, built["qemu"], probe=probe).get_json()
    assert item["status"] == "launched" and item["physical_device"] is False
    assert item["evidence"] == item["result"]["evidence"] == "emulator (PRG32-QT)"


# --- nothing is replaced that nobody named or saw ---------------------------------------------

def test_a_slot_must_be_named_and_confirmed(client, monkeypatch, device):
    built = compiled(client, monkeypatch)
    target = register(client, device)
    probe = look(client, target, built["esp32c6"])
    unnamed = deploy_to(client, target, built["esp32c6"], slot="", probe=probe)
    assert unnamed.status_code == 400 and unnamed.get_json()["code"] == "slot_unknown"
    payload = {"artifact_id": built["esp32c6"]["id"], "target": target["id"], "slot": "cart3",
               "expect": {"fingerprint": probe["fingerprint"], "slot_content": {"slot": "cart3"}}}
    unconfirmed = client.post("/api/deployments", json=payload)
    assert unconfirmed.status_code == 400 and unconfirmed.get_json()["code"] == "not_confirmed"
    blind = client.post("/api/deployments", json={**payload, "confirm": True, "expect": {}})
    assert blind.status_code == 400 and blind.get_json()["code"] == "not_confirmed"
    missing = deploy_to(client, target, built["esp32c6"], slot="cart9", probe={
        **probe, "slots": probe["slots"] + [{"slot": "cart9"}]}).get_json()
    assert missing["status"] == "refused" and missing["result"]["code"] == "slot_unknown"
    assert device.uploads == []


def test_a_slot_that_changed_since_the_student_looked_is_not_overwritten(client, monkeypatch, device):
    built = compiled(client, monkeypatch)
    target = register(client, device)
    probe = look(client, target, built["esp32c6"])
    device.slots["cart3"] = cartridge("Someone else's game")        # another student, meanwhile
    item = deploy_to(client, target, built["esp32c6"], probe=probe).get_json()
    assert item["status"] == "refused" and item["result"]["code"] == "slot_changed"
    assert item["result"]["left"] == "Nothing was sent: the target is as it was."
    assert FakePrg32.name_of(device.slots["cart3"]) == "Someone else's game" and device.uploads == []


def test_a_target_that_changed_firmware_since_the_student_looked_is_refused(client, monkeypatch, device):
    built = compiled(client, monkeypatch)
    target = register(client, device)
    probe = look(client, target, built["esp32c6"])
    device.firmware_version = "abc1234"                              # re-flashed meanwhile
    item = deploy_to(client, target, built["esp32c6"], probe=probe).get_json()
    assert item["result"]["code"] == "target_changed" and device.uploads == []


# --- the cartridge ----------------------------------------------------------------------------

def test_a_stale_build_is_refused(client, monkeypatch, device):
    built = compiled(client, monkeypatch)
    target = register(client, device)
    probe = look(client, target, built["esp32c6"])
    project = built["project"]
    client.put(f"/api/projects/{project['id']}", json={"title": "Changed", "expected_version": project["version"]})
    answer = deploy_to(client, target, built["esp32c6"], probe=probe)
    assert answer.status_code == 409 and answer.get_json()["code"] == "stale_build"
    assert "press Compile" in answer.get_json()["error"] and device.uploads == []


def test_a_cartridge_whose_bytes_changed_after_the_build_is_refused(client, monkeypatch, device):
    built = compiled(client, monkeypatch)
    target = register(client, device)
    probe = look(client, target, built["esp32c6"])
    with client.application.app_context():
        from prg32_construction_kit.db import get_resource

        path = Path(get_resource("artifacts", built["esp32c6"]["id"])["path"])
    path.write_bytes(path.read_bytes() + b"\x00")
    answer = deploy_to(client, target, built["esp32c6"], probe=probe)
    assert answer.status_code == 409 and answer.get_json()["code"] == "hash_mismatch" and device.uploads == []


def test_only_cartridges_built_here_and_for_this_kind_of_target(client, monkeypatch, device):
    built = compiled(client, monkeypatch)
    target = register(client, device)
    probe = look(client, target, built["esp32c6"])
    wrong = deploy_to(client, target, built["qemu"], probe=probe)
    assert wrong.status_code == 409 and wrong.get_json()["code"] == "wrong_architecture"
    uploaded = client.post("/api/artifacts", json={"kind": "prg32_cartridge", "name": "mine.prg32",
                                                   "metadata": {"architecture": "esp32c6"}}).get_json()
    answer = deploy_to(client, target, uploaded, probe=probe)
    assert answer.status_code == 409 and answer.get_json()["code"] == "not_built_here"


# --- the target -------------------------------------------------------------------------------

def test_an_unsupported_abi_is_refused_before_anything_is_sent(client, monkeypatch):
    other = FakePrg32(abi_hash=0x12345678)
    try:
        built = compiled(client, monkeypatch)
        target = register(client, other)
        probe = look(client, target, built["esp32c6"])
        assert probe["abi_problems"] and "another PRG32 version" in probe["abi_problems"][0]["error"]
        item = deploy_to(client, target, built["esp32c6"], probe=probe).get_json()
        assert item["status"] == "refused" and item["result"]["code"] == "unsupported_abi" and other.uploads == []
    finally:
        other.stop()


def test_missing_features_and_a_major_version_are_unsupported_too():
    header = deploy.cartridge_header(cartridge(features=0b100))
    probe = {"abi": {"major": 1, "minor": 6, "hash": ABI_HASH, "features": 0b011}, "limits": {}}
    assert "features" in str(deploy.abi_problems(header, probe)[0])
    assert "ABI 1, the target has ABI 2" in str(deploy.abi_problems(header, {**probe, "abi": {**probe["abi"], "major": 2}})[0])
    older = deploy.cartridge_header(cartridge(abi_hash=1810294992))      # an older hash the SDK still runs
    assert deploy.abi_problems(older, probe | {"abi": {**probe["abi"], "features": 0xFFFF}}) == []


def test_a_full_target_is_refused_before_and_while_sending(client, monkeypatch):
    small = FakePrg32(cart_max_size=100)
    try:
        built = compiled(client, monkeypatch, padding=200)
        target = register(client, small)
        probe = look(client, target, built["esp32c6"])
        assert "takes at most 100" in probe["slots"][3]["problems"][0]["error"]
        item = deploy_to(client, target, built["esp32c6"], probe=probe).get_json()
        assert item["result"]["code"] == "target_full" and small.uploads == []
    finally:
        small.stop()


def test_a_target_that_refuses_the_upload_says_the_slot_may_have_changed(client, monkeypatch, device):
    built = compiled(client, monkeypatch)
    target = register(client, device)
    device.fail = "full"
    item = deploy_to(client, target, built["esp32c6"]).get_json()
    assert item["status"] == "refused" and item["result"]["code"] == "target_full"
    assert "cart3 may no longer hold its old game" in item["result"]["left"]


def test_a_dropped_connection_is_retried_then_reported(client, monkeypatch, device):
    monkeypatch.setattr(deploy.time, "sleep", lambda _seconds: None)
    built = compiled(client, monkeypatch)
    target = register(client, device)
    device.fail, device.drops = "drop_upload", 1                      # one hiccup: the retry succeeds
    item = deploy_to(client, target, built["esp32c6"]).get_json()
    assert item["status"] == "launched" and any("trying again (1 of 2)" in line["text"] for line in item["log"])
    device.fail, device.drops, device.loaded = "drop_upload", 5, None   # the console is gone for good
    item = deploy_to(client, target, built["esp32c6"]).get_json()
    assert item["status"] == "failed" and item["result"]["code"] == "disconnected"
    assert "may hold part of the cartridge" in item["result"]["left"]


def test_a_target_that_disappears_after_the_upload_says_the_cartridge_is_stored(client, monkeypatch, device):
    monkeypatch.setattr(deploy.time, "sleep", lambda _seconds: None)
    built = compiled(client, monkeypatch)
    target = register(client, device)
    device.fail = "gone_after_upload"
    item = deploy_to(client, target, built["esp32c6"]).get_json()
    assert item["status"] == "failed" and item["result"]["code"] == "disconnected"
    assert item["result"]["left"].startswith("cart3 holds this cartridge, but it did not start")


def test_an_unreachable_target_is_reported_when_looking(client):
    target = client.post("/api/admin/deploy_targets", json={"name": "Off", "kind": "prg32",
                                                            "address": "http://127.0.0.1:9"}).get_json()
    answer = client.post(f"/api/deploy/targets/{target['id']}/probe", json={})
    assert answer.status_code == 502 and answer.get_json()["code"] == "disconnected"


@pytest.mark.parametrize("failure", ["select_refused", "never_runs"])
def test_a_launch_failure_is_reported_with_what_the_slot_holds(client, monkeypatch, device, failure):
    built = compiled(client, monkeypatch)
    target = register(client, device)
    device.fail = failure
    item = deploy_to(client, target, built["esp32c6"]).get_json()
    assert item["status"] == "failed" and item["result"]["code"] == "launch_failed"
    assert item["result"]["left"].startswith("cart3 holds this cartridge")


def test_a_deployment_can_be_cancelled(app, client, monkeypatch, device):
    app.config["DEPLOY_INLINE"] = False
    monkeypatch.setattr(deploy, "SETTLE_SECONDS", 30)
    built = compiled(client, monkeypatch)
    target = register(client, device)
    device.fail = "never_runs"                                       # waits in "verifying"
    item = deploy_to(client, target, built["esp32c6"]).get_json()
    deadline = time.monotonic() + 10
    while client.get(f"/api/deployments/{item['id']}").get_json()["status"] != "verifying":
        assert time.monotonic() < deadline
        time.sleep(0.05)
    assert client.post(f"/api/deployments/{item['id']}/cancel").get_json()["cancel_requested"] is True
    while (done := client.get(f"/api/deployments/{item['id']}").get_json())["status"] != "cancelled":
        assert time.monotonic() < deadline
        time.sleep(0.05)
    assert done["result"]["left"].startswith("cart3 holds this cartridge")


def test_one_deployment_per_target_at_a_time(app, client, monkeypatch, device):
    from prg32_construction_kit.db import db

    built = compiled(client, monkeypatch)
    target = register(client, device)
    with app.app_context():
        db.session.add(deploy.Deployment(id="dep_running", owner_id=1, artifact_id="x", target=target["id"],
                                         target_kind="prg32", slot="cart1", status="uploading"))
        db.session.commit()
    answer = deploy_to(client, target, built["esp32c6"])
    assert answer.status_code == 409 and answer.get_json()["code"] == "target_busy"


def test_a_deployment_whose_server_stopped_is_reported_as_interrupted(app, client):
    from prg32_construction_kit.db import db

    with app.app_context():
        db.session.add(deploy.Deployment(id="dep_old", owner_id=1, artifact_id="x", target="1", target_kind="prg32",
                                         slot="cart1", status="uploading", updated_at="2020-01-01T00:00:00+00:00"))
        db.session.commit()
    item = client.get("/api/deployments/dep_old").get_json()
    assert item["status"] == "failed" and item["result"]["code"] == "interrupted"


# --- who may do what ------------------------------------------------------------------------------

def test_only_administrators_register_targets_and_only_safe_addresses(app, client, monkeypatch, device):
    assert client.post("/api/users", json={"username": "ann", "email": "ann@school.test",
                                           "password": STUDENT_PASSWORD}).status_code == 201
    ann = app.test_client(login=("ann", STUDENT_PASSWORD))
    assert ann.post("/api/admin/deploy_targets", json={"name": "Mine", "kind": "prg32",
                                                       "address": device.url}).status_code == 403
    for address in ("ftp://192.168.4.1", "http://user:pw@192.168.4.1", "http://192.168.4.1/api/x", "192.168.4.1"):
        answer = client.post("/api/admin/deploy_targets", json={"name": "Bad", "kind": "prg32", "address": address})
        assert answer.status_code == 400, address
    assert client.post("/api/admin/deploy_targets", json={"name": "Q", "kind": "qemu",
                                                          "address": device.url}).status_code == 400
    target = register(client, device)
    assert [item["name"] for item in ann.get("/api/deploy/targets").get_json()] == ["Class console"]
    # A student deploys their own cartridges only, and sees only their own deployments.
    built = compiled(client, monkeypatch)                               # the admin's
    answer = deploy_to(ann, target, built["esp32c6"], probe=look(client, target))
    assert answer.status_code == 404 and answer.get_json()["code"] == "not_found"
    mine = compiled(ann, monkeypatch, title="Ann's game")
    item = deploy_to(ann, target, mine["esp32c6"]).get_json()
    assert item["status"] == "launched"
    assert ann.get("/api/deployments").get_json()[0]["id"] == item["id"]
    other = deploy_to(client, target, built["esp32c6"], slot="cart4").get_json()
    assert ann.get(f"/api/deployments/{other['id']}").status_code == 404
    assert ann.get(other["screenshot"]).status_code == 404


def test_guests_and_tokens_without_the_build_scope_cannot_deploy(app, anon, client):
    from prg32_construction_kit.auth import required_scope

    assert anon.get("/api/deploy/targets").status_code == 401
    assert required_scope("POST", "/api/deployments") == "build"
    assert required_scope("POST", "/api/deploy/targets/1/probe") == "build"
    assert required_scope("POST", "/api/admin/deploy_targets") == "admin"


def test_erasure_removes_the_deployments_and_keeps_the_console(app, client, monkeypatch, device):
    from prg32_construction_kit import privacy
    from prg32_construction_kit.db import db

    built = compiled(client, monkeypatch)
    target = register(client, device)
    item = deploy_to(client, target, built["esp32c6"]).get_json()
    folder = Path(app.config["DATA_DIR"]) / "deployments" / item["id"]
    assert (folder / "screenshot.png").is_file()
    with app.app_context():
        removed = deploy.delete_deployments_of(1)
        assert removed == 1 and db.session.get(deploy.Deployment, item["id"]) is None
        assert db.session.get(deploy.DeployTarget, int(target["id"])).created_by is None
        assert "deployments" in privacy.PERSONAL_TABLES and "deploy_targets" in privacy.PERSONAL_TABLES
    assert not folder.exists()


# --- QEMU's flash staging and the pictures ------------------------------------------------------------

def test_a_cartridge_fills_its_whole_slot_in_the_flash_image(tmp_path):
    flash = tmp_path / "flash.bin"
    flash.write_bytes(b"\x00" * 0x400)
    deploy.stage_in_flash(flash, 0x100, 0x80, b"PRG2game")
    image = flash.read_bytes()
    assert image[0x100:0x108] == b"PRG2game" and image[0x108:0x180] == b"\xff" * 0x78
    assert image[:0x100] == b"\x00" * 0x100 and image[0x180:] == b"\x00" * 0x280
    with pytest.raises(deploy.DeployProblem) as refused:
        deploy.stage_in_flash(flash, 0x100, 4, b"PRG2game")
    assert refused.value.code == "target_full"


def test_screens_become_pngs():
    yellow = FakePrg32.bmp(SimpleNamespace(loaded="cart0"))
    picture = deploy.bmp_to_png(yellow)
    assert picture[:8] == b"\x89PNG\r\n\x1a\n" and picture[16:24] == b"\x00\x00\x00\x04\x00\x00\x00\x02"
    assert deploy.bmp_to_png(b"not a bmp") is None
    assert deploy.rgb565_to_png(b"\xff\xff" * 4, 2, 2)[:8] == b"\x89PNG\r\n\x1a\n"
    assert deploy.rgb565_to_png(b"\xff", 2, 2) is None


def test_qemu_is_offered_only_when_the_operator_set_it_up(app, client, tmp_path):
    assert all(item["kind"] != "qemu" for item in client.get("/api/deploy/targets").get_json())
    app.config["QEMU_FIRMWARE"], app.config["QEMU_BINARY"] = str(tmp_path / "missing"), "/bin/true"
    assert all(item["kind"] != "qemu" for item in client.get("/api/deploy/targets").get_json())
