"""Keeping projects in Google Drive or OneDrive (ADR-0019, docs/cloud_storage.md).

Optional: a kit without cloud settings works exactly as before, and guests never use it
(their games stay in the browser). A registered student connects a cloud account on
the Account page, then saves a project there ("push") or takes the cloud copy back
("pull").

How it stays safe and simple:

- **One small interface** (``CloudProvider``): list, load, create, save, delete and
  revoke. ``GoogleDrive`` and ``OneDrive`` implement it; everything else (consent,
  tokens, conflicts, quotas) is shared.
- **Least privilege.** Drive: ``drive.file`` (only files the kit made). OneDrive:
  ``Files.ReadWrite.AppFolder`` (only the kit's app folder) plus ``User.Read`` for the
  account's id. The student ticks a consent box first; the provider asks again.
- **Tokens** are encrypted in the database (a key derived from ``SECRET_KEY`` or
  ``PRG32_CLOUD_TOKEN_KEY``), never sent to the browser and never logged; refreshed when
  they expire; revoked at the provider on disconnect where it offers that (Google).
- **Bounded retries:** reads and conditional writes are tried at most 3 times on
  429/5xx/network errors (0.5 s, 1 s, Retry-After up to 8 s); creating a file is never
  repeated blindly: the next attempt first looks for the file it may already have made.
- **Nothing is overwritten silently**, locally or in the cloud. Each link remembers the
  project version and the cloud revision it last synced. If both sides changed, the
  answer is 409 ``cloud_conflict`` with the choices *copy*, *take remote* and
  *overwrite*; *take remote* and *overwrite* must name the version the student saw, and
  the local version goes into the project's history first.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote, urlencode, urlsplit

import requests
from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session
from sqlalchemy import UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from . import project_format, security
from .db import db, utcnow
from . import settings as site_settings

FLOW_SECONDS = 600
HTTP_TIMEOUT = 20
MAX_BODY_BYTES = project_format.MAX_ARCHIVE_BYTES + 64 * 1024
RETRY_DELAYS = (0.5, 1.0)          # three attempts in all
MAX_RETRY_AFTER = 8.0
REFRESH_MARGIN = 60                # refresh a token that expires within a minute
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


# --- tables -------------------------------------------------------------------

class CloudAccount(db.Model):
    """One connected cloud account per kit user and provider."""
    __tablename__ = "cloud_accounts"
    __table_args__ = (UniqueConstraint("user_id", "provider"),)
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(db.String(32), nullable=False)
    account_id: Mapped[str] = mapped_column(db.String(255), nullable=False)
    account_name: Mapped[str] = mapped_column(db.String(255), nullable=False, default="")
    scopes: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    tokens: Mapped[str] = mapped_column(db.Text, nullable=False, default="")   # encrypted JSON
    needs_reconnect: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)
    connected_at: Mapped[str] = mapped_column(db.String(40), nullable=False, default=utcnow)


class CloudLink(db.Model):
    """A project and the cloud file it was last synced with."""
    __tablename__ = "cloud_links"
    __table_args__ = (UniqueConstraint("user_id", "provider", "project_id"),)
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(db.String(32), nullable=False)
    account_id: Mapped[str] = mapped_column(db.String(255), nullable=False)
    project_id: Mapped[str] = mapped_column(db.String(64), nullable=False)
    file_id: Mapped[str] = mapped_column(db.String(255), nullable=False)
    remote_revision: Mapped[str] = mapped_column(db.String(255), nullable=False)
    content_sha256: Mapped[str] = mapped_column(db.String(64), nullable=False)
    local_version: Mapped[int] = mapped_column(db.Integer, nullable=False)
    synced_at: Mapped[str] = mapped_column(db.String(40), nullable=False, default=utcnow)


# --- errors -------------------------------------------------------------------

class CloudError(Exception):
    """A refusal with a stable code, a message for students and an HTTP status."""

    def __init__(self, code: str, message: str, status: int = 502, retryable: bool = False, **details: Any):
        super().__init__(message)
        self.code, self.status, self.retryable, self.details = code, status, retryable, details


class RemoteChanged(CloudError):
    def __init__(self, revision: str = ""):
        super().__init__("remote_changed", "The cloud copy changed since you last looked at it.", 409,
                         remote_revision=revision)


@dataclass
class RemoteFile:
    file_id: str
    name: str
    revision: str          # Drive: version; OneDrive: eTag
    modified: str = ""
    size: int = 0


# --- HTTP ---------------------------------------------------------------------
# One function, so tests put in-process fake providers behind it.

def _transport(method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, dict[str, str], bytes]:
    response = requests.request(method, url, headers=headers, data=body, timeout=HTTP_TIMEOUT,
                                allow_redirects=False, stream=True)
    data = response.raw.read(MAX_BODY_BYTES + 1, decode_content=True)
    if len(data) > MAX_BODY_BYTES:
        raise CloudError("too_large", "The cloud sent more data than a project can have.", 502)
    return response.status_code, dict(response.headers), data


transport: Callable[..., tuple[int, dict[str, str], bytes]] = _transport
sleep: Callable[[float], None] = time.sleep


def now_seconds() -> float:
    return time.time()


def _allowed(url: str, hosts: tuple[str, ...], suffixes: tuple[str, ...] = ()) -> None:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443) or not (
            host in hosts or any(host.endswith(suffix) for suffix in suffixes)):
        raise CloudError("bad_address", "The kit only talks to the cloud provider's own addresses.", 502)


def _json(data: bytes) -> Any:
    try:
        return json.loads(data or b"null")
    except ValueError:
        return None


# --- providers ----------------------------------------------------------------

class CloudProvider:
    """What the kit needs from a cloud drive. Subclasses fill in the addresses."""

    name = ""
    title = ""
    scopes = ""
    hosts: tuple[str, ...] = ()
    download_suffixes: tuple[str, ...] = ()
    max_upload = project_format.MAX_ARCHIVE_BYTES
    revokes_at_provider = False

    def __init__(self, client_id: str, client_secret: str = "", tenant: str = "common"):
        self.client_id, self.client_secret, self.tenant = client_id, client_secret, tenant

    # OAuth endpoints
    def authorize_endpoint(self) -> str: raise NotImplementedError
    def token_endpoint(self) -> str: raise NotImplementedError
    def authorize_extra(self) -> dict[str, str]: return {}

    # files (``api`` is an Api bound to one account)
    def account(self, api: "Api") -> tuple[str, str]: raise NotImplementedError
    def list(self, api: "Api") -> list[RemoteFile]: raise NotImplementedError
    def metadata(self, api: "Api", file_id: str) -> RemoteFile | None: raise NotImplementedError
    def load(self, api: "Api", file_id: str) -> tuple[RemoteFile, bytes]: raise NotImplementedError
    def find(self, api: "Api", name: str, project_id: str, digest: str) -> RemoteFile | None: raise NotImplementedError
    def create(self, api: "Api", name: str, data: bytes, project_id: str, digest: str) -> RemoteFile: raise NotImplementedError
    def save(self, api: "Api", file_id: str, data: bytes, digest: str, expected_revision: str) -> RemoteFile: raise NotImplementedError
    def delete(self, api: "Api", file_id: str, expected_revision: str) -> None: raise NotImplementedError
    def revoke(self, tokens: dict[str, Any]) -> bool: return False


class GoogleDrive(CloudProvider):
    name, title = "google", "Google Drive"
    scopes = "https://www.googleapis.com/auth/drive.file"
    hosts = ("www.googleapis.com", "oauth2.googleapis.com")
    revokes_at_provider = True
    API = "https://www.googleapis.com/drive/v3"
    UPLOAD = "https://www.googleapis.com/upload/drive/v3"
    FIELDS = "id,name,version,modifiedTime,size,trashed,appProperties"

    def authorize_endpoint(self): return "https://accounts.google.com/o/oauth2/v2/auth"
    def token_endpoint(self): return "https://oauth2.googleapis.com/token"
    def authorize_extra(self): return {"access_type": "offline", "prompt": "consent", "include_granted_scopes": "false"}

    @staticmethod
    def _file(item: dict[str, Any]) -> RemoteFile:
        return RemoteFile(item["id"], item.get("name", ""), str(item.get("version", "")), item.get("modifiedTime", ""),
                          int(item.get("size") or 0))

    def account(self, api):
        user = api.json("GET", f"{self.API}/about?fields=user(permissionId,displayName,emailAddress)")["user"]
        return user["permissionId"], user.get("emailAddress") or user.get("displayName", "")

    def list(self, api):
        query = urlencode({"q": "appProperties has { key='prg32kit' and value='project' } and trashed = false",
                           "fields": f"files({self.FIELDS})", "pageSize": "100", "spaces": "drive"})
        return [self._file(item) for item in api.json("GET", f"{self.API}/files?{query}").get("files", [])]

    def metadata(self, api, file_id):
        status, item = api.call("GET", f"{self.API}/files/{quote(file_id, safe='')}?fields={self.FIELDS}",
                                accept=(200, 404))
        item = _json(item)
        return None if status == 404 or not item or item.get("trashed") else self._file(item)

    def load(self, api, file_id):
        remote = self.metadata(api, file_id)
        if remote is None:
            raise CloudError("remote_missing", "This file is not in your Google Drive any more.", 404)
        _status, data = api.call("GET", f"{self.API}/files/{quote(file_id, safe='')}?alt=media")
        return remote, data

    def find(self, api, name, project_id, digest):
        query = urlencode({"q": f"appProperties has {{ key='prg32_project' and value='{project_id}' }} and "
                                f"appProperties has {{ key='prg32_sha256' and value='{digest}' }} and trashed = false",
                           "fields": f"files({self.FIELDS})", "spaces": "drive"})
        files = api.json("GET", f"{self.API}/files?{query}").get("files", [])
        return self._file(files[0]) if files else None

    def _multipart(self, metadata: dict[str, Any], data: bytes) -> tuple[bytes, str]:
        boundary = "prg32kit" + secrets.token_hex(12)
        body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(metadata)}\r\n"
                f"--{boundary}\r\nContent-Type: application/zip\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
        return body, f"multipart/related; boundary={boundary}"

    def create(self, api, name, data, project_id, digest):
        body, kind = self._multipart({"name": name, "mimeType": "application/zip", "appProperties": {
            "prg32kit": "project", "prg32_project": project_id, "prg32_sha256": digest}}, data)
        return self._file(api.json("POST", f"{self.UPLOAD}/files?uploadType=multipart&fields={self.FIELDS}",
                                   body=body, content_type=kind, retry=False))

    def save(self, api, file_id, data, digest, expected_revision):
        # Drive has no conditional upload: check the version right before writing.
        # The window between the check and the write is documented (ADR-0019).
        current = self.metadata(api, file_id)
        if current is None:
            raise CloudError("remote_missing", "This file is not in your Google Drive any more.", 404)
        if current.revision != expected_revision:
            raise RemoteChanged(current.revision)
        body, kind = self._multipart({"appProperties": {"prg32_sha256": digest}}, data)
        return self._file(api.json("PATCH", f"{self.UPLOAD}/files/{quote(file_id, safe='')}?uploadType=multipart"
                                            f"&fields={self.FIELDS}", body=body, content_type=kind))

    def delete(self, api, file_id, expected_revision):
        current = self.metadata(api, file_id)
        if current is None:
            return
        if current.revision != expected_revision:
            raise RemoteChanged(current.revision)
        # To the Drive trash, so the student can still get it back there.
        api.json("PATCH", f"{self.API}/files/{quote(file_id, safe='')}?fields=id", body=b'{"trashed": true}',
                 content_type="application/json")

    def revoke(self, tokens):
        token = tokens.get("refresh_token") or tokens.get("access_token")
        if not token:
            return False
        url = "https://oauth2.googleapis.com/revoke"
        _allowed(url, self.hosts)
        try:
            status, _headers, _data = transport("POST", url, {"Content-Type": "application/x-www-form-urlencoded"},
                                                urlencode({"token": token}).encode())
        except (requests.RequestException, CloudError):
            return False
        return status == 200


class OneDrive(CloudProvider):
    name, title = "onedrive", "OneDrive"
    scopes = "Files.ReadWrite.AppFolder User.Read offline_access"
    hosts = ("graph.microsoft.com", "login.microsoftonline.com")
    # Graph hands out pre-authenticated download addresses on these hosts.
    download_suffixes = (".1drv.com", ".sharepoint.com", ".livefilestore.com", ".onedrive.com")
    max_upload = 4 * 1024 * 1024    # Graph's simple upload
    API = "https://graph.microsoft.com/v1.0"

    def authorize_endpoint(self): return f"https://login.microsoftonline.com/{quote(self.tenant)}/oauth2/v2.0/authorize"
    def token_endpoint(self): return f"https://login.microsoftonline.com/{quote(self.tenant)}/oauth2/v2.0/token"

    @staticmethod
    def _file(item: dict[str, Any]) -> RemoteFile:
        return RemoteFile(item["id"], item.get("name", ""), str(item.get("eTag", "")),
                          item.get("lastModifiedDateTime", ""), int(item.get("size") or 0))

    def account(self, api):
        me = api.json("GET", f"{self.API}/me?$select=id,userPrincipalName,displayName")
        return me["id"], me.get("userPrincipalName") or me.get("displayName", "")

    def list(self, api):
        items = api.json("GET", f"{self.API}/me/drive/special/approot/children?$top=200").get("value", [])
        return [self._file(item) for item in items
                if "file" in item and item.get("name", "").endswith(project_format.ARCHIVE_SUFFIX)]

    def _item(self, api, url):
        status, item = api.call("GET", url, accept=(200, 404))
        return None if status == 404 else _json(item)

    def metadata(self, api, file_id):
        item = self._item(api, f"{self.API}/me/drive/items/{quote(file_id, safe='')}")
        return self._file(item) if item else None

    def load(self, api, file_id):
        item = self._item(api, f"{self.API}/me/drive/items/{quote(file_id, safe='')}")
        if not item:
            raise CloudError("remote_missing", "This file is not in your OneDrive any more.", 404)
        url = str(item.get("@microsoft.graph.downloadUrl") or "")
        _allowed(url, (), self.download_suffixes)
        _status, data = api.call("GET", url, authorized=False)
        return self._file(item), data

    def find(self, api, name, project_id, digest):
        item = self._item(api, f"{self.API}/me/drive/special/approot:/{quote(name)}")
        if not item:
            return None
        remote, data = self.load(api, item["id"])
        return remote if hashlib.sha256(data).hexdigest() == digest else None

    def _check_size(self, data):
        if len(data) > self.max_upload:
            raise CloudError("too_large", "This project is too big to save in OneDrive from the kit (4 MB).", 413)

    def create(self, api, name, data, project_id, digest):
        self._check_size(data)
        status, answer = api.call("PUT", f"{self.API}/me/drive/special/approot:/{quote(name)}:/content"
                                         "?@microsoft.graph.conflictBehavior=fail", body=data,
                                  content_type="application/zip", accept=(200, 201, 409), retry=False)
        if status == 409:
            raise CloudError("name_taken", "A different file with this name is already in your OneDrive.", 409)
        return self._file(_json(answer))

    def save(self, api, file_id, data, digest, expected_revision):
        self._check_size(data)
        status, answer = api.call("PUT", f"{self.API}/me/drive/items/{quote(file_id, safe='')}/content", body=data,
                                  content_type="application/zip", headers={"If-Match": expected_revision},
                                  accept=(200, 201, 404, 412))
        if status == 404:
            raise CloudError("remote_missing", "This file is not in your OneDrive any more.", 404)
        if status == 412:
            current = self.metadata(api, file_id)
            raise RemoteChanged(current.revision if current else "")
        return self._file(_json(answer))

    def delete(self, api, file_id, expected_revision):
        # To the OneDrive recycle bin, so the student can still get it back there.
        status, _answer = api.call("DELETE", f"{self.API}/me/drive/items/{quote(file_id, safe='')}",
                                   headers={"If-Match": expected_revision}, accept=(204, 404, 412))
        if status == 412:
            current = self.metadata(api, file_id)
            raise RemoteChanged(current.revision if current else "")

    # Microsoft offers no endpoint to revoke one app's refresh token: disconnecting
    # forgets the tokens here, and the student removes the app's permission in their
    # Microsoft account (docs/cloud_storage.md).


PROVIDER_CLASSES = {"google": GoogleDrive, "onedrive": OneDrive}


def configured() -> dict[str, CloudProvider]:
    config = site_settings.view()
    found: dict[str, CloudProvider] = {}
    # A provider needs its app credentials on the server and must not be switched off on the
    # Settings page (CLOUD_*_ENABLED).
    if config.get("CLOUD_GOOGLE_CLIENT_ID") and config.get("CLOUD_GOOGLE_ENABLED"):
        found["google"] = GoogleDrive(config["CLOUD_GOOGLE_CLIENT_ID"], config.get("CLOUD_GOOGLE_CLIENT_SECRET") or "")
    if config.get("CLOUD_ONEDRIVE_CLIENT_ID") and config.get("CLOUD_ONEDRIVE_ENABLED"):
        found["onedrive"] = OneDrive(config["CLOUD_ONEDRIVE_CLIENT_ID"], config.get("CLOUD_ONEDRIVE_CLIENT_SECRET") or "",
                                     config.get("CLOUD_ONEDRIVE_TENANT") or "common")
    return found


def provider_named(name: str) -> CloudProvider:
    item = configured().get(name)
    if item is None:
        raise CloudError("not_configured", "This cloud storage is not set up on this kit.", 404)
    return item


# --- tokens -------------------------------------------------------------------

def _fernet():
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    secret = str(current_app.config.get("CLOUD_TOKEN_KEY") or current_app.config["SECRET_KEY"]).encode()
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"prg32-construction-kit", info=b"cloud-tokens").derive(secret)
    return Fernet(base64.urlsafe_b64encode(key))


def seal(tokens: dict[str, Any]) -> str:
    return _fernet().encrypt(json.dumps(tokens).encode()).decode()


def unseal(sealed: str) -> dict[str, Any] | None:
    from cryptography.fernet import InvalidToken

    try:
        return json.loads(_fernet().decrypt(sealed.encode()))
    except (InvalidToken, ValueError):
        return None   # the key changed: the student connects again


def _token_request(item: CloudProvider, data: dict[str, str]) -> dict[str, Any]:
    url = item.token_endpoint()
    _allowed(url, item.hosts)
    data = {**data, "client_id": item.client_id}
    if item.client_secret:
        data["client_secret"] = item.client_secret
    try:
        status, _headers, body = transport("POST", url, {"Content-Type": "application/x-www-form-urlencoded",
                                                         "Accept": "application/json"}, urlencode(data).encode())
    except requests.RequestException as error:
        raise CloudError("unavailable", f"{item.title} could not be reached. Try again.", 503, retryable=True) from error
    answer = _json(body) or {}
    if status in (400, 401) and answer.get("error") in ("invalid_grant", "unauthorized_client", "invalid_client"):
        raise CloudError("reconnect", f"Your {item.title} connection has ended. Connect it again.", 401)
    if status != 200 or not answer.get("access_token"):
        raise CloudError("unavailable", f"{item.title} did not answer as expected. Try again.", 503, retryable=status >= 500)
    expires_in = int(answer.get("expires_in") or 3600)
    return {"access_token": answer["access_token"], "refresh_token": answer.get("refresh_token", ""),
            "expires_at": now_seconds() + expires_in, "scope": answer.get("scope", item.scopes)}


class Api:
    """Calls one provider's API as one connected account: tokens, refresh, retries."""

    def __init__(self, item: CloudProvider, account: CloudAccount):
        self.item, self.account = item, account
        tokens = unseal(account.tokens) if account.tokens else None
        if tokens is None or account.needs_reconnect:
            raise CloudError("reconnect", f"Connect your {item.title} account again.", 401)
        self.tokens = tokens

    def _refresh(self) -> None:
        if not self.tokens.get("refresh_token"):
            self._ended()
        try:
            fresh = _token_request(self.item, {"grant_type": "refresh_token", "refresh_token": self.tokens["refresh_token"]})
        except CloudError as error:
            if error.code == "reconnect":
                self._ended()
            raise
        fresh["refresh_token"] = fresh["refresh_token"] or self.tokens["refresh_token"]
        self.tokens = fresh
        self.account.tokens = seal(fresh)
        db.session.commit()

    def _ended(self):
        self.account.needs_reconnect = True
        self.account.tokens = ""
        db.session.commit()
        security.record("cloud_token_ended", target_type="cloud", target_id=self.item.name, outcome="refused")
        raise CloudError("reconnect", f"Your {self.item.title} connection has ended. Connect it again.", 401)

    def call(self, method: str, url: str, body: bytes | None = None, content_type: str = "",
             headers: dict[str, str] | None = None, accept: tuple[int, ...] = (200, 201, 204), retry: bool = True,
             authorized: bool = True) -> tuple[int, bytes]:
        if authorized:
            _allowed(url, self.item.hosts)
        refreshed = False
        attempts = len(RETRY_DELAYS) + 1 if retry else 1
        for attempt in range(attempts):
            if authorized and float(self.tokens.get("expires_at") or 0) - REFRESH_MARGIN < now_seconds():
                self._refresh()
            sent = dict(headers or {})
            if authorized:
                sent["Authorization"] = "Bearer " + self.tokens["access_token"]
            if content_type:
                sent["Content-Type"] = content_type
            try:
                status, answer_headers, data = transport(method, url, sent, body)
            except requests.RequestException:
                if attempt + 1 < attempts:
                    sleep(RETRY_DELAYS[attempt])
                    continue
                raise CloudError("unavailable", f"{self.item.title} could not be reached. Nothing was changed there; "
                                                "try again.", 503, retryable=True)
            if status == 401 and authorized and not refreshed:
                refreshed = True
                self._refresh()
                continue
            if status in RETRYABLE_STATUS and attempt + 1 < attempts:
                wait = RETRY_DELAYS[attempt]
                try:
                    wait = min(MAX_RETRY_AFTER, max(wait, float(answer_headers.get("Retry-After", wait))))
                except ValueError:
                    pass
                sleep(wait)
                continue
            if status in accept:
                return status, data
            if status == 401:
                self._ended()
            if status == 403:
                raise CloudError("forbidden", f"{self.item.title} did not allow this. The kit can only use its own "
                                              "files.", 403)
            if status in RETRYABLE_STATUS:
                raise CloudError("unavailable", f"{self.item.title} is busy or down. Try again later.", 503,
                                 retryable=True)
            if status == 413:
                raise CloudError("too_large", "This project is too big for the cloud storage.", 413)
            raise CloudError("unexpected", f"{self.item.title} answered with an error ({status}).", 502)
        raise CloudError("unavailable", f"{self.item.title} could not be reached. Try again.", 503, retryable=True)

    def json(self, method: str, url: str, **options: Any) -> dict[str, Any]:
        _status, data = self.call(method, url, **options)
        answer = _json(data)
        if not isinstance(answer, dict):
            raise CloudError("unexpected", f"{self.item.title} did not answer with JSON.", 502)
        return answer


