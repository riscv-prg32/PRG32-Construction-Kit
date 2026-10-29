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
# Libraries only the tests use (never served to students): same checks, own record.
TEST_VENDOR = ROOT / "tests" / "vendor"

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
        # Blockly's own menus (Delete block, Undo, ...) in the kit's interface languages (ADR-0027).
        **{f"msg/{code}.js": f"msg/{code}.js" for code in ("it", "es", "fr", "de", "zh-hans")},
    }),
    # The code editor of the IDE (ADR-0013): the classic AMD build, only the editor core,
    # its worker, the codicon font and the C/C++ grammar (no TypeScript/JSON/CSS/HTML services).
    ("monaco-editor", "0.52.2", "MIT", {
        "min/vs/loader.js": "min/vs/loader.js",
        "min/vs/editor/editor.main.js": "min/vs/editor/editor.main.js",
        "min/vs/editor/editor.main.css": "min/vs/editor/editor.main.css",
        "min/vs/base/worker/workerMain.js": "min/vs/base/worker/workerMain.js",
        "min/vs/base/browser/ui/codicons/codicon/codicon.ttf": "min/vs/base/browser/ui/codicons/codicon/codicon.ttf",
        "min/vs/basic-languages/cpp/cpp.js": "min/vs/basic-languages/cpp/cpp.js",
        # Monaco's own menus and messages in the kit's interface languages (ADR-0027).
        **{f"min/vs/nls.messages.{code}.js": f"min/vs/nls.messages.{code}.js"
           for code in ("it", "es", "fr", "de", "zh-cn")},
        "LICENSE": "LICENSE",
        "ThirdPartyNotices.txt": "ThirdPartyNotices.txt",
    }),
    # Direct cartridge deployment to an ESP32-C6 over Web Serial. The bundle
    # includes its pako dependency and is served locally for the strict CSP.
    ("esptool-js", "0.7.0", "Apache-2.0", {
        "bundle.js": "bundle.js",
        "LICENSE": "LICENSE",
    }),
    # Simplified Chinese text (ADR-0027) on computers without a CJK font: regular weight only,
    # in the pieces a browser fetches one by one as the characters on a page need them
    # (unicode-range); only Chinese pages load it. SIL Open Font License 1.1.
    ("@fontsource/noto-sans-sc", "5.3.1", "OFL-1.1", {
        "400.css": "400.css",
        "files/*-400-normal.woff2": "files/",
        "LICENSE": "LICENSE",
    }),
]

TEST_PACKAGES = [
    # Accessibility checks in the browser tests (tests/test_ide_browser.py).
    ("axe-core", "4.10.2", "MPL-2.0", {
        "axe.min.js": "axe.min.js",
        "LICENSE": "LICENSE",
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
    for root, packages in ((VENDOR, PACKAGES), (TEST_VENDOR, TEST_PACKAGES)):
        if vendor_into(root, packages) != 0:
            return 1
    return 0


def vendor_into(root: Path, packages: list) -> int:
    record: dict = {"schema": "prg32-kit-vendor-1", "packages": []}
    with tempfile.TemporaryDirectory(prefix="prg32-vendor-") as folder:
        work = Path(folder)
        for name, version, licence, files in packages:
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
            target = root / name / version
            shutil.rmtree(target, ignore_errors=True)
            copied: dict[str, str] = {}
            for source, destination in files.items():
                if "*" in source:   # a pattern: only the matching files of a folder
                    for item in sorted(package.glob(source)):
                        out = target / destination / item.name
                        out.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(item, out)
                        copied[str(out.relative_to(root))] = sha256(out)
                elif source.endswith("/"):
                    for item in sorted((package / source).iterdir()):
                        out = target / destination / item.name
                        out.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(item, out)
                        copied[str(out.relative_to(root))] = sha256(out)
                else:
                    out = target / destination
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(package / source, out)
                    copied[str(out.relative_to(root))] = sha256(out)
            for url, destination, expected in EXTRA_FILES.get(name, []):
                out = target / destination
                data = subprocess.run(["curl", "-fsSL", url], capture_output=True, check=True).stdout
                if hashlib.sha256(data).hexdigest() != expected:
                    print(f"{name}: {url} does not have the pinned SHA-256")
                    return 1
                out.write_bytes(data)
                copied[str(out.relative_to(root))] = expected
            record["packages"].append({
                "name": name, "version": version, "license": licence,
                "source": f"https://registry.npmjs.org/{name}/-/{name.rsplit('/', 1)[-1]}-{version}.tgz",
                "integrity": integrity, "files": copied,
                "extra_sources": [url for url, _destination, _digest in EXTRA_FILES.get(name, [])],
            })
            print(f"{name}@{version}: {len(copied)} files, integrity matches the registry")
    (root / "VENDOR.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return 0


def check() -> int:
    return max(check_root(VENDOR), check_root(TEST_VENDOR))


def check_root(root: Path) -> int:
    record = json.loads((root / "VENDOR.json").read_text(encoding="utf-8"))
    problems = []
    listed = set()
    for package in record["packages"]:
        for path, digest in package["files"].items():
            listed.add(path)
            file = root / path
            if not file.is_file() or sha256(file) != digest:
                problems.append(path)
    extra = [str(path.relative_to(root)) for path in root.rglob("*")
             if path.is_file() and path.name != "VENDOR.json" and str(path.relative_to(root)) not in listed]
    for path in problems:
        print(f"changed or missing: {path}")
    for path in extra:
        print(f"not in VENDOR.json: {path}")
    where = root.relative_to(ROOT)
    print(f"{where} matches VENDOR.json" if not (problems or extra) else f"{where} does not match VENDOR.json")
    return 0 if not (problems or extra) else 1


if __name__ == "__main__":
    raise SystemExit(check() if "--check" in sys.argv else vendor())
