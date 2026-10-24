"""Build provenance: what made each cartridge, with SHA-256 fingerprints."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from prg32_construction_kit import provenance
from prg32_construction_kit.build_check import check_command
from prg32_construction_kit.sample_data import default_blocks

ASM = """    .section .text
    .globl prov_asm_init
    .globl prov_asm_update
    .globl prov_asm_draw
prov_asm_init:
    ret
prov_asm_update:
    ret
prov_asm_draw:
    ret
"""


def fake_builder(payload=b"PRG2-fake-cartridge", returncode=0):
    def run(command, **_kwargs):
        if returncode == 0:
            with open(command[command.index("--out") + 1], "wb") as cartridge:
                cartridge.write(payload)
        return SimpleNamespace(returncode=returncode, stdout="", stderr="" if returncode == 0 else "error: bad line")
    return run


@pytest.fixture()
def tools_present(monkeypatch):
    monkeypatch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: True)


def package(client, project_id, **body):
    response = client.post(f"/api/projects/{project_id}/package", json=body)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def blocks_project(client, title="Prov Game"):
    return client.post("/api/projects", json={"title": title, "blocks_json": default_blocks()}).get_json()


def test_c_build_records_provenance_and_cartridge_hashes(client, monkeypatch, tools_present):
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder())
    result = package(client, blocks_project(client)["id"], architectures=["qemu"])
    record = result["build"]["metadata"]["provenance"]
    assert record["schema"] == provenance.SCHEMA and record["status"] == "ready"
    assert record["kit"]["name"] == "PRG32-Construction-Kit" and record["kit"]["version"]
    assert record["abi"] == {"name": "prg32-portable-abi", "major": 1, "minor": 6, "hash": "0x260f6136"}
    assert record["authoring"] == "blocks" and record["source_language"] == "c"
    assert record["entry_prefix"] == "prov_game" and record["architectures_requested"] == ["qemu"]
    assert record["cart_ram_kib"] == 64 and isinstance(record["required_features"], list)
    assert record["source_sha256"] == hashlib.sha256(result["c_artifact"]["text_content"].encode()).hexdigest()
    expected = hashlib.sha256(b"PRG2-fake-cartridge").hexdigest()
    assert record["cartridges"] == [{"architecture": "qemu", "file": "prov-game-qemu.prg32",
                                     "sha256": expected, "bytes": len(b"PRG2-fake-cartridge")}]
    assert record["attempts"] == [{"architecture": "qemu", "ok": True}]
    assert record["started_at"] <= record["finished_at"]
    cartridge = result["cartridge_artifacts"][0]
    assert cartridge["metadata"]["sha256"] == expected and cartridge["metadata"]["bytes"] == 19
    downloaded = client.get(f"/api/artifacts/{cartridge['id']}/download").data
    assert hashlib.sha256(downloaded).hexdigest() == expected
    # Stored with the build, through the normal builds API.
    stored = client.get(f"/api/builds/{result['build']['id']}").get_json()
    assert stored["metadata"]["provenance"] == record


def test_generated_and_handwritten_assembly_say_what_they_are(client, monkeypatch, tools_present):
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder())
    generated = package(client, blocks_project(client)["id"], source_language="asm", architectures=["qemu"])
    record = generated["build"]["metadata"]["provenance"]
    assert (record["authoring"], record["source_language"]) == ("blocks", "asm")
    assert record["source_sha256"] == hashlib.sha256(generated["asm_artifact"]["text_content"].encode()).hexdigest()
    both = package(client, blocks_project(client, "Both Game")["id"], source_language="both", architectures=["qemu"])
    assert set(both["build"]["metadata"]["provenance"]["sources"]) == {"asm", "c"}
    project = client.post("/api/projects", json={"title": "Prov Asm",
                                                 "game_json": {"source_mode": "asm", "source_asm": ASM}}).get_json()
    handwritten = package(client, project["id"], architectures=["qemu"])["build"]["metadata"]["provenance"]
    assert (handwritten["authoring"], handwritten["source_language"]) == ("assembly", "asm")
    assert handwritten["source_sha256"] == hashlib.sha256(ASM.encode()).hexdigest()


def test_same_inputs_give_the_same_provenance(client, monkeypatch, tools_present):
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder())
    project = blocks_project(client)
    first = package(client, project["id"], architectures=["qemu"])["build"]["metadata"]["provenance"]
    second = package(client, project["id"], architectures=["qemu"])["build"]["metadata"]["provenance"]
    assert first["build_id"] != second["build_id"]
    for field in provenance.VOLATILE_FIELDS:
        first.pop(field)
        second.pop(field)
    assert first == second


def test_compiler_errors_are_failed_builds_not_source_only(client, monkeypatch, tools_present):
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder(returncode=1))
    result = package(client, blocks_project(client)["id"], architectures=["qemu"])
    assert result["build"]["status"] == "failed" and result["result"]["status"] == "failed"
    assert result["cartridge_artifacts"] == [] and result["bundle_artifact"]["kind"] == "source_bundle"
    record = result["build"]["metadata"]["provenance"]
    assert record["status"] == "failed" and record["cartridges"] == []
    assert record["attempts"] == [{"architecture": "qemu", "ok": False}]


def test_without_build_tools_the_bundle_is_source_only(client, monkeypatch):
    monkeypatch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: False)
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder(returncode=1))
    result = package(client, blocks_project(client)["id"])
    assert result["build"]["status"] == "source-only"
    assert result["build"]["metadata"]["provenance"]["status"] == "source-only"
    assert result["bundle_artifact"]["metadata"]["publishable"] is False


def test_packaging_crash_still_records_provenance(client, monkeypatch):
    def broken(**_kwargs):
        raise OSError("disk full")
    monkeypatch.setattr("prg32_construction_kit.routes.prepare_package", broken)
    project = blocks_project(client)
    assert client.post(f"/api/projects/{project['id']}/package", json={}).status_code == 500
    build = client.get(f"/api/builds?project_id={project['id']}").get_json()["builds"][0]
    assert build["status"] == "failed"
    assert build["metadata"]["provenance"]["status"] == "failed"
    assert build["metadata"]["provenance"]["cartridges"] == []


def test_no_server_paths_or_secrets_leave_the_server(app, client, monkeypatch, tools_present):
    app.config["PRG32_BUILD_COMMAND"] = "/opt/secret/bin/python3 -m prg32 cartridge build --api-token=abc123"
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder())
    result = package(client, blocks_project(client)["id"], architectures=["qemu"])
    text = json.dumps(result)
    for leaked in (str(app.config["BUILD_ROOT"]), str(app.config["DATA_DIR"]), "/opt/secret", "abc123"):
        assert leaked not in text
    assert "source_path" not in result["result"]
    command = result["build"]["metadata"]["provenance"]["build_command"]
    assert command["command"] == "python3 -m prg32 cartridge build --api-token=<hidden>"
    assert len(command["sha256"]) == 64


def test_git_revision_is_read_without_git(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git" / "refs" / "heads").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    assert provenance.git_revision(repo) is None
    (repo / ".git" / "packed-refs").write_text("# pack-refs\n" + "a" * 40 + " refs/heads/main\n")
    assert provenance.git_revision(repo) == "a" * 40
    (repo / ".git" / "refs" / "heads" / "main").write_text("b" * 40 + "\n")
    assert provenance.git_revision(repo) == "b" * 40
    (repo / ".git" / "HEAD").write_text("c" * 40 + "\n")  # detached
    assert provenance.git_revision(repo) == "c" * 40
    assert provenance.git_revision(tmp_path / "nothing") is None


def _real_toolchain_missing(command: str) -> bool:
    return not all(ok for ok, _ in check_command(command))


def test_real_cartridge_provenance(app, client):
    """Uses the real PRG32 toolchain when it is installed (skipped otherwise)."""
    if _real_toolchain_missing(app.config["PRG32_BUILD_COMMAND"]):
        pytest.skip("PRG32 build toolchain is not installed")
    result = package(client, blocks_project(client)["id"], architectures=["qemu"])
    record = result["build"]["metadata"]["provenance"]
    assert record["status"] == "ready" and record["toolchain"]["found"] and record["toolchain"]["version"]
    assert record["sdk"]["installed"] is True
    downloaded = client.get(f"/api/artifacts/{result['cartridge_artifacts'][0]['id']}/download").data
    assert downloaded[:4] == b"PRG2"
    assert hashlib.sha256(downloaded).hexdigest() == record["cartridges"][0]["sha256"]
    # Building the same project again with the same tools gives the same cartridge bytes.
    again = package(client, result["build"]["project_id"], architectures=["qemu"])["build"]["metadata"]["provenance"]
    assert again["cartridges"][0]["sha256"] == record["cartridges"][0]["sha256"]