# --- syncing ------------------------------------------------------------------

def project_archive(project: dict[str, Any]) -> bytes:
    from .routes import _project_children

    sprites, assets = _project_children(project["id"], everyone=True)
    return project_format.export_archive(project, sprites, assets)


def remote_name(project: dict[str, Any], copy: bool = False) -> str:
    stem = project_format.archive_filename(project).removesuffix(project_format.ARCHIVE_SUFFIX)
    suffix = f"-copy-{uuid.uuid4().hex[:6]}" if copy else ""
    return f"{stem}-{project['id']}{suffix}{project_format.ARCHIVE_SUFFIX}"


def remote_changed(item: CloudProvider, api: Api, link: CloudLink, remote: RemoteFile) -> tuple[bool, RemoteFile, bytes | None]:
    """Did the cloud content change since the last sync? A new revision with the same bytes (a rename) did not."""
    if remote.revision == link.remote_revision:
        return False, remote, None
    remote, data = item.load(api, link.file_id)
    return hashlib.sha256(data).hexdigest() != link.content_sha256, remote, data


def _remember(link: CloudLink | None, *, user_id: int, item: CloudProvider, account: CloudAccount, project: dict[str, Any],
              remote: RemoteFile, digest: str, version: int) -> CloudLink:
    account_id = account.account_id
    if link is None:
        link = CloudLink(user_id=user_id, provider=item.name, project_id=project["id"])
    link.account_id, link.file_id, link.remote_revision = account_id, remote.file_id, remote.revision
    link.content_sha256, link.local_version, link.synced_at = digest, version, utcnow()
    db.session.add(link)
    db.session.commit()
    return link


