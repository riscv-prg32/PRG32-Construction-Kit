"""Generate the Store contract fixtures (contracts/prg32-store-contract-1.json, docs/store_contract.md).

    python3 tools/build_contract_fixtures.py          # write tests/fixtures/contract/
    python3 tools/build_contract_fixtures.py --check  # fail if they differ

One valid bundle (the kit's own manifest for the Pong example, with the real Pong
cartridge from tests/fixtures/debug/) and one bundle per way of being refused. Every zip
is byte-for-byte reproducible (fixed order, fixed timestamps). expected.json says, for
each, whether the Store must accept it and which contract code the kit gives.
tests/test_store_contract.py runs both the kit and, when it is checked out next to the
kit, the CartridgeStore's own bundle code on them.
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prg32_construction_kit.packager import project_manifest, write_png_icon  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "contract"
CARTRIDGE = (ROOT / "tests" / "fixtures" / "debug" / "pong.prg32").read_bytes()


def icon_bytes() -> bytes:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "icon.png"
        write_png_icon(path)
        return path.read_bytes()


def zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in files:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name])
    return buffer.getvalue()


def base_manifest() -> dict:
    data = json.loads((ROOT / "examples" / "games" / "pong.json").read_text(encoding="utf-8"))
    project = {**data.get("project", data), "version": 3}
    return project_manifest(project, {"abi": "prg32-construction-kit-game-1.0", "title": project["title"]},
                            [{"id": "esp32c6", "file": "pong-esp32c6.prg32"}, {"id": "qemu", "file": "pong-qemu.prg32"}])


def bundle(manifest: dict | None, extra: dict[str, bytes] | None = None, drop: tuple[str, ...] = ()) -> bytes:
    files = {}
    if manifest is not None:
        files["manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True).encode()
    files.update({"icon.png": icon_bytes(), "pong-esp32c6.prg32": CARTRIDGE, "pong-qemu.prg32": CARTRIDGE})
    files.update(extra or {})
    for name in drop:
        files.pop(name, None)
    return zip_bytes(dict(sorted(files.items())))


def changed(**fields) -> dict:
    manifest = copy.deepcopy(base_manifest())
    manifest.update(fields)
    return manifest


def cases() -> dict[str, tuple[bytes, dict]]:
    """name -> (bundle bytes, expectation)."""
    one = lambda arch, file="pong-qemu.prg32": [{"id": arch, "file": file}]  # noqa: E731
    return {
        "valid": (bundle(base_manifest()), {"accepted": True}),
        "not-a-zip": (b"this is not a zip file at all", {"accepted": False, "kit_code": "not_a_zip"}),
        "no-manifest": (bundle(None), {"accepted": False, "kit_code": "manifest_missing"}),
        "wrong-abi": (bundle(changed(abi="prg32-metadata-0.9")), {"accepted": False, "kit_code": "manifest_invalid"}),
        "unsafe-id": (bundle(changed(id="my game!")), {"accepted": False, "kit_code": "unsafe_id_or_version"}),
        "unsafe-version": (bundle(changed(version="1.0 beta")), {"accepted": False, "kit_code": "unsafe_id_or_version"}),
        "no-architectures": (bundle(changed(architectures=[])), {"accepted": False, "kit_code": "manifest_invalid"}),
        "unknown-architecture": (bundle(changed(architectures=one("gameboy"))),
                                 {"accepted": False, "kit_code": "bad_architecture"}),
        "repeated-architecture": (bundle(changed(architectures=[{"id": "qemu", "file": "pong-qemu.prg32"},
                                                                {"id": "emulator", "file": "pong-esp32c6.prg32"}])),
                                  {"accepted": False, "kit_code": "bad_architecture"}),
        "missing-cartridge": (bundle(base_manifest(), drop=("pong-qemu.prg32",)),
                              {"accepted": False, "kit_code": "file_missing"}),
        "parent-path": (bundle(changed(architectures=one("qemu", "../pong-qemu.prg32"))),
                        {"accepted": False, "kit_code": "unsafe_path"}),
        "icon-not-image": (bundle(base_manifest(), extra={"icon.png": b"GIF89a not allowed"}),
                           {"accepted": False, "kit_code": "bad_image"}),
        "not-a-cartridge": (bundle(base_manifest(), extra={"pong-qemu.prg32": b"hello, not a cartridge"}),
                            {"accepted": False, "kit_code": "bad_cartridge"}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = {}
    stale = []
    for name, (data, expectation) in cases().items():
        expected[name] = expectation
        path = OUT / f"{name}.zip"
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                stale.append(path.name)
        else:
            OUT.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    text = json.dumps(expected, indent=1, sort_keys=True) + "\n"
    if args.check:
        if not (OUT / "expected.json").is_file() or (OUT / "expected.json").read_text() != text:
            stale.append("expected.json")
        if stale:
            print("out of date: " + ", ".join(stale) + " (run python3 tools/build_contract_fixtures.py)", file=sys.stderr)
            return 1
        print("contract fixtures are up to date")
        return 0
    (OUT / "expected.json").write_text(text)
    print(f"Wrote {len(expected)} bundles and expected.json to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
