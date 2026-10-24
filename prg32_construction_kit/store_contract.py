"""The shared Store contract (contracts/prg32-store-contract-1.json, docs/store_contract.md).

One machine-readable file says what a PRG32 Store bundle is, what the Cartridge Store
accepts and what its refusals mean. The kit uses it three ways:

- ``validate_manifest``: the manifest it writes must match the contract's JSON Schema
  (checked when a bundle is made, so a bad manifest never becomes a bundle);
- ``validate_bundle``: a bundle is checked like the Store checks it, before anything is
  uploaded, so a publish either happens completely or not at all;
- ``classify``: a Store answer (status + message) becomes a stable code with a
  student-readable message and whether trying again can help.

tests/test_store_contract.py proves the contract agrees with the Store's own code (when a
CartridgeStore checkout is next to the kit) on generated fixture bundles.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Any

CONTRACT_PATH = Path(__file__).resolve().parent.parent / "contracts" / "prg32-store-contract-1.json"


@lru_cache(maxsize=1)
def contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


class ContractViolation(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# --- a small JSON Schema validator (the keywords the contract uses) ---------------------

def _schema_errors(value: Any, schema: dict[str, Any], where: str) -> list[str]:
    errors: list[str] = []
    kind = schema.get("type")
    types = {"object": dict, "array": list, "string": str}
    if kind in types and not isinstance(value, types[kind]):
        return [f"{where} must be a{'n' if kind[0] in 'aeiou' else ''} {kind}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{where} must be {schema['const']}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where} must be one of: {', '.join(map(str, schema['enum']))}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{where} is required")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{where} has characters or a form that is not allowed")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{where} must not be empty")
        for index, item in enumerate(value):
            errors.extend(_schema_errors(item, schema.get("items", {}), f"{where}[{index}]"))
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{where}.{name} is required")
        for name, sub in schema.get("properties", {}).items():
            if name in value:
                errors.extend(_schema_errors(value[name], sub, f"{where}.{name}"))
    return errors


def manifest_errors(manifest: Any) -> list[str]:
    return _schema_errors(manifest, contract()["manifest_schema"], "manifest")


def validate_manifest(manifest: Any) -> None:
    errors = manifest_errors(manifest)
    if errors:
        raise ContractViolation("manifest_invalid", "; ".join(errors))


# --- bundles --------------------------------------------------------------------------

def canonical_architecture(name: str) -> str | None:
    rules = contract()["architectures"]
    key = str(name or "").strip().lower()
    key = rules["aliases"].get(key, key)
    return key if key in rules["canonical"] else None


def _is_image(data: bytes) -> bool:
    return data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff")


def validate_bundle(data: bytes) -> dict[str, Any]:
    """The manifest of a bundle the Store would accept, or ContractViolation(code, message)."""
    if not data.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        raise ContractViolation("not_a_zip", "the bundle is not a zip file")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise ContractViolation("not_a_zip", "the bundle is not a valid zip file") from error
    with archive:
        names = {info.filename for info in archive.infolist() if not info.is_dir()}
        if contract()["bundle"]["manifest"] not in names:
            raise ContractViolation("manifest_missing", "the bundle has no manifest.json")
        try:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise ContractViolation("manifest_invalid", "manifest.json is not UTF-8 JSON") from error
        errors = manifest_errors(manifest)
        if errors:
            code = "unsafe_id_or_version" if any(e.startswith(("manifest.id ", "manifest.version ")) for e in errors) \
                else "bad_architecture" if any(".architectures" in e and ".id" in e for e in errors) \
                else "unsafe_path" if any(e.endswith("not allowed") and (".file" in e or ".assets." in e) for e in errors) \
                else "manifest_invalid"
            raise ContractViolation(code, "; ".join(errors))
        assets = manifest["assets"]
        for key in ("icon", "splash"):
            if key in assets:
                if assets[key] not in names:
                    raise ContractViolation("file_missing", f"the bundle's {key} file is missing")
                if not _is_image(archive.read(assets[key])):
                    raise ContractViolation("bad_image", f"the bundle's {key} must be PNG or JPEG")
        seen: set[str] = set()
        for entry in manifest["architectures"]:
            architecture = canonical_architecture(entry["id"])
            if architecture in seen:
                raise ContractViolation("bad_architecture", f"the architecture {architecture} appears twice")
            seen.add(architecture)
            if entry["file"] not in names:
                raise ContractViolation("file_missing", f"the cartridge file {entry['file']} is missing")
            if archive.read(entry["file"])[:4] != contract()["cartridge_artifact_metadata"]["header"]["magic"].encode():
                raise ContractViolation("bad_cartridge", f"{entry['file']} is not a PRG32 cartridge")
    return manifest


# --- Store answers ----------------------------------------------------------------------

def classify(status: int | None, message: str = "") -> dict[str, Any]:
    """A Store refusal as {code, student_message, retryable}. ``status`` None = no answer (network)."""
    text = str(message or "")
    for rule in contract()["errors"]:
        if rule["status"] != status:
            continue
        if rule["match"] is None or re.search(rule["match"], text, re.IGNORECASE):
            return {"code": rule["code"], "student_message": rule["student_message"], "retryable": rule["retryable"]}
    if status is not None and status >= 500:
        return classify(500)
    return {"code": "unknown", "student_message": "The Store refused the bundle: " + text[:200], "retryable": False}