def link_of(user_id: int, provider: str, project_id: str) -> CloudLink | None:
    return db.session.scalar(select(CloudLink).where(CloudLink.user_id == user_id, CloudLink.provider == provider,
                                                     CloudLink.project_id == project_id))


def conflict(remote: RemoteFile, project: dict[str, Any], choices: list[str], code: str = "cloud_conflict",
             message: str = "") -> CloudError:
    return CloudError(code, message or "The project changed here and in the cloud since the last sync. Nothing was "
                                       "overwritten: keep both (copy), take the cloud version, or overwrite the cloud "
                                       "copy.", 409, choices=choices,
                      remote={"file_id": remote.file_id, "revision": remote.revision, "modified": remote.modified,
                              "name": remote.name},
                      local={"version": project.get("version", 0)})


# --- routes -------------------------------------------------------------------

bp = Blueprint("cloud", __name__)


def _principal():
    from .auth import current_principal

    return current_principal()


def _account(item: CloudProvider) -> CloudAccount:
    account = db.session.scalar(select(CloudAccount).where(CloudAccount.user_id == _principal().id,
                                                           CloudAccount.provider == item.name))
    if account is None:
        raise CloudError("not_connected", f"Connect your {item.title} account first (Account page).", 400)
    return account


def _own(project_id: str) -> dict[str, Any]:
    from .routes import can_write, readable

    project = readable("projects", project_id, supervised=False)
    if project is None:
        raise CloudError("not_found", "Project not found", 404)
    if not can_write(project):
        raise CloudError("forbidden", "Only the owner of a project can keep it in the cloud.", 403)
    return project


