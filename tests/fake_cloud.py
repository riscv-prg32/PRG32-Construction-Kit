"""In-process Google Drive and OneDrive (Microsoft Graph), just enough of each for the kit.

They behave like the real services where it matters to the kit: OAuth tokens that
expire and can be revoked, Drive's ``version`` and ``appProperties`` (no conditional
upload), Graph's ``eTag`` with ``If-Match`` (412), name conflicts (409), the app-folder
and pre-authenticated download addresses, trash/recycle bin. They can also fail: an
outage for the next N requests, a dropped connection, or a write that is stored but
answered with an error.
"""

from __future__ import annotations

import json
import secrets
from urllib.parse import parse_qs, unquote, urlsplit

import requests


class FakeCloud:
    def __init__(self, provider: str, clock):
        self.provider = provider
        self.clock = clock                  # a function: the current time in seconds
        self.files: dict[str, dict] = {}
        self.access: dict[str, float] = {}  # access token -> expiry
        self.refresh: set[str] = set()
        self.account = {"id": "acct-1", "name": "ada@school.test"}
        self.outage = 0                     # answer the next N API requests with 503
        self.drop = 0                       # drop the next N connections
        self.store_then_fail = False        # store the next write, then answer 503
        self.token_lifetime = 3600
        self.revoked: list[str] = []
        self.log: list[tuple[str, str, dict]] = []
        self._next = 0

    # --- helpers ----------------------------------------------------------------
    def new_id(self) -> str:
        self._next += 1
        return f"file{self._next}"

    def tokens(self) -> dict:
        access, refresh = "at-" + secrets.token_hex(8), "rt-" + secrets.token_hex(8)
        self.access[access] = self.clock() + self.token_lifetime
        self.refresh.add(refresh)
        return {"access_token": access, "refresh_token": refresh, "expires_in": self.token_lifetime,
                "token_type": "Bearer", "scope": "granted"}

    def expire_tokens(self) -> None:
        for token in self.access:
            self.access[token] = 0

    def revoke_refresh_tokens(self) -> None:
        self.refresh.clear()

    def revision(self, item: dict) -> str:
        return str(item["version"]) if self.provider == "google" else f'"{{{item["id"]}}},{item["version"]}"'

    def edit_elsewhere(self, file_id: str, data: bytes | None = None, rename: str | None = None) -> None:
        """Somebody changes the file in the cloud (another computer, the provider's web page)."""
        item = self.files[file_id]
        if data is not None:
            item["data"] = data
        if rename is not None:
            item["name"] = rename
        item["version"] += 1

    def live_files(self) -> list[dict]:
        return [item for item in self.files.values() if not item["trashed"]]

    @staticmethod
    def answer(status: int, body=None, headers=None):
        data = body if isinstance(body, bytes) else (json.dumps(body).encode() if body is not None else b"")
        return status, headers or {}, data

    # --- the transport the kit calls ---------------------------------------------
    def __call__(self, method: str, url: str, headers: dict, body: bytes | None):
        self.log.append((method, url, dict(headers)))
        if self.drop:
            self.drop -= 1
            raise requests.ConnectionError("connection dropped")
        parts = urlsplit(url)
        if parts.path.endswith("/token"):
            return self.token_endpoint(body)
        if parts.path == "/revoke":
            token = parse_qs(body.decode())["token"][0]
            self.refresh.discard(token)
            self.access.pop(token, None)
            self.revoked.append(token)
            return self.answer(200, {})
        if parts.hostname.endswith(".1drv.com"):
            item = self.files.get(parts.path.rsplit("/", 1)[-1])
            return self.answer(200, item["data"]) if item else self.answer(404, {})
        if self.outage:
            self.outage -= 1
            return self.answer(503, {"error": "busy"}, {"Retry-After": "1"})
        token = headers.get("Authorization", "").removeprefix("Bearer ")
        if self.access.get(token, 0) <= self.clock():
            return self.answer(401, {"error": "invalid_token"})
        handler = self.google if self.provider == "google" else self.graph
        status, answer_headers, data = handler(method, parts, headers, body)
        if self.store_then_fail and method in ("POST", "PUT", "PATCH"):
            self.store_then_fail = False
            return self.answer(503, {"error": "timeout after storing"})
        return status, answer_headers, data

    def token_endpoint(self, body: bytes):
        form = {key: values[0] for key, values in parse_qs(body.decode()).items()}
        if form.get("grant_type") == "authorization_code":
            if form.get("code") != "good-code" or not form.get("code_verifier"):
                return self.answer(400, {"error": "invalid_grant"})
            return self.answer(200, self.tokens())
        if form.get("grant_type") == "refresh_token":
            if form.get("refresh_token") not in self.refresh:
                return self.answer(400, {"error": "invalid_grant"})
            self.refresh.discard(form["refresh_token"])
            return self.answer(200, self.tokens())
        return self.answer(400, {"error": "unsupported_grant_type"})

    # --- Google Drive v3 --------------------------------------------------------------
    def drive_item(self, item: dict) -> dict:
        return {"id": item["id"], "name": item["name"], "version": str(item["version"]), "size": str(len(item["data"])),
                "modifiedTime": "2026-10-20T10:00:00Z", "trashed": item["trashed"], "appProperties": item["props"]}

    def google(self, method, parts, headers, body):
        query = {key: values[0] for key, values in parse_qs(parts.query).items()}
        path = parts.path
        if path == "/drive/v3/about":
            return self.answer(200, {"user": {"permissionId": self.account["id"], "emailAddress": self.account["name"]}})
        if path == "/drive/v3/files" and method == "GET":
            wanted = query.get("q", "")
            found = [item for item in self.live_files() if item["props"].get("prg32kit") == "project"]
            for key in ("prg32_project", "prg32_sha256"):
                marker = f"key='{key}' and value='"
                if marker in wanted:
                    value = wanted.split(marker, 1)[1].split("'", 1)[0]
                    found = [item for item in found if item["props"].get(key) == value]
            return self.answer(200, {"files": [self.drive_item(item) for item in found]})
        if path.startswith("/drive/v3/files/"):
            item = self.files.get(unquote(path.rsplit("/", 1)[-1]))
            if item is None:
                return self.answer(404, {"error": "notFound"})
            if method == "GET":
                return self.answer(200, item["data"] if query.get("alt") == "media" else self.drive_item(item))
            if method == "PATCH":
                item["trashed"] = bool(json.loads(body).get("trashed"))
                return self.answer(200, {"id": item["id"]})
        if path == "/upload/drive/v3/files" and method == "POST":
            metadata, data = self.multipart(headers, body)
            item = {"id": self.new_id(), "name": metadata["name"], "data": data, "version": 1, "trashed": False,
                    "props": dict(metadata.get("appProperties", {}))}
            self.files[item["id"]] = item
            return self.answer(200, self.drive_item(item))
        if path.startswith("/upload/drive/v3/files/") and method == "PATCH":
            item = self.files.get(unquote(path.rsplit("/", 1)[-1]))
            if item is None:
                return self.answer(404, {"error": "notFound"})
            metadata, data = self.multipart(headers, body)
            item["data"], item["version"] = data, item["version"] + 1
            item["props"].update(metadata.get("appProperties", {}))
            return self.answer(200, self.drive_item(item))
        return self.answer(400, {"error": f"fake drive does not know {method} {path}"})

    @staticmethod
    def multipart(headers, body):
        boundary = headers["Content-Type"].split("boundary=", 1)[1].encode()
        parts = body.split(b"--" + boundary)
        metadata = json.loads(parts[1].split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n", 1)[0])
        data = parts[2].split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n", 1)[0]
        return metadata, data

    # --- Microsoft Graph (OneDrive app folder) -----------------------------------------
    def graph_item(self, item: dict) -> dict:
        return {"id": item["id"], "name": item["name"], "eTag": self.revision(item), "size": len(item["data"]),
                "lastModifiedDateTime": "2026-10-20T10:00:00Z", "file": {"mimeType": "application/zip"},
                "@microsoft.graph.downloadUrl": f"https://public.files.1drv.com/dl/{item['id']}"}

    def graph(self, method, parts, headers, body):
        path = unquote(parts.path).removeprefix("/v1.0")
        if path == "/me":
            return self.answer(200, {"id": self.account["id"], "userPrincipalName": self.account["name"]})
        if path == "/me/drive/special/approot/children":
            return self.answer(200, {"value": [self.graph_item(item) for item in self.live_files()]})
        if path.startswith("/me/drive/special/approot:/"):
            name = path.removeprefix("/me/drive/special/approot:/").removesuffix(":/content")
            existing = next((item for item in self.live_files() if item["name"] == name), None)
            if method == "GET":
                return self.answer(200, self.graph_item(existing)) if existing else self.answer(404, {})
            if method == "PUT":
                if existing is not None:
                    return self.answer(409, {"error": {"code": "nameAlreadyExists"}})
                item = {"id": self.new_id(), "name": name, "data": body, "version": 1, "trashed": False, "props": {}}
                self.files[item["id"]] = item
                return self.answer(201, self.graph_item(item))
        if path.startswith("/me/drive/items/"):
            file_id = path.removeprefix("/me/drive/items/").removesuffix("/content")
            item = self.files.get(file_id)
            if item is None or item["trashed"]:
                return self.answer(404, {"error": {"code": "itemNotFound"}})
            if "If-Match" in headers and headers["If-Match"] != self.revision(item):
                return self.answer(412, {"error": {"code": "resourceModified"}})
            if method == "GET":
                return self.answer(200, self.graph_item(item))
            if method == "PUT":
                item["data"], item["version"] = body, item["version"] + 1
                return self.answer(200, self.graph_item(item))
            if method == "DELETE":
                item["trashed"] = True     # the recycle bin
                return self.answer(204)
        return self.answer(400, {"error": f"fake graph does not know {method} {path}"})
