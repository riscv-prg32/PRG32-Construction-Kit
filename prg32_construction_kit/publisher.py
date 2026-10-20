"""Send a bundle to a Cartridge Store: ``POST <store>/api/publish/bundle`` (multipart field ``bundle``).

Every upload follows the Store egress policy (store_policy.py, ADR-0008):
approved origin, public (or explicitly trusted local) address, connection
pinned to the address that was checked, no redirects, short timeouts and a
small, bounded answer. What comes back to the browser is a short summary with
only the fields CartridgeStore documents; never addresses, raw bodies or tokens.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, ClassVar

import certifi
import urllib3
from flask import current_app, has_app_context

from . import store_contract, store_policy
from .store_policy import StorePolicy, StoreRefused

log = logging.getLogger(__name__)

# Fields of CartridgeStore's publish answer (app.py publish_bundle_request) that a student may see.
SAFE_FIELDS = ("ok", "status", "review_required", "submission_id", "id", "version", "submitted", "error")
STATUS_MESSAGES = {
    401: "The Store needs you to sign in: check the profile's token or single sign-on.",
    403: "The Store does not allow this account to publish.",
    409: "The Store already has this cartridge version.",
    413: "The bundle is too large for the Store.",
}


class StorePublishFailed(Exception):
    """The Store could not be reached or the connection failed; ``reason`` is a short code."""

    MESSAGES: ClassVar[dict[str, str]] = {
        "timeout": "The Store did not answer in time. Try again later.",
        "tls": "The Store's security certificate could not be verified.",
        "connection": "The Store could not be reached. Try again later.",
    }

    def __init__(self, reason: str):
        super().__init__(self.MESSAGES[reason])
        self.reason = reason


def _safe_answer(raw: bytes, content_type: str, limit: int) -> dict[str, Any] | None:
    if len(raw) > limit or "json" not in content_type.lower():
        return None
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(body, dict):
        return None
    safe: dict[str, Any] = {}
    for key in SAFE_FIELDS:
        if key not in body:
            continue
        value = body[key]
        if key == "submitted" and isinstance(value, list):
            value = [{"architecture": str(item.get("architecture", ""))[:40], "file": str(item.get("file", ""))[:120]}
                     for item in value[:16] if isinstance(item, dict)]
        elif isinstance(value, str):
            value = value[:300]
        elif not isinstance(value, (bool, int, float)) and value is not None:
            continue
        safe[key] = value
    return safe


def publish_bundle(store_url: str, token: str, bundle_path: Path, policy: StorePolicy | None = None) -> dict[str, Any]:
    """Upload one bundle. Raises StoreRefused (policy) or StorePublishFailed (network/TLS)."""
    if policy is None:
        if not has_app_context():
            raise StoreRefused("not_allowed")
        policy = store_policy.policy_from_config(current_app.config)
    target = store_policy.check_url(store_url, policy)
    address = store_policy.choose_address(target, policy)
    bundle_path = Path(bundle_path)
    body, content_type = urllib3.encode_multipart_formdata(
        {"bundle": (bundle_path.name, bundle_path.read_bytes(), "application/zip")})
    headers = {"Host": target.host_header, "Content-Type": content_type, "User-Agent": "PRG32-Construction-Kit",
               "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    timeout = urllib3.Timeout(connect=policy.connect_timeout, read=policy.read_timeout)
    # Connect to the address that was checked; TLS still verifies the Store's host name.
    if target.scheme == "https":
        pool: urllib3.HTTPConnectionPool = urllib3.HTTPSConnectionPool(
            str(address), target.port, timeout=timeout, retries=False, cert_reqs="CERT_REQUIRED",
            ca_certs=policy.ca_bundle or certifi.where(), server_hostname=target.host, assert_hostname=target.host)
    else:
        pool = urllib3.HTTPConnectionPool(str(address), target.port, timeout=timeout, retries=False)
    try:
        response = pool.urlopen("POST", target.path + "/api/publish/bundle", body=body, headers=headers,
                                redirect=False, retries=False, preload_content=False, assert_same_host=False)
        try:
            raw = response.read(policy.max_response_bytes + 1, decode_content=True)
        finally:
            response.release_conn()
    except (urllib3.exceptions.ReadTimeoutError, urllib3.exceptions.ConnectTimeoutError, TimeoutError):
        log.warning("Store upload to %s timed out", target.host)
        raise StorePublishFailed("timeout") from None
    except urllib3.exceptions.SSLError:
        log.warning("Store upload to %s failed the TLS check", target.host)
        raise StorePublishFailed("tls") from None
    except (urllib3.exceptions.HTTPError, OSError):
        log.warning("Store upload to %s could not connect", target.host)
        raise StorePublishFailed("connection") from None
    finally:
        pool.close()
    status = response.status
    if 300 <= status < 400:
        raise StoreRefused("redirect")
    answer = _safe_answer(raw, response.headers.get("Content-Type", ""), policy.max_response_bytes)
    ok = 200 <= status < 300 and answer is not None
    if answer is None:
        message = "The Store gave an unexpected answer."
    elif ok:
        message = "The Store received the bundle."
    else:
        message = STATUS_MESSAGES.get(status) or str(answer.get("error") or f"The Store refused the bundle ({status}).")
    result = {"ok": ok, "status_code": status, "store_host": target.host, "message": message, "response": answer or {}}
    if not ok:
        # The contract's stable code for this refusal, and whether trying again can help.
        verdict = store_contract.classify(status, str((answer or {}).get("error") or ""))
        result.update(error_code=verdict["code"], retryable=verdict["retryable"])
    return result