def _redirect_uri(name: str) -> str:
    base = str(site_settings.get("PUBLIC_URL") or "").rstrip("/")
    path = f"/cloud/{name}/callback"
    return base + path if base else request.host_url.rstrip("/") + path


@bp.errorhandler(CloudError)
def cloud_error(error: CloudError):
    return jsonify({"error": str(error), "code": error.code, "retryable": error.retryable, **error.details}), error.status


@bp.get("/api/cloud")
def api_cloud():
    """Which cloud storages this kit offers and whether this account is connected (never tokens)."""
    principal = _principal()
    rows = {row.provider: row for row in db.session.scalars(select(CloudAccount).where(CloudAccount.user_id == principal.id))}
    providers = []
    for name, item in configured().items():
        row = rows.get(name)
        providers.append({"name": name, "title": item.title, "scopes": item.scopes.split(),
                          "revokes_at_provider": item.revokes_at_provider, "connected": row is not None,
                          "account_name": row.account_name if row else "",
                          "needs_reconnect": bool(row and row.needs_reconnect)})
    return jsonify({"providers": providers})


@bp.post("/api/cloud/<name>/connect")
def api_connect(name: str):
    """Start connecting (Code flow with PKCE). The student must have ticked the consent box."""
    principal = _principal()
    if principal.token_scopes is not None:
        raise CloudError("browser_only", "Connecting a cloud account needs a browser sign-in.", 403)
    item = provider_named(name)
    if (request.get_json(silent=True) or {}).get("consent") is not True:
        raise CloudError("consent_required", "Read what the kit will be allowed to do and tick the box first.", 400)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(32)
    session["cloud_flow"] = {"state": state, "provider": name, "verifier": verifier, "user_id": principal.id,
                             "started": now_seconds()}
    query = {"response_type": "code", "client_id": item.client_id, "redirect_uri": _redirect_uri(name),
             "scope": item.scopes, "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
             **item.authorize_extra()}
    security.record("cloud_consent", target_type="cloud", target_id=name, metadata={"scopes": item.scopes})
    from . import privacy

    privacy.record_notice(principal.id, "cloud", name)   # ADR-0022: the notice was beside the consent box
    return jsonify({"redirect": item.authorize_endpoint() + "?" + urlencode(query)})


