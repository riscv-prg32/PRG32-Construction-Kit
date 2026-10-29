"""The PRG32 SDK at the revision the kit is pinned to, as a clean checkout (static/wasm/BUILD.json).

The kit's checks of the SDK (the language index, the upstream patches, the audio sources) must
read the SDK revision the kit claims, not whatever a developer's ``../PRG32`` happens to hold.

``pinned_checkout(source)`` returns ``source`` when it already is that revision with no changes,
else a clean clone of ``source`` at that revision in ``build/pinned-sdk/<revision>`` (made once,
reused after). ``source`` itself is never changed. When ``source`` is not a git checkout (an SDK
copied into an image), it is returned as it is; when it does not have the revision at all,
None says so.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "static" / "wasm" / "BUILD.json"


def pinned_revision() -> str:
    return json.loads(BUILD.read_text())["audio"]["revision"]


def _git(path: Path, *args: str) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, check=True,
                              timeout=120).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def pinned_checkout(source: Path, revision: str | None = None) -> Path | None:
    revision = revision or pinned_revision()
    source = Path(source).resolve()
    if _git(source, "rev-parse", "--is-inside-work-tree") != "true":
        return source
    if _git(source, "rev-parse", "HEAD") == revision and _git(source, "status", "--porcelain", "--untracked-files=no") == "":
        return source
    if _git(source, "cat-file", "-e", revision + "^{commit}") is None:
        return None
    clone = ROOT / "build" / "pinned-sdk" / revision[:12]
    if _git(clone, "rev-parse", "HEAD") != revision:
        clone.parent.mkdir(parents=True, exist_ok=True)
        if not (clone / ".git").is_dir():
            subprocess.run(["git", "clone", "-q", "--no-hardlinks", "--no-checkout", str(source), str(clone)],
                           check=True, capture_output=True, timeout=300)
        subprocess.run(["git", "-C", str(clone), "checkout", "-q", "--force", revision], check=True, capture_output=True,
                       timeout=300)
    return clone
