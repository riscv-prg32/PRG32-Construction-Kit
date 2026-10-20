"""The shared Store contract (contracts/prg32-store-contract-1.json) against the kit and the Store.

- The generated fixture bundles are up to date and reproducible.
- The kit accepts and refuses exactly the fixtures the contract says, with its codes.
- Every manifest the kit makes satisfies the contract; the version follows the project.
- A bundle that breaks the contract is refused before anything is uploaded.
- With a CartridgeStore checkout next to the kit (or PRG32_CARTRIDGE_STORE_SOURCE), the
  Store's own bundle code accepts and refuses the same fixtures, its refusals map to the
  same contract codes, and its id/version patterns, architectures and metadata ABI are the
  contract's. PRG32_REQUIRE_STORE=1 (the CI store-contract job) turns a missing checkout
  into a failure instead of a skip.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from prg32_construction_kit import store_contract
from prg32_construction_kit.packager import project_manifest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "contract"
EXPECTED = json.loads((FIXTURES / "expected.json").read_text())
STORE = Path(os.environ.get("PRG32_CARTRIDGE_STORE_SOURCE") or ROOT.parent / "CartridgeStore")
REQUIRE_STORE = os.environ.get("PRG32_REQUIRE_STORE") == "1"

# Runs in a separate interpreter with the Store on its path: the Store's code decides.
STORE_PROBE = r"""
import io, json, re, sys, zipfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from cartridge_store import app as store_app, prg32_format as fmt, store as store_module
results = {}
for path in sorted(Path(sys.argv[2]).glob("*.zip")):
    data = path.read_bytes()
    try:
        if not data.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
            raise store_app.StoreError("bundle must be a zip file")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            store_app._prepare_bundle(zf)
        results[path.stem] = {"accepted": True}
    except Exception as error:
        results[path.stem] = {"accepted": False, "message": str(error)}
aliases = {}
for alias in json.loads(sys.argv[3]):
    try:
        aliases[alias] = fmt.normalize_architecture(alias)
    except Exception:
        aliases[alias] = None
print(json.dumps({"results": results, "safe_id": store_module.SAFE_ID_RE.pattern,
                  "safe_version": store_module.SAFE_VERSION_RE.pattern, "metadata_abi": fmt.METADATA_ABI,
                  "architectures": sorted(fmt.ARCHITECTURE_PROFILES), "aliases": aliases}))
"""


@pytest.fixture(scope="module")
def store():
    if not (STORE / "cartridge_store" / "app.py").is_file():
        if REQUIRE_STORE:
            pytest.fail(f"PRG32_REQUIRE_STORE=1 but there is no CartridgeStore checkout at {STORE}", pytrace=False)
        pytest.skip("no CartridgeStore checkout (set PRG32_CARTRIDGE_STORE_SOURCE)")
    names = list(store_contract.contract()["architectures"]["aliases"]) + ["gameboy", "esp32c6", "qemu"]
    result = subprocess.run([sys.executable, "-c", STORE_PROBE, str(STORE), str(FIXTURES), json.dumps(names)],
                            capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        if REQUIRE_STORE:
            pytest.fail(f"the CartridgeStore code could not run: {result.stderr[-800:]}", pytrace=False)
        pytest.skip(f"the CartridgeStore code could not run (its requirements?): {result.stderr[-200:]}")
    return json.loads(result.stdout)


def test_fixtures_are_up_to_date():
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "build_contract_fixtures.py"), "--check"],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_the_kit_decides_like_the_contract(name):
    data = (FIXTURES / f"{name}.zip").read_bytes()
    if EXPECTED[name]["accepted"]:
        assert store_contract.validate_bundle(data)["id"]
    else:
        with pytest.raises(store_contract.ContractViolation) as refused:
            store_contract.validate_bundle(data)
        assert refused.value.code == EXPECTED[name]["kit_code"]


def test_every_refusal_code_is_in_the_contract():
    codes = {rule["code"] for rule in store_contract.contract()["errors"]}
    assert {item["kit_code"] for item in EXPECTED.values() if not item["accepted"]} <= codes


def test_kit_manifests_satisfy_the_contract_and_follow_the_project_version():
    from test_examples import EXAMPLE_FILES, load_project

    for path in EXAMPLE_FILES:
        project = {**load_project(path), "version": 7}
        manifest = project_manifest(project, {"abi": "prg32-construction-kit-game-1.0", "title": project["title"]},
                                    [{"id": "qemu", "file": "game-qemu.prg32"}])
        assert store_contract.manifest_errors(manifest) == [], path.name
        assert manifest["version"] == "0.1.7"


def test_store_answers_become_contract_codes():
    assert store_contract.classify(401)["code"] == "unauthorized"
    assert store_contract.classify(None) == {"code": "network", "retryable": True,
                                             "student_message": store_contract.classify(None)["student_message"]}
    assert store_contract.classify(502)["retryable"] is True
    assert store_contract.classify(400, "something new")["code"] == "unknown"


def test_a_bundle_that_breaks_the_contract_is_never_uploaded(app, client, monkeypatch):
    """The review refuses it (contract_<code>) and no request reaches a Store."""
    from prg32_construction_kit.db import create_resource

    uploads = []
    monkeypatch.setattr("prg32_construction_kit.routes.publish_bundle", lambda *args, **kwargs: uploads.append(args))
    app.config["STORE_ALLOWED_ORIGINS"] = ["https://store.school.test"]
    bundle_path = Path(app.config["BUILD_ROOT"]) / "contract-test" / "bad.zip"
    bundle_path.parent.mkdir(parents=True)
    bundle_path.write_bytes((FIXTURES / "unsafe-version.zip").read_bytes())
    with app.app_context():
        profile = create_resource("publish_profiles", {"name": "s", "store_url": "https://store.school.test",
                                                       "owner_id": 1})
        bundle = create_resource("artifacts", {"kind": "store_bundle", "name": "bad.zip", "path": str(bundle_path),
                                               "owner_id": 1, "metadata": {"publishable": True}})
    answer = client.post("/api/publish/review", json={"profile_id": profile["id"], "bundle_artifact_id": bundle["id"]})
    assert answer.status_code == 400, answer.get_json()
    assert answer.get_json()["reason"] == "contract_unsafe_id_or_version", answer.get_json()
    confirm = client.post("/api/publish", json={"profile_id": profile["id"], "bundle_artifact_id": bundle["id"],
                                                "confirm": True, "review_token": "anything"})
    assert confirm.status_code >= 400
    assert uploads == []


# --- the Store's own code -----------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_the_store_decides_like_the_contract(store, name):
    observed = store["results"][name]
    assert observed["accepted"] is EXPECTED[name]["accepted"], observed
    if not observed["accepted"]:
        status = 400
        assert store_contract.classify(status, observed["message"])["code"] == EXPECTED[name]["kit_code"], observed


def test_the_store_uses_the_contracts_patterns_and_architectures(store):
    schema = store_contract.contract()["manifest_schema"]["properties"]
    assert schema["id"]["pattern"] == store["safe_id"]
    assert schema["version"]["pattern"] == store["safe_version"]
    assert schema["abi"]["const"] == store["metadata_abi"]
    rules = store_contract.contract()["architectures"]
    assert sorted(rules["canonical"]) == store["architectures"]
    for alias, canonical in rules["aliases"].items():
        assert store["aliases"][alias] == canonical
    assert store["aliases"]["gameboy"] is None