def _callback_page(message: str, status: int):
    return render_template("auth_message.html", title="Cloud storage", message=message), status


@bp.get("/cloud/<name>/callback")
def cloud_callback(name: str):
    principal = _principal()
    flow = session.pop("cloud_flow", None)      # works once
    if (not flow or flow.get("state") != request.args.get("state") or flow.get("provider") != name
            or flow.get("user_id") != principal.id):
        return _callback_page("This link is not valid any more. Connect again from the Account page.", 400)
    if now_seconds() - float(flow.get("started", 0)) > FLOW_SECONDS:
        return _callback_page("Connecting took too long. Start again from the Account page.", 400)
    if request.args.get("error"):
        security.record("cloud_connect", target_type="cloud", target_id=name, outcome="refused")
        return _callback_page("Nothing was connected: the permission was not given.", 400)
    try:
        item = provider_named(name)
        tokens = _token_request(item, {"grant_type": "authorization_code", "code": request.args.get("code", ""),
                                       "redirect_uri": _redirect_uri(name), "code_verifier": flow["verifier"]})
        row = db.session.scalar(select(CloudAccount).where(CloudAccount.user_id == principal.id,
                                                           CloudAccount.provider == name))
        probe = CloudAccount(user_id=principal.id, provider=name, account_id="", tokens=seal(tokens))
        account_id, account_name = item.account(Api(item, probe))
    except CloudError as error:
        return _callback_page(str(error), 502 if error.status < 500 else error.status)
    if row is None:
        row = CloudAccount(user_id=principal.id, provider=name)
        db.session.add(row)
    switched = bool(row.account_id) and row.account_id != account_id
    row.account_id, row.account_name, row.scopes = account_id, account_name, tokens.get("scope") or item.scopes
    row.tokens, row.needs_reconnect, row.connected_at = seal(tokens), False, utcnow()
    db.session.commit()
    security.record("cloud_connect", target_type="cloud", target_id=name, metadata={"switched_account": switched})
    return redirect("/account#cloud")


