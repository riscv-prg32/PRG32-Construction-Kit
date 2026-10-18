#!/usr/bin/env python3
"""Copy the pinned browser libraries into static/vendor/ (refinement phase 1, ADR-0012).

    python3 tools/vendor_assets.py            # download with npm pack, check, copy, write VENDOR.json
    python3 tools/vendor_assets.py --check    # only check static/vendor against VENDOR.json (no network)

The kit's pages must work offline and under a strict Content Security Policy,
so every library is served from the kit itself. This script is the only place
that downloads them: it runs ``npm pack <name>@<version>`` (the npm registry),
compares each tarball with the integrity hash the registry publishes, copies
only the files the kit uses into ``static/vendor/<name>/<version>/`` together
with the licence, and records names, versions, licences, tarball integrity and
the SHA-256 of every copied file in ``static/vendor/VENDOR.json``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "static" / "vendor"
RECORD = VENDOR / "VENDOR.json"

# name, version, licence, {path in the package: path under static/vendor/<name>/<version>/}
PACKAGES = [
    ("bootstrap", "5.3.3", "MIT", {
        "dist/css/bootstrap.min.css": "css/bootstrap.min.css",
        "dist/js/bootstrap.bundle.min.js": "js/bootstrap.bundle.min.js",
        "LICENSE": "LICENSE",
    }),
    ("bootstrap-icons", "1.11.3", "MIT", {
        "font/bootstrap-icons.min.css": "font/bootstrap-icons.min.css",
        "font/fonts/bootstrap-icons.woff2": "font/fonts/bootstrap-icons.woff2",
        "font/fonts/bootstrap-icons.woff": "font/fonts/bootstrap-icons.woff",
        "LICENSE": "LICENSE",
    }),
    ("jquery", "3.7.1", "MIT", {
        "dist/jquery.min.js": "jquery.min.js",
        "LICENSE.txt": "LICENSE.txt",
    }),
    ("blockly", "11.2.1", "Apache-2.0", {
        "blockly.min.js": "blockly.min.js",
        "media/": "media/",  # icons and sounds Blockly would otherwise fetch from a Google server
    }),
]

# Licence texts a package does not ship in its npm tarball: fetched from the project's
# repository at the same release tag and checked against a pinned SHA-256.
EXTRA_FILES = {
    "blockly": [("https://raw.githubusercontent.com/google/blockly/blockly-v11.2.1/LICENSE", "LICENSE",
                 "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30")],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sri(data: bytes) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()


def registry_integrity(name: str, version: str) -> str:
    return subprocess.run(["npm", "view", f"{name}@{version}", "dist.integrity"], capture_output=True, text=True,
                          check=True).stdout.strip()


def vendor() -> int:
    record: dict = {"schema": "prg32-kit-vendor-1", "packages": []}
    with tempfile.TemporaryDirectory(prefix="prg32-vendor-") as folder:
        work = Path(folder)
        for name, version, licence, files in PACKAGES:
            packed = subprocess.run(["npm", "pack", "--silent", f"{name}@{version}"], cwd=work, capture_output=True,
                                    text=True, check=True).stdout.strip().splitlines()[-1]
            tarball = work / packed
            integrity = sri(tarball.read_bytes())
            published = registry_integrity(name, version)
            if integrity != published:
                print(f"{name}@{version}: tarball integrity {integrity} does not match the registry {published}")
                return 1
            unpacked = work / f"{name}-{version}"
            with tarfile.open(tarball) as archive:
                archive.extractall(unpacked, filter="data")
            package = unpacked / "package"
            target = VENDOR / name / version
            shutil.rmtree(target, ignore_errors=True)
            copied: dict[str, str] = {}
            for source, destination in files.items():
                if source.endswith("/"):
                    for item in sorted((package / source).iterdir()):
                        out = target / destination / item.name
                        out.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(item, out)
                        copied[str(out.relative_to(VENDOR))] = sha256(out)
                else:
                    out = target / destination
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(package / source, out)
                    copied[str(out.relative_to(VENDOR))] = sha256(out)
            for url, destination, expected in EXTRA_FILES.get(name, []):
                out = target / destination
                data = subprocess.run(["curl", "-fsSL", url], capture_output=True, check=True).stdout
                if hashlib.sha256(data).hexdigest() != expected:
                    print(f"{name}: {url} does not have the pinned SHA-256")
                    return 1
                out.write_bytes(data)
                copied[str(out.relative_to(VENDOR))] = expected
            record["packages"].append({
                "name": name, "version": version, "license": licence,
                "source": f"https://registry.npmjs.org/{name}/-/{name}-{version}.tgz",
                "integrity": integrity, "files": copied,
                "extra_sources": [url for url, _destination, _digest in EXTRA_FILES.get(name, [])],
            })
            print(f"{name}@{version}: {len(copied)} files, integrity matches the registry")
    RECORD.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return 0


def check() -> int:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    problems = []
    listed = set()
    for package in record["packages"]:
        for path, digest in package["files"].items():
            listed.add(path)
            file = VENDOR / path
            if not file.is_file() or sha256(file) != digest:
                problems.append(path)
    extra = [str(path.relative_to(VENDOR)) for path in VENDOR.rglob("*")
             if path.is_file() and path != RECORD and str(path.relative_to(VENDOR)) not in listed]
    for path in problems:
        print(f"changed or missing: {path}")
    for path in extra:
        print(f"not in VENDOR.json: {path}")
    print("static/vendor matches VENDOR.json" if not (problems or extra) else "static/vendor does not match")
    return 0 if not (problems or extra) else 1


if __name__ == "__main__":
    raise SystemExit(check() if "--check" in sys.argv else vendor())
