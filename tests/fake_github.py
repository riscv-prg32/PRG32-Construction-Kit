"""An in-process GitHub for tests/test_github.py: the parts of the REST and Git data APIs the kit uses.

It keeps real Git-like objects (blobs, trees, commits) so a test can look at exactly what the kit
committed, change a repository "from another computer", or move a branch at the worst moment.
"""

from __future__ import annotations

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

APP_CLIENT = "kit-github-app"


def _sha(kind: str, payload) -> str:
    return hashlib.sha1((kind + json.dumps(payload, sort_keys=True, default=str)).encode()).hexdigest()


class FakeGitHub:
    def __init__(self, clock):
        self.clock = clock
        self.objects: dict[str, dict] = {}            # sha -> {"type": blob|tree|commit, ...}
        self.branches: dict[tuple[str, str], str] = {}  # (repository, branch) -> commit sha
        self.tokens: dict[str, float] = {}            # access token -> expires at
        self.refresh_tokens: set[str] = set()
        self.requests: list[tuple[str, str]] = []
        self.verifiers: list[str] = []
        self.revoked: list[str] = []
        self.move_branch_before_update = False
        self.repositories = ["ada/games", "ada/notes"]
        for repository in self.repositories:
            self.commit_files(repository, "main", {"README.md": b"# My games\n"}, "first commit", parents=[])

    # --- objects -----------------------------------------------------------------------------
    def put(self, kind: str, data: dict) -> str:
        sha = _sha(kind, data)
        self.objects[sha] = {"type": kind, **data}
        return sha

    def blob(self, content: bytes) -> str:
        return self.put("blob", {"content": base64.b64encode(content).decode()})

    def tree_from_files(self, files: dict[str, str]) -> str:
        """files: path -> blob sha; returns the root tree."""
        here: dict[str, tuple[str, str]] = {}
        folders: dict[str, dict[str, str]] = {}
        for path, sha in files.items():
            head, _, rest = path.partition("/")
            if rest:
                folders.setdefault(head, {})[rest] = sha
            else:
                here[head] = ("blob", sha)
        for name, inside in folders.items():
            here[name] = ("tree", self.tree_from_files(inside))
        return self.put("tree", {"entries": sorted([name, kind, sha] for name, (kind, sha) in here.items())})

    def files_of(self, tree: str, prefix: str = "") -> dict[str, str]:
        found = {}
        for name, kind, sha in self.objects[tree]["entries"]:
            if kind == "tree":
                found.update(self.files_of(sha, f"{prefix}{name}/"))
            else:
                found[prefix + name] = sha
        return found

    def commit_files(self, repository, branch, contents: dict[str, bytes], message, parents=None) -> str:
        """Commit as another computer would: the folder files given replace what is there."""
        head = self.branches.get((repository, branch))
        files = self.files_of(self.objects[head]["tree"]) if head else {}
        files.update({path: self.blob(content) for path, content in contents.items()})
        tree = self.tree_from_files(files)
        sha = self.put("commit", {"tree": tree, "parents": [head] if parents is None and head else (parents or []),
                                  "message": message, "time": self.clock()})
        self.branches[(repository, branch)] = sha
        return sha

    def folder_files(self, repository, folder, branch="main") -> dict[str, bytes]:
        tree = self.objects[self.branches[(repository, branch)]]["tree"]
        return {path[len(folder) + 1:]: base64.b64decode(self.objects[sha]["content"])
                for path, sha in self.files_of(tree).items() if path.startswith(folder + "/")}

    def _tree_answer(self, sha, recursive):
        if recursive:
            entries = []

            def walk(tree, prefix):
                for name, kind, child in self.objects[tree]["entries"]:
                    entries.append({"path": prefix + name, "type": kind, "sha": child, "mode": "100644"})
                    if kind == "tree":
                        walk(child, prefix + name + "/")
            walk(sha, "")
            return {"sha": sha, "tree": entries, "truncated": False}
        return {"sha": sha, "tree": [{"path": name, "type": kind, "sha": child}
                                     for name, kind, child in self.objects[sha]["entries"]]}

    # --- HTTP --------------------------------------------------------------------------------
    def __call__(self, method, url, headers, body):
        self.requests.append((method, url))
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        if parts.hostname == "github.com" and parts.path == "/login/oauth/access_token":
            return self._token(parse_qs(body.decode()))
        if parts.path.startswith("/applications/") and method == "DELETE":
            self.revoked.append(json.loads(body)["access_token"])
            return 204, {}, b""
        token = (headers.get("Authorization") or "").removeprefix("Bearer ")
        if self.tokens.get(token, 0) < self.clock():
            return 401, {}, b'{"message": "Bad credentials"}'
        payload = json.loads(body) if body else None
        path = parts.path
        if path == "/user":
            return self._ok({"id": 4242, "login": "ada-codes"})
        if path == "/user/installations":
            return self._ok({"installations": [{"id": 7}]})
        if path == "/user/installations/7/repositories":
            return self._ok({"repositories": [{"full_name": name, "default_branch": "main", "private": True}
                                              for name in self.repositories]})
        segments = path.split("/")
        repository = "/".join(segments[2:4])
        rest = segments[4:]
        if rest[:1] == ["branches"]:
            head = self.branches.get((repository, rest[1]))
            if head is None:
                return 404, {}, b"{}"
            return self._ok({"commit": {"sha": head, "commit": {"tree": {"sha": self.objects[head]["tree"]}}}})
        if rest[:2] == ["git", "trees"] and method == "GET":
            return self._ok(self._tree_answer(rest[2], "recursive" in query))
        if rest[:2] == ["git", "blobs"] and method == "GET":
            return self._ok({"sha": rest[2], "content": self.objects[rest[2]]["content"], "encoding": "base64"})
        if rest[:2] == ["git", "blobs"]:
            return self._ok({"sha": self.blob(base64.b64decode(payload["content"]))}, 201)
        if rest[:2] == ["git", "trees"]:
            files = self.files_of(payload["base_tree"])
            for entry in payload["tree"]:
                if entry["sha"] is None:
                    files.pop(entry["path"], None)
                else:
                    files[entry["path"]] = entry["sha"]
            return self._ok({"sha": self.tree_from_files(files)}, 201)
        if rest[:2] == ["git", "commits"]:
            sha = self.put("commit", {"tree": payload["tree"], "parents": payload["parents"],
                                      "message": payload["message"], "time": self.clock()})
            return self._ok({"sha": sha}, 201)
        if rest[:3] == ["git", "refs", "heads"]:
            branch = "/".join(rest[3:])
            if self.move_branch_before_update:      # someone else pushed in between
                self.move_branch_before_update = False
                self.commit_files(repository, branch, {"elsewhere.txt": b"x"}, "pushed elsewhere")
            head = self.branches[(repository, branch)]
            if payload["sha"] != head and head not in self.objects[payload["sha"]]["parents"] and not payload["force"]:
                return 422, {}, b'{"message": "Update is not a fast forward"}'
            self.branches[(repository, branch)] = payload["sha"]
            return self._ok({"object": {"sha": payload["sha"]}})
        if rest == ["commits"]:
            return self._ok(self._history(repository, query["sha"][0], query["path"][0], int(query["per_page"][0])))
        return 404, {}, b'{"message": "Not Found"}'

    def _history(self, repository, branch, folder, limit):
        found, sha = [], self.branches[(repository, branch)]
        while sha and len(found) < limit:
            commit = self.objects[sha]
            parent = commit["parents"][0] if commit["parents"] else None
            mine = {p: s for p, s in self.files_of(commit["tree"]).items() if p.startswith(folder + "/")}
            before = ({p: s for p, s in self.files_of(self.objects[parent]["tree"]).items() if p.startswith(folder + "/")}
                      if parent else {})
            if mine != before:
                found.append({"sha": sha, "html_url": f"https://github.com/{repository}/commit/{sha}",
                              "commit": {"message": commit["message"], "author": {"name": "kit", "date": "2026-10-22"}}})
            sha = parent
        return found

    def _token(self, form):
        if form.get("client_id") != [APP_CLIENT]:
            return 200, {}, b'{"error": "incorrect_client_credentials"}'
        if form.get("grant_type") == ["refresh_token"]:
            if form["refresh_token"][0] not in self.refresh_tokens:
                return 200, {}, b'{"error": "bad_refresh_token"}'
            self.refresh_tokens.discard(form["refresh_token"][0])
        elif form.get("code") != ["good-code"]:
            return 200, {}, b'{"error": "bad_verification_code"}'
        else:
            self.verifiers.append(form.get("code_verifier", [""])[0])
        access, refresh = f"ghu_{len(self.tokens)}", f"ghr_{len(self.tokens)}"
        self.tokens[access] = self.clock() + 28800
        self.refresh_tokens.add(refresh)
        return 200, {}, json.dumps({"access_token": access, "refresh_token": refresh, "expires_in": 28800,
                                    "token_type": "bearer"}).encode()

    @staticmethod
    def _ok(data, status=200):
        return status, {}, json.dumps(data).encode()