@bp.post("/api/cloud/<name>/disconnect")
def api_disconnect(name: str):
    """Forget the tokens (and revoke them at the provider where possible). Links stay for a later reconnect."""
    item = provider_named(name)
    row = _account(item)
    tokens = unseal(row.tokens) if row.tokens else None
    revoked = bool(tokens) and item.revoke(tokens)
    db.session.delete(row)
    db.session.commit()
    security.record("cloud_disconnect", target_type="cloud", target_id=name, metadata={"revoked_at_provider": revoked})
    return jsonify({"ok": True, "revoked_at_provider": revoked,
                    "note": "" if revoked else f"Also remove the kit's permission in your {item.title} account settings."})


@bp.get("/api/cloud/<name>/files")
def api_files(name: str):
    item = provider_named(name)
    account = _account(item)
    files = item.list(Api(item, account))
    links = {link.file_id: link.project_id for link in db.session.scalars(
        select(CloudLink).where(CloudLink.user_id == _principal().id, CloudLink.provider == name,
                                CloudLink.account_id == account.account_id))}
    return jsonify({"files": [{**vars(remote), "project_id": links.get(remote.file_id, "")} for remote in files]})


@bp.get("/api/projects/<project_id>/cloud")
def api_project_cloud(project_id: str):
    """The project's links, from the kit's records only (no call to the cloud)."""
    project = _own(project_id)
    links = db.session.scalars(select(CloudLink).where(CloudLink.user_id == _principal().id,
                                                       CloudLink.project_id == project_id))
    return jsonify({"links": [{"provider": link.provider, "file_id": link.file_id, "synced_at": link.synced_at,
                               "local_version": link.local_version, "remote_revision": link.remote_revision,
                               "changed_here": link.local_version != project.get("version", 0)} for link in links]})


