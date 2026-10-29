# Dependencies, their lock, the SBOM and security updates

## What the kit depends on

| Kind | Declared in | Pinned in | Checked by |
| --- | --- | --- | --- |
| Python packages | `requirements.txt`, `requirements-production.txt` (ranges) | `requirements.lock` (exact versions and the SHA-256 of every file) | the Docker image installs with `pip install --require-hashes -r requirements.lock` |
| Browser libraries | `tools/vendor_assets.py` | `static/vendor/VENDOR.json` (versions, licenses, integrity, file hashes) | `tools/vendor_assets.py --check`, served from `static/vendor/` only (ADR-0012) |
| PRG32 SDK and RISC-V compiler | `Dockerfile` (`PRG32_REF`, toolchain version) | image labels, build provenance; the fixtures record theirs in `tests/fixtures/*/BUILD.json` | CI container job: its test image builds the SDK at `static/wasm/BUILD.json` `audio.revision`, so the debugger and console-check rebuilds compare byte for byte |

`docs/sbom.cdx.json` is the software bill of materials (CycloneDX 1.5): every Python
package of the image and every vendored browser library, with versions and hashes.
It is made from the files above, with no network access, and is the same every time
for the same inputs.

## Changing a dependency

```bash
python3 tools/lock_requirements.py
```

```bash
python3 tools/make_sbom.py
```

```bash
python3 -m pytest -q
```

1. Change the range in `requirements.txt` (or `requirements-production.txt`).
2. Re-lock (needs PyPI), regenerate the SBOM, run the tests.
3. Commit all three files together. CI checks that the lock fits the ranges and that
   the SBOM matches (`quality` job).

## Known vulnerabilities

- **Pull requests:** GitHub's dependency review refuses newly added packages with
  high-severity advisories. It needs the repository's Dependency graph (Settings >
  Code security); while that is off, the same CI job audits the whole
  `requirements.lock` with `pip-audit` instead and warns that the review was skipped.
- **Any time:** run the manual CI job *Known vulnerabilities in the locked packages*
  (`pip-audit` against `requirements.lock`), or locally:

```bash
pip-audit --require-hashes --disable-pip -r requirements.lock
```

- **How often:** at least once a month, and when an advisory names a package in the
  SBOM.
- **What to do with a finding:** read the advisory and decide whether the kit uses the
  affected code. Either way, update to the fixed version (widen the range if needed)
  as above, and write in `release-notes.md` what changed and whether the kit was
  affected. If no fix exists yet, record the finding and its exposure in
  `security.md`.

Example (2026-10-20): `cryptography` 49.0.0 (CVE-2026-69247, PKCS#7 decryption, not
used by the kit) and `pytest` 9.0.2 and older (CVE-2025-71176, local denial of service
through `/tmp`) were updated to 50.0.2 and 9.1.1; the audit then found nothing.

Browser libraries are updated with `tools/vendor_assets.py` (it records the new
integrity values), followed by `tools/service_worker_lock.py` (the cached files
changed) and the SBOM.
