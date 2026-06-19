from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests


def publish_bundle(store_url: str, token: str, bundle_path: Path) -> dict[str, Any]:
    endpoint = urljoin(store_url.rstrip("/") + "/", "api/publish/bundle")
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with bundle_path.open("rb") as fp:
        response = requests.post(endpoint, headers=headers, files={"bundle": (bundle_path.name, fp, "application/zip")}, timeout=30)
    content_type = response.headers.get("content-type", "")
    body: Any
    if "application/json" in content_type:
        try:
            body = response.json()
        except Exception:
            body = response.text
    else:
        body = response.text
    return {
        "ok": 200 <= response.status_code < 300,
        "status_code": response.status_code,
        "endpoint": endpoint,
        "response": body,
    }