@bp.post("/api/projects/<project_id>/cloud/<name>/push")
def api_push(project_id: str, name: str):
    """Save the project to the cloud. choice: none, "copy" (a new cloud file) or "overwrite"."""
    from .routes import request_json

    data_in = request_json()
    choice = data_in.get("choice")
    project = _own(project_id)
    item = provider_named(name)
    account = _account(item)
    api = Api(item, account)
    user_id = _principal().id
    data = project_archive(project)
    digest = hashlib.sha256(data).hexdigest()
    version = int(project.get("version") or 0)
    link = link_of(user_id, name, project_id)
    if link is not None and link.account_id != account.account_id and choice != "copy":
        raise CloudError("other_account", f"This project was synced with another {item.title} account. Save it as a "
                                          "new file in this one (copy).", 409, choices=["copy"])
    if link is None or choice == "copy" or link.account_id != account.account_id:
        name_ = remote_name(project, copy=link is not None)
        remote = item.find(api, name_, project_id, digest) or item.create(api, name_, data, project_id, digest)
        _remember(link, user_id=user_id, item=item, account=account, project=project, remote=remote, digest=digest,
                  version=version)
        security.record("cloud_push", target_type="project", target_id=project_id, metadata={"provider": name, "new_file": True})
        return jsonify({"ok": True, "result": "created", "file_id": remote.file_id, "revision": remote.revision})
    remote = item.metadata(api, link.file_id)
    if remote is None:
        raise CloudError("remote_missing", f"The cloud copy is not in your {item.title} any more. Save a new copy.",
                         409, choices=["copy"])
    changed, remote, _data = remote_changed(item, api, link, remote)
    if changed and (choice != "overwrite" or data_in.get("expected_remote_revision") != remote.revision):
        # "overwrite" counts only for the cloud version the student was shown.
        raise conflict(remote, project, ["copy", "take_remote", "overwrite"],
                       message="" if choice != "overwrite" else
                       "The cloud copy changed again since you chose. Look at it and choose again.")
    if not changed and digest == link.content_sha256:
        _remember(link, user_id=user_id, item=item, account=account, project=project, remote=remote, digest=digest,
                  version=version)
        return jsonify({"ok": True, "result": "in_sync", "file_id": remote.file_id, "revision": remote.revision})
    remote = item.save(api, link.file_id, data, digest, remote.revision)
    _remember(link, user_id=user_id, item=item, account=account, project=project, remote=remote, digest=digest,
              version=version)
    security.record("cloud_push", target_type="project", target_id=project_id,
                    metadata={"provider": name, "overwrite": choice == "overwrite"})
    return jsonify({"ok": True, "result": "overwritten" if changed else "saved", "file_id": remote.file_id,
                    "revision": remote.revision})


