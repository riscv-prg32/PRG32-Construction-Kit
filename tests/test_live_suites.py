"""tools/run_live_suites.py: one step for the live integration suites, never a false pass, no secrets kept."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import run_live_suites  # noqa: E402


def test_a_suite_without_its_service_is_not_run_and_never_passes(tmp_path, monkeypatch):
    for name, (tests, environment, _check) in list(run_live_suites.SUITES.items()):
        monkeypatch.setitem(run_live_suites.SUITES, name, (tests, environment, lambda: "not here"))
    monkeypatch.setenv("PRG32_LIVE_CLOUD_REFRESH_TOKEN", "refresh-value-1234")
    assert run_live_suites.main(["--out", str(tmp_path)]) == 0
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert {item["outcome"] for item in summary["suites"].values()} == {"not run"}
    assert set(summary["suites"]) == {"store", "oidc-keycloak", "oidc-external", "cloud", "qemu"}
    assert "PRG32_LIVE_CLOUD_REFRESH_TOKEN" in summary["settings_present"]
    assert "refresh-value-1234" not in (tmp_path / "summary.json").read_text()


def test_secret_settings_are_redacted_from_logs():
    environment = {"PRG32_LIVE_OIDC_SECRET": "s3cr3t-value", "PRG32_LIVE_OIDC_PASSWORD": "pw-value",
                   "PRG32_LIVE_OIDC_ISSUER": "https://login.school.test", "HOME": "/home/x"}
    secrets = run_live_suites.secrets_in(environment)
    assert sorted(secrets) == ["pw-value", "s3cr3t-value"]                   # names say secret; not the issuer
    text = run_live_suites.redact("client_secret=s3cr3t-value password=pw-value at https://login.school.test", secrets)
    assert "s3cr3t-value" not in text and "pw-value" not in text and "https://login.school.test" in text
    machine = run_live_suites.redact(f'<testsuite hostname="laptop.home.lan"> {Path.home()}/x', [])
    assert "laptop.home.lan" not in machine and str(Path.home()) not in machine and "~/x" in machine


def test_the_recorded_live_run():
    """docs/evidence/live/2026-10-21: what ran passed, what had no service says so, nothing private kept."""
    folder = ROOT / "docs" / "evidence" / "live" / "2026-10-21"
    summary = json.loads((folder / "summary.json").read_text())
    outcomes = {name: item["outcome"] for name, item in summary["suites"].items()}
    assert outcomes == {"store": "passed", "oidc-keycloak": "passed", "oidc-external": "not run",
                        "cloud": "not run", "qemu": "passed"}
    for path in folder.iterdir():
        text = path.read_text()
        assert str(Path.home()) not in text, path.name
        if path.suffix == ".xml":
            import xml.etree.ElementTree as ElementTree

            assert 'hostname="redacted-host"' in text, path.name
            ElementTree.parse(path)                          # still well-formed after redaction


def test_a_run_where_everything_skipped_is_not_a_pass(tmp_path, monkeypatch):
    junit = tmp_path / "store.xml"

    def fake_run(command, **_kwargs):
        junit.write_text('<testsuites><testsuite tests="3" failures="0" errors="0" skipped="3"/></testsuites>')
        return type("Result", (), {"returncode": 0, "stdout": "sss", "stderr": ""})()

    monkeypatch.setattr(run_live_suites.subprocess, "run", fake_run)
    monkeypatch.setitem(run_live_suites.SUITES, "store", (["tests/test_store_live.py"], {}, lambda: None))
    assert run_live_suites.run_suite("store", tmp_path, [])["outcome"] == "not run"


def test_unknown_suites_are_refused(tmp_path):
    import pytest

    with pytest.raises(SystemExit):
        run_live_suites.main(["--out", str(tmp_path), "--only", "store,nonsense"])
