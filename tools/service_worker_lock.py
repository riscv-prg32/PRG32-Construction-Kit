#!/usr/bin/env python3
"""Keep the service worker's CACHE_NAME in step with the files it caches.

    python3 tools/service_worker_lock.py          # record CACHE_NAME + fingerprint of APP_SHELL
    python3 tools/service_worker_lock.py --check  # exit 1 if a cached file changed but CACHE_NAME did not

Browsers keep the old cache until CACHE_NAME changes (AGENTS.md: bump it when
cached files change). static/service-worker.lock.json records the name and a
SHA-256 over every file in APP_SHELL; tests/test_frontend_offline.py fails when
the files changed and the name did not.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKER = ROOT / "static" / "service-worker.js"
LOCK = ROOT / "static" / "service-worker.lock.json"


def read_worker() -> tuple[str, list[str]]:
    text = WORKER.read_text(encoding="utf-8")
    name = re.search(r"const CACHE_NAME = '([^']+)'", text).group(1)
    shell = re.search(r"const APP_SHELL = \[(.*?)\];", text, re.DOTALL).group(1)
    return name, re.findall(r"'([^']+)'", shell)


def fingerprint(paths: list[str]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.encode() + b"\0" + (ROOT / path.lstrip("/")).read_bytes() + b"\0")
    return digest.hexdigest()


def main() -> int:
    name, paths = read_worker()
    current = {"cache_name": name, "app_shell_sha256": fingerprint(paths)}
    if "--check" in sys.argv:
        recorded = json.loads(LOCK.read_text(encoding="utf-8"))
        if recorded == current:
            print("service worker cache is up to date")
            return 0
        if recorded["cache_name"] == name:
            print(f"Cached files changed but CACHE_NAME is still {name}: bump it, then run this tool.")
        else:
            print("CACHE_NAME was bumped: run python3 tools/service_worker_lock.py to record it.")
        return 1
    LOCK.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