def _contents(data: bytes) -> dict[str, Any]:
    try:
        return project_format.import_archive(data)
    except project_format.ProjectFormatError as error:
        raise CloudError("bad_file", f"The cloud file is not a PRG32 project: {error}", 422) from error


@bp.post("/api/projects/<project_id>/cloud/<name>/pull")
def api_pull(project_id: str, name: str):
    """Take the cloud version. choice: none, "copy" (a new project) or "take_remote" (with expected_version)."""
    from .db import VersionConflict, restore_project_state
    from .routes import _create_from_contents, _size, public, quota, request_json, restore_plan, save_revision

    data_in = request_json()
    choice = data_in.get("choice")
    project = _own(project_id)
    item = provider_named(name)
    account = _account(item)
    api = Api(item, account)
    user_id = _principal().id
    link = link_of(user_id, name, project_id)
    if link is None:
        raise CloudError("not_linked", "This project is not in the cloud yet: save it there first.", 400)
    if link.account_id != account.account_id:
        raise CloudError("other_account", f"This project was synced with another {item.title} account.", 409,
                         choices=["copy"])
    remote = item.metadata(api, link.file_id)
    if remote is None:
        raise CloudError("remote_missing", f"The cloud copy is not in your {item.title} any more.", 409, choices=[])
    changed, remote, data = remote_changed(item, api, link, remote)
    if choice == "copy":
        if data is None:
            remote, data = item.load(api, link.file_id)
        copy = _create_from_contents(_contents(data), title=f"{project.get('title') or 'Game'} (cloud copy)")
        return jsonify({"ok": True, "result": "copied", "project": public("projects", copy)}), 201
    if not changed:
        _remember(link, user_id=user_id, item=item, account=account, project=project, remote=remote,
                  digest=link.content_sha256, version=link.local_version)
        return jsonify({"ok": True, "result": "nothing_new"})
    version = int(project.get("version") or 0)
    if version != link.local_version:
        if choice != "take_remote":
            raise conflict(remote, project, ["copy", "take_remote", "overwrite"])
        if data_in.get("expected_version") != version:
            raise conflict(remote, project, ["copy", "take_remote", "overwrite"],
                           message="The project changed here again since you chose. Look at it and choose again.")
    contents = _contents(data)
    fields = contents["project"]
    quota(adding_bytes=_size(contents) - _size(project))
    save_revision(project, "cloud")     # the local version stays in the project's history
    plan = restore_plan({"child_ids": {}}, contents, project_id)
    try:
        updated = restore_project_state(
            project_id, {key: fields[key] for key in ("title", "description", "author", "tags", "blocks_json", "game_json")},
            plan, new_owner_id=project.get("owner_id"), expected_version=version)
    except VersionConflict:
        raise conflict(remote, project, ["copy", "take_remote", "overwrite"],
                       message="The project was saved here while taking the cloud version. Nothing was changed.") from None
    if updated is None:      # deleted for good meanwhile
        raise CloudError("not_found", "Project not found", 404)
    _remember(link, user_id=user_id, item=item, account=account, project=updated, remote=remote,
              digest=hashlib.sha256(data).hexdigest(), version=int(updated["version"]))
    security.record("cloud_pull", target_type="project", target_id=project_id,
                    metadata={"provider": name, "replaced_local_changes": choice == "take_remote"})
    return jsonify({"ok": True, "result": "taken", "project": public("projects", updated)})


@bp.post("/api/cloud/<name>/files/<file_id>/open")
def api_open(name: str, file_id: str):
    """Make a new project from a cloud file (for example one saved from another kit or computer)."""
    from .routes import _create_from_contents, public

    item = provider_named(name)
    account = _account(item)
    api = Api(item, account)
    remote, data = item.load(api, file_id)
    project = _create_from_contents(_contents(data))
    user_id = _principal().id
    already = db.session.scalar(select(CloudLink).where(CloudLink.user_id == user_id, CloudLink.provider == name,
                                                        CloudLink.account_id == account.account_id,
                                                        CloudLink.file_id == file_id))
    if already is None:   # one file is linked to one project at most
        _remember(None, user_id=user_id, item=item, account=account, project=project, remote=remote,
                  digest=hashlib.sha256(data).hexdigest(), version=int(project.get("version") or 0))
    return jsonify({"ok": True, "project": public("projects", project), "linked": already is None}), 201


@bp.delete("/api/cloud/<name>/files/<file_id>")
def api_delete_file(name: str, file_id: str):
    """Move a cloud file to the provider's trash. ``revision`` must be the one the student saw."""
    item = provider_named(name)
    account = _account(item)
    revision = str(request.args.get("revision") or "")
    if not revision:
        raise CloudError("revision_required", "Say which version of the file to delete.", 400)
    item.delete(Api(item, account), file_id, revision)
    for link in db.session.scalars(select(CloudLink).where(CloudLink.user_id == _principal().id,
                                                           CloudLink.provider == name, CloudLink.file_id == file_id)):
        db.session.delete(link)
    db.session.commit()
    security.record("cloud_delete", target_type="cloud", target_id=name)
    return jsonify({"ok": True, "trashed": True})


def init_app(app) -> None:
    app.register_blueprint(bp)
