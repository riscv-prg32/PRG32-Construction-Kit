"""Write the kit's software bill of materials (docs/sbom.cdx.json, CycloneDX 1.5; docs/dependencies.md).

    python3 tools/make_sbom.py           # write docs/sbom.cdx.json
    python3 tools/make_sbom.py --check   # fail if it no longer matches the inputs

What is in it, and where it comes from (nothing is downloaded):
- the Python packages of the Docker image, from requirements.lock (version and hashes);
- the browser libraries served from static/vendor/, from VENDOR.json (version,
  license, source and integrity);
- the kit itself.
The file is deterministic (no timestamp; the serial number is derived from the
content), so --check can run in CI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "sbom.cdx.json"
LOCK = ROOT / "requirements.lock"
VENDOR = ROOT / "static" / "vendor" / "VENDOR.json"


def python_components() -> list[dict]:
    components = []
    for block in re.split(r"\n(?=[A-Za-z0-9])", LOCK.read_text(encoding="utf-8")):
        match = re.match(r"([A-Za-z0-9_.\-]+)==([^\s\\]+)", block)
        if not match:
            continue
        name, version = match.groups()
        digests = re.findall(r"--hash=sha256:([0-9a-f]{64})", block)
        components.append({"type": "library", "bom-ref": f"pkg:pypi/{name}@{version}", "name": name,
                           "version": version, "purl": f"pkg:pypi/{name}@{version}",
                           "hashes": [{"alg": "SHA-256", "content": digest} for digest in digests],
                           "properties": [{"name": "prg32:origin", "value": "requirements.lock"}]})
    return components


def vendor_components() -> list[dict]:
    components = []
    for package in json.loads(VENDOR.read_text(encoding="utf-8"))["packages"]:
        name, version = package["name"], package["version"]
        component = {"type": "library", "bom-ref": f"pkg:npm/{name}@{version}", "name": name, "version": version,
                     "purl": f"pkg:npm/{name}@{version}",
                     "licenses": [{"license": {"id": package["license"]}}] if package.get("license") else [],
                     "externalReferences": [{"type": "distribution", "url": package["source"]}],
                     "properties": [{"name": "prg32:origin", "value": "static/vendor/VENDOR.json"}]}
        integrity = package.get("integrity", "")
        if integrity.startswith("sha512-"):
            import base64

            component["hashes"] = [{"alg": "SHA-512", "content": base64.b64decode(integrity[7:]).hex()}]
        components.append(component)
    return components


def sbom() -> dict:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    components = sorted(python_components() + vendor_components(), key=lambda item: item["bom-ref"])
    body = {"bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
            "metadata": {"component": {"type": "application", "bom-ref": "prg32-construction-kit",
                                       "name": "PRG32-Construction-Kit", "version": project["version"],
                                       "licenses": [{"license": {"id": project["license"]["text"]}}]},
                         "tools": {"components": [{"type": "application", "name": "tools/make_sbom.py"}]}},
            "components": components,
            "dependencies": [{"ref": "prg32-construction-kit", "dependsOn": [item["bom-ref"] for item in components]}]}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return {"bomFormat": body.pop("bomFormat"), "specVersion": body.pop("specVersion"),
            "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, 'prg32-construction-kit-sbom:' + digest)}", **body}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(sbom(), indent=1) + "\n"
    if args.check:
        if not OUT.is_file() or OUT.read_text(encoding="utf-8") != text:
            print("docs/sbom.cdx.json is out of date (run python3 tools/make_sbom.py)", file=sys.stderr)
            return 1
        print("docs/sbom.cdx.json is up to date")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(json.loads(text)['components'])} components)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
