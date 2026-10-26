"""The CartridgeStore the kit's cross-repository tests talk to (docs/upstream/README.md §6.1).

The kit and the Store share one account username; the Store keeps its pseudonymous public
handle apart. Until that contract is merged into the canonical Store, the tests check it on a
clean clone of the Store with the kit's patch applied to the clone, never to the Store itself.

``store_source()`` decides, in this order:

1. ``PRG32_CARTRIDGE_STORE_SOURCE`` set: that checkout, as it is (CI checks out its own pin);
2. the Store next to the kit already has the contract (its ``tests/test_shared_identity.py``):
   that checkout, as it is;
3. it has the revision the patch is made against (``PATCH_BASE``): a clean clone in
   ``build/pinned-store/<revision>-shared-identity`` with the patch applied by ``git am``
   (made once, reused after);
4. otherwise the checkout as it is, and the tests show what it does.

The Store next to the kit is only read (``git clone``); nothing is written into it.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADJACENT = ROOT.parent / "CartridgeStore"
PATCH = ROOT / "docs" / "upstream" / "cartridge-store-shared-identity.patch"
PATCH_BASE = "4a3138be6784dc98d32b408df145cc51a9fea683"      # Store main, "Complete GDPR remediation"
CONTRACT_MARKER = Path("tests") / "test_shared_identity.py"


def _git(path: Path, *args: str) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, check=True,
                              timeout=120).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def patched_clone(source: Path) -> Path | None:
    """A clean clone of ``source`` at PATCH_BASE with the shared-identity patch; None if it lacks the revision."""
    if _git(source, "cat-file", "-e", PATCH_BASE + "^{commit}") is None:
        return None
    clone = ROOT / "build" / "pinned-store" / f"{PATCH_BASE[:12]}-shared-identity"
    if (clone / CONTRACT_MARKER).is_file() and _git(clone, "rev-parse", "HEAD~1") == PATCH_BASE \
            and _git(clone, "status", "--porcelain") == "":
        return clone
    clone.parent.mkdir(parents=True, exist_ok=True)
    if not (clone / ".git").is_dir():
        subprocess.run(["git", "clone", "-q", "--no-hardlinks", "--no-checkout", str(source), str(clone)],
                       check=True, capture_output=True, timeout=300)
    _git(clone, "am", "--abort")                            # an earlier run stopped half way
    subprocess.run(["git", "-C", str(clone), "checkout", "-q", "--force", "--detach", PATCH_BASE], check=True,
                   capture_output=True, timeout=300)
    subprocess.run(["git", "-C", str(clone), "clean", "-q", "-fdx"], check=True, capture_output=True, timeout=120)
    # The patch keeps its author and date; the committer is only this clone's.
    subprocess.run(["git", "-C", str(clone), "-c", "user.name=PRG32 kit tests", "-c", "user.email=tests@prg32.invalid",
                    "am", "-q", "--committer-date-is-author-date", str(PATCH)], check=True, capture_output=True,
                   timeout=120)
    return clone


def store_source() -> Path:
    chosen = os.environ.get("PRG32_CARTRIDGE_STORE_SOURCE") or os.environ.get("PRG32_STORE_SOURCE")
    if chosen:
        return Path(chosen)
    if not (ADJACENT / "cartridge_store").is_dir() or (ADJACENT / CONTRACT_MARKER).is_file():
        return ADJACENT
    return patched_clone(ADJACENT) or ADJACENT


if __name__ == "__main__":
    print(store_source())
