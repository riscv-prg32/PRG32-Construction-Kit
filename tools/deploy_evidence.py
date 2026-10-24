"""Deploy a real kit-built cartridge to a real target through the kit's own Deploy API, and keep the record.

    python3 tools/deploy_evidence.py --prg32qt http://127.0.0.1:8080 --slot cart3 --out docs/evidence/deploy/DATE-prg32qt
    python3 tools/deploy_evidence.py --qemu-firmware data/qemu-firmware --slot cart0 --out docs/evidence/deploy/DATE-qemu
    python3 tools/deploy_evidence.py --console http://192.168.4.1 --slot cart7 --out docs/evidence/deploy/DATE-console

A fresh kit (its own temporary data folder) compiles examples/games/pong.json with the real PRG32
toolchain (PYTHONPATH must reach the PRG32 SDK, PATH the RISC-V GCC), an administrator registers
the target, and then, through the same API routes the Deploy page uses:

1. the target is looked at (identity, ABI, slots) and the cartridge fits;
2. what must be refused is refused without sending anything: no slot named, a slot whose content
   is not what was seen, a stale build, a cartridge file changed after its build, the wrong
   architecture (the target is asked again after these: the slot is still as it was);
3. the cartridge is deployed to --slot (what is in it is replaced: pick one nobody needs), and the
   target reports it running; its screenshot is kept.

``record.json`` has each check, the deployment's steps, the cartridge's SHA-256, the target's
identity and ABI, the kit and SDK commits, and what the run proves: only --console is a physical
device. Exit status 0 when every check passed.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EXAMPLE = ROOT / "examples" / "games" / "pong.json"


def commit(path: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def make_kit(data: Path, qemu_firmware: Path | None):
    from prg32_construction_kit import create_app

    password = secrets.token_urlsafe(18)
    app = create_app({
        "TESTING": True, "DATA_DIR": data, "DB_PATH": data / "kit.sqlite", "BUILD_ROOT": data / "builds",
        "ARTIFACT_ROOT": data / "artifacts", "ADMIN_PASSWORD": password, "SSO_SECRET": "", "SSO_PEER_URL": "",
        "PRG32_BUILD_COMMAND": os.environ.get("PRG32_BUILD_COMMAND", f"{sys.executable} -m prg32 cartridge build"),
        "PRG32_CART_RAM_KIB": 64, "DEPLOY_INLINE": True,
        "QEMU_FIRMWARE": str(qemu_firmware) if qemu_firmware else None,
        "QEMU_BINARY": os.environ.get("PRG32_QEMU") or None, "QEMU_GDB": os.environ.get("PRG32_QEMU_GDB") or None,
    })
    client = app.test_client()
    client.environ_base["HTTP_X_PRG32_KIT"] = "1"
    answer = client.post("/auth/login", data={"username": "admin", "password": password})
    assert answer.status_code == 302, answer.get_data(as_text=True)
    return app, client


def compile_example(client) -> dict:
    project = json.loads(EXAMPLE.read_text())
    project = project.get("project", project)
    made = client.post("/api/projects", json={"title": "Deploy check", "blocks_json": project["blocks_json"]}).get_json()
    packaged = client.post(f"/api/projects/{made['id']}/package", json={}).get_json()
    if not packaged.get("cartridge_artifacts"):
        raise SystemExit("the PRG32 toolchain did not compile the example: " + str(packaged.get("build", {}).get("log", ""))[-800:])
    return {"project": made, **{item["metadata"]["architecture"]: item for item in packaged["cartridge_artifacts"]}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--console", help="a PRG32 console's address, e.g. http://192.168.4.1")
    where.add_argument("--prg32qt", help="PRG32-QT's web API, e.g. http://127.0.0.1:8080")
    where.add_argument("--qemu-firmware", type=Path, help="a folder from tools/build_qemu_firmware.py")
    parser.add_argument("--slot", required=True, help="the slot to use; what is in it is replaced")
    parser.add_argument("--notes", default="", help="what you saw")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    from prg32_construction_kit import deploy

    checks: list[dict] = []

    def check(name: str, ok: bool, detail: object = "") -> bool:
        checks.append({"check": name, "ok": bool(ok), "detail": "" if ok else str(detail)[:500]})
        print(("ok    " if ok else "FAIL  ") + name + ("" if ok else f": {detail}"), flush=True)
        return bool(ok)

    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        app, client = make_kit(Path(temp), args.qemu_firmware.resolve() if args.qemu_firmware else None)
        kind = "prg32" if args.console else "prg32qt" if args.prg32qt else "qemu"
        if kind == "qemu":
            target = next((item for item in client.get("/api/deploy/targets").get_json() if item["id"] == "qemu"), None)
            if not check("QEMU is offered (firmware folder and qemu-system-riscv32 found)", target is not None):
                return 1
        else:
            answer = client.post("/api/admin/deploy_targets", json={
                "name": "PRG32 console" if kind == "prg32" else "PRG32-QT", "kind": kind,
                "address": args.console or args.prg32qt})
            check("an administrator registers the target", answer.status_code == 201, answer.get_json())
            target = answer.get_json()
        built = compile_example(client)
        architecture = "esp32c6" if kind == "prg32" else "qemu"
        cartridge = built[architecture]

        def look() -> dict:
            answer = client.post(f"/api/deploy/targets/{target['id']}/probe", json={"artifact_id": cartridge["id"]})
            return answer.get_json() if answer.status_code == 200 else {"error": answer.get_json()}

        probe = look()
        if not check("the target answers who it is", "fingerprint" in probe, probe.get("error")):
            return finish(args, checks, {}, None, kind)
        check("the cartridge's ABI is the target's", probe["abi_problems"] == [], probe["abi_problems"])
        seen = next((slot for slot in probe["slots"] if slot["slot"] == args.slot), None)
        if not check(f"the target has {args.slot} and the cartridge fits in it", seen is not None and seen["problems"] == [],
                     seen):
            return finish(args, checks, probe, None, kind)
        expect = {"fingerprint": probe["fingerprint"], "slot_content": deploy.slot_content(seen)}

        def deploy_with(**changes) -> tuple[int, dict]:
            payload = {"artifact_id": cartridge["id"], "target": target["id"], "slot": args.slot, "confirm": True,
                       "expect": expect, **changes}
            answer = client.post("/api/deployments", json=payload)
            return answer.status_code, answer.get_json()

        status, answer = deploy_with(slot="")
        check("refused: no slot named", status == 400 and answer.get("code") == "slot_unknown", answer)
        status, answer = deploy_with(expect={**expect, "slot_content": {**expect["slot_content"], "name": "not what is there"}})
        check("refused: the slot holds something else than what was seen",
              answer.get("status") == "refused" and answer["result"].get("code") == "slot_changed", answer)
        other = built["esp32c6" if architecture == "qemu" else "qemu"]
        status, answer = deploy_with(artifact_id=other["id"])
        if kind != "prg32qt":            # PRG32-QT runs both architectures
            check("refused: a cartridge for another architecture", answer.get("code") == "wrong_architecture", answer)
        with app.app_context():
            from prg32_construction_kit.db import get_resource

            path = Path(get_resource("artifacts", cartridge["id"])["path"])
        original = path.read_bytes()
        path.write_bytes(original + b"\0")
        status, answer = deploy_with()
        check("refused: the cartridge file changed after its build", answer.get("code") == "hash_mismatch", answer)
        path.write_bytes(original)
        project = built["project"]
        client.put(f"/api/projects/{project['id']}", json={"description": "changed after the build",
                                                           "expected_version": project["version"]})
        status, answer = deploy_with()
        check("refused: a stale build", answer.get("code") == "stale_build", answer)
        again = look()
        check("after the refusals the slot is as it was", deploy.slot_content(next(
            slot for slot in again["slots"] if slot["slot"] == args.slot)) == expect["slot_content"])
        cartridge = compile_example(client)[architecture]        # a fresh build of the example, deployed for real
        probe = look()
        seen = next(slot for slot in probe["slots"] if slot["slot"] == args.slot)
        expect = {"fingerprint": probe["fingerprint"], "slot_content": deploy.slot_content(seen)}
        status, item = deploy_with()
        check("the deployment ran to the end", item.get("status") == "launched", item.get("result"))
        check("the target received the kit's cartridge (same SHA-256)",
              item["result"].get("cartridge", {}).get("sha256") == cartridge["metadata"]["sha256"], item["result"])
        picture = client.get(item["screenshot"]).data if item.get("screenshot") else None
        check("a screenshot came back from the target", bool(picture), item.get("screenshot"))
        if picture:
            (args.out / "screenshot.png").write_bytes(picture)
        if kind != "qemu":
            after = look()
            slot = next(slot for slot in after["slots"] if slot["slot"] == args.slot)
            check(f"{args.slot} now holds the cartridge", slot["stored"] and slot["code_size"] == item["result"]["cartridge"]["code_size"], slot)
        return finish(args, checks, probe, item, kind, cartridge, picture)


def finish(args, checks, probe, item, kind, cartridge=None, picture=None) -> int:
    from prg32_construction_kit import deploy

    sdk = Path(os.environ.get("PRG32_SOURCE") or ROOT.parent / "PRG32")
    record = {
        "tool": "tools/deploy_evidence.py", "date": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "kit_commit": commit(ROOT), "prg32_sdk_commit": commit(sdk), "target_kind": kind,
        "evidence": deploy.EVIDENCE[kind], "physical_device": kind == "prg32",
        "address": args.console or args.prg32qt or "qemu", "slot": args.slot, "notes": args.notes,
        "target": {key: probe.get(key) for key in ("identity", "abi", "limits", "fingerprint")} if probe else {},
        "cartridge": {"file": cartridge["name"], **{key: cartridge["metadata"].get(key) for key in ("architecture", "sha256", "bytes")}}
        if cartridge else {},
        "deployment": {key: item.get(key) for key in ("status", "log", "result")} if item else {},
        "screenshot_sha256": hashlib.sha256(picture).hexdigest() if picture else None,
        "checks": checks, "passed": all(row["ok"] for row in checks),
    }
    (args.out / "record.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"{'PASS' if record['passed'] else 'FAIL'}: {args.out / 'record.json'}")
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
