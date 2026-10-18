"""Store egress policy (ADR-0008): publishing can reach only approved, public Cartridge Stores.

Audit finding H-01: a signed-in user could make the server POST to any URL
(loopback, school LAN, cloud metadata...). These tests try those targets.
Network traffic only ever goes to servers started by the tests on 127.0.0.1.
"""

from __future__ import annotations

import io
import ipaddress
import json
import logging
import shutil
import ssl
import subprocess
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from prg32_construction_kit import publisher, store_policy
from prg32_construction_kit.store_policy import StorePolicy, StoreRefused

TOKEN = "prg32_super_secret_token_value"


def policy(*origins, trusted_local=False, production=False, **extra):
    return StorePolicy(allowed_origins=frozenset(origins), trusted_local=trusted_local, production=production, **extra)


@pytest.fixture()
def dns(monkeypatch):
    """A fake DNS: host name -> list of addresses."""
    table: dict[str, list[str]] = {}

    def resolve(host, port):
        if host not in table:
            raise StoreRefused("resolve")
        return [ipaddress.ip_address(address) for address in table[host]]

    monkeypatch.setattr(store_policy, "resolve", resolve)
    return table


# --- URL shape and allow-list -------------------------------------------------------

@pytest.mark.parametrize("url, reason", [
    ("file:///etc/passwd", "scheme"),
    ("ftp://store.example.org", "scheme"),
    ("gopher://store.example.org", "scheme"),
    ("https://user:pass@store.example.org", "credentials"),
    ("https://token@store.example.org", "credentials"),
    ("https://store.example.org/#frag", "fragment"),
    ("https://store.example.org/?next=http://evil", "query"),
    ("https://store.example.org:99999", "port"),
    ("https://store.example.org:abc", "port"),
    ("https://store.example.org:0", "port"),
    ("https://", "host"),
    ("https://store.example.org.", "host"),
    ("https://[fe80::1%25eth0]", "host"),
    ("https://2130706433", "ambiguous_ip"),
    ("https://0x7f000001", "ambiguous_ip"),
    ("https://0177.0.0.1", "ambiguous_ip"),
    ("https://127.1", "ambiguous_ip"),
    ("https://0x7f.0.0.1", "ambiguous_ip"),
    ("https://bad_host!.org", "host"),
    ("https://store.example.org\n.evil", "host"),
    ("https://store.evil.org", "not_allowed"),
    ("https://store.example.org:8443", "not_allowed"),  # another port is another origin
    ("http://store.example.org", "not_allowed"),
])
def test_bad_or_unlisted_store_urls_are_refused(url, reason):
    with pytest.raises(StoreRefused) as error:
        store_policy.check_url(url, policy("https://store.example.org"))
    assert error.value.reason == reason


def test_the_configured_https_origin_is_accepted_with_a_path():
    target = store_policy.check_url("https://Store.Example.org/school/", policy("https://store.example.org"))
    assert (target.scheme, target.host, target.port, target.path) == ("https", "store.example.org", 443, "/school")
    assert target.origin == "https://store.example.org"


def test_plain_http_needs_trusted_local_and_not_production():
    origin = "http://store.lan:5080"
    with pytest.raises(StoreRefused) as error:
        store_policy.check_url(origin, policy(origin))
    assert error.value.reason == "insecure"
    with pytest.raises(StoreRefused):
        store_policy.check_url(origin, policy(origin, trusted_local=True, production=True))
    assert store_policy.check_url(origin, policy(origin, trusted_local=True)).port == 5080


def test_default_allow_list_is_the_administrator_store_and_sso_peer():
    config = {"DEFAULT_STORE_URL": "https://store.school.test/", "SSO_PEER_URL": "https://peer.school.test",
              "STORE_ALLOWED_ORIGINS": None, "STORE_TRUSTED_LOCAL": False, "KIT_ENV": "production"}
    assert store_policy.policy_from_config(config).allowed_origins == {"https://store.school.test",
                                                                       "https://peer.school.test"}
    config["STORE_ALLOWED_ORIGINS"] = ["https://a.test", "not a url", "https://b.test:8443/"]
    assert store_policy.policy_from_config(config).allowed_origins == {"https://a.test", "https://b.test:8443"}


# --- destination addresses -----------------------------------------------------------

@pytest.mark.parametrize("address", [
    "127.0.0.1", "127.8.9.10", "::1", "0.0.0.0", "::",
    "10.1.2.3", "172.16.0.5", "192.168.1.20", "fd00::1", "fc12::3",
    "169.254.169.254", "fe80::1", "100.64.0.1",
    "224.0.0.1", "ff02::1", "240.0.0.1", "255.255.255.255",
    "192.0.2.10", "198.51.100.3", "203.0.113.7", "198.18.0.1",
    "::ffff:127.0.0.1", "::ffff:10.0.0.1", "::ffff:169.254.169.254", "64:ff9b::a00:1",
])
def test_non_public_destinations_are_refused(address):
    assert not store_policy.address_allowed(ipaddress.ip_address(address), trusted_local=False)


@pytest.mark.parametrize("address", ["93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946", "1.1.1.1"])
def test_public_destinations_are_allowed(address):
    assert store_policy.address_allowed(ipaddress.ip_address(address), trusted_local=False)


@pytest.mark.parametrize("address", ["169.254.169.254", "fe80::1", "224.0.0.1", "0.0.0.0", "240.0.0.1"])
def test_trusted_local_still_refuses_link_local_multicast_and_reserved(address):
    assert not store_policy.address_allowed(ipaddress.ip_address(address), trusted_local=True)


@pytest.mark.parametrize("address", ["127.0.0.1", "192.168.1.20", "10.0.0.5", "::1", "fd00::1"])
def test_trusted_local_allows_loopback_and_private(address):
    assert store_policy.address_allowed(ipaddress.ip_address(address), trusted_local=True)


@pytest.mark.parametrize("url", ["https://127.0.0.1", "https://[::1]", "https://10.0.0.8", "https://169.254.169.254"])
def test_allow_listed_but_private_ip_literals_are_refused(url):
    """Even an administrator's mistake in the allow-list does not open the internal network."""
    with pytest.raises(StoreRefused) as error:
        store_policy.choose_address(store_policy.check_url(url, policy(url)), policy(url))
    assert error.value.reason == "private_address"


def test_public_name_that_resolves_to_a_private_address_is_refused(dns):
    dns["store.example.org"] = ["93.184.216.34", "10.0.0.7"]  # one bad answer is enough
    rule = policy("https://store.example.org")
    with pytest.raises(StoreRefused) as error:
        store_policy.choose_address(store_policy.check_url("https://store.example.org", rule), rule)
    assert error.value.reason == "private_address"
    dns["store.example.org"] = ["93.184.216.34"]
    chosen = store_policy.choose_address(store_policy.check_url("https://store.example.org", rule), rule)
    assert str(chosen) == "93.184.216.34"


def test_names_that_do_not_resolve_are_refused(dns):
    rule = policy("https://nowhere.example.org")
    with pytest.raises(StoreRefused) as error:
        store_policy.choose_address(store_policy.check_url("https://nowhere.example.org", rule), rule)
    assert error.value.reason == "resolve"


# --- the HTTP transport: pinned address, no redirects, bounded answers -----------------

class FakeStore(BaseHTTPRequestHandler):
    """A tiny Cartridge Store. ``mode`` on the server picks the answer."""

    def log_message(self, *_args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.seen.append({"path": self.path, "host": self.headers.get("Host"),
                                 "authorization": self.headers.get("Authorization"), "body": body})
        mode = self.server.mode
        if mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:9/internal")
            self.end_headers()
            return
        if mode == "huge":
            payload = b"{" + b'"x":"' + b"a" * (200 * 1024) + b'"}'
        elif mode == "html":
            payload = b"<html>internal admin page 10.0.0.1</html>"
        elif mode == "slow":
            threading.Event().wait(2)
            payload = b"{}"
        else:
            payload = json.dumps({"ok": True, "status": "pending", "submission_id": 7, "id": "org.test.game",
                                  "version": "1.0.0", "submitted": [{"architecture": "qemu", "file": "g.prg32"}],
                                  "internal": "secret server detail"}).encode()
        self.send_response(401 if mode == "unauthorized" else 200)
        self.send_header("Content-Type", "text/html" if mode == "html" else "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture()
def store_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeStore)
    server.seen, server.mode = [], "ok"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture()
def bundle(tmp_path):
    path = tmp_path / "game-store-bundle.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", "{}")
    return path


def local_store(store_server, dns, **extra):
    """store.test -> 127.0.0.1 (the test server), allowed only in trusted-local mode."""
    dns["store.test"] = ["127.0.0.1"]
    origin = f"http://store.test:{store_server.server_port}"
    return origin, policy(origin, trusted_local=True, **extra)


def test_publish_connects_to_the_checked_address_with_the_store_host_name(store_server, dns, bundle):
    origin, rule = local_store(store_server, dns)
    result = publisher.publish_bundle(origin + "/", TOKEN, bundle, policy=rule)
    assert result["ok"] is True and result["status_code"] == 200
    seen = store_server.seen[0]
    assert seen["path"] == "/api/publish/bundle"
    assert seen["host"] == f"store.test:{store_server.server_port}"
    assert seen["authorization"] == f"Bearer {TOKEN}"
    assert b'name="bundle"' in seen["body"]
    # Only known Store fields come back; nothing the Store did not promise.
    assert result["response"] == {"ok": True, "status": "pending", "submission_id": 7, "id": "org.test.game",
                                  "version": "1.0.0", "submitted": [{"architecture": "qemu", "file": "g.prg32"}]}


def test_dns_rebinding_cannot_move_the_upload(store_server, dns, bundle, monkeypatch):
    """The name is resolved once; the upload goes to that address even if DNS changes afterwards."""
    origin, rule = local_store(store_server, dns)
    calls = []
    original = store_policy.resolve

    def rebinding(host, port):
        calls.append(host)
        return original(host, port) if len(calls) == 1 else [ipaddress.ip_address("169.254.169.254")]

    monkeypatch.setattr(store_policy, "resolve", rebinding)
    assert publisher.publish_bundle(origin, TOKEN, bundle, policy=rule)["ok"] is True
    assert calls == ["store.test"]


def test_without_trusted_local_the_same_store_is_refused(store_server, dns, bundle):
    origin, _ = local_store(store_server, dns)
    with pytest.raises(StoreRefused):
        publisher.publish_bundle(origin, TOKEN, bundle, policy=policy(origin))
    assert store_server.seen == []


def test_redirects_are_not_followed(store_server, dns, bundle):
    origin, rule = local_store(store_server, dns)
    store_server.mode = "redirect"
    with pytest.raises(StoreRefused) as error:
        publisher.publish_bundle(origin, TOKEN, bundle, policy=rule)
    assert error.value.reason == "redirect"
    assert len(store_server.seen) == 1  # nothing was sent to the redirect target


@pytest.mark.parametrize("mode", ["huge", "html"])
def test_unexpected_answers_are_bounded_and_not_echoed(store_server, dns, bundle, mode):
    origin, rule = local_store(store_server, dns)
    store_server.mode = mode
    result = publisher.publish_bundle(origin, TOKEN, bundle, policy=rule)
    assert result["ok"] is False and result["response"] == {}
    assert "10.0.0.1" not in json.dumps(result) and "aaaa" not in json.dumps(result)


def test_store_refusal_is_reported_as_a_recoverable_error(store_server, dns, bundle):
    origin, rule = local_store(store_server, dns)
    store_server.mode = "unauthorized"
    result = publisher.publish_bundle(origin, TOKEN, bundle, policy=rule)
    assert result["ok"] is False and result["status_code"] == 401
    assert "sign" in result["message"].lower()


def test_slow_stores_time_out(store_server, dns, bundle):
    origin, rule = local_store(store_server, dns, read_timeout=0.5)
    store_server.mode = "slow"
    with pytest.raises(publisher.StorePublishFailed) as error:
        publisher.publish_bundle(origin, TOKEN, bundle, policy=rule)
    assert error.value.reason == "timeout" and TOKEN not in str(error.value)


def test_https_store_is_accepted_with_certificate_checks(tmp_path, dns, bundle):
    """A real TLS connection to the pinned address, verifying the Store's host name."""
    if shutil.which("openssl") is None:
        pytest.skip("openssl is not installed")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    made = subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                           "-subj", "/CN=store.test", "-addext", "subjectAltName=DNS:store.test",
                           "-keyout", str(key), "-out", str(cert)], capture_output=True, check=False)
    if made.returncode != 0:
        pytest.skip("openssl cannot make a test certificate here")
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeStore)
    server.seen, server.mode = [], "ok"
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        dns["store.test"] = ["127.0.0.1"]
        origin = f"https://store.test:{server.server_port}"
        # A school LAN Store with its own CA: HTTPS works even in production with trusted-local.
        rule = policy(origin, trusted_local=True, production=True, ca_bundle=str(cert))
        assert publisher.publish_bundle(origin, TOKEN, bundle, policy=rule)["ok"] is True
        # The certificate is for store.test: a name it does not cover fails verification.
        dns["other.test"] = ["127.0.0.1"]
        other = f"https://other.test:{server.server_port}"
        with pytest.raises(publisher.StorePublishFailed) as error:
            publisher.publish_bundle(other, TOKEN, bundle, policy=policy(other, trusted_local=True, ca_bundle=str(cert)))
        assert error.value.reason == "tls"
    finally:
        server.shutdown()
        server.server_close()


# --- through the API ---------------------------------------------------------------------

def store_bundle_artifact(app, client):
    path = app.config["BUILD_ROOT"] / "bundle.zip"
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", "{}")
    return client.post("/api/artifacts", json={"kind": "store_bundle", "name": "b.zip", "path": str(path)}).get_json()


def audit(client, action="publish"):
    return client.get("/api/admin/audit", query_string={"action": action}).get_json()["events"]


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:22", "http://localhost:5080", "http://[::1]/", "http://192.168.1.1/admin",
    "http://169.254.169.254/latest/meta-data", "http://2130706433/", "file:///etc/passwd",
    "https://user:pw@store.school.test", "https://attacker.example.org",
])
def test_students_cannot_save_profiles_for_unapproved_urls(app, client, url):
    app.config["STORE_ALLOWED_ORIGINS"] = ["https://store.school.test"]
    response = client.post("/api/publish_profiles", json={"name": "x", "store_url": url})
    assert response.status_code == 400
    assert "Store" in response.get_json()["error"]
    profile = client.get("/api/publish_profiles").get_json()["publish_profiles"][0]
    assert client.put(f"/api/publish_profiles/{profile['id']}", json={"store_url": url}).status_code == 400


def test_approved_store_profiles_can_be_saved(app, client):
    app.config["STORE_ALLOWED_ORIGINS"] = ["https://store.school.test"]
    response = client.post("/api/publish_profiles", json={"name": "School", "store_url": "https://store.school.test/"})
    assert response.status_code == 201


def test_publishing_to_a_profile_that_is_no_longer_approved_is_refused_and_audited(app, client, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    app.config["STORE_ALLOWED_ORIGINS"] = ["https://store.school.test"]
    profile = client.post("/api/publish_profiles", json={"name": "School", "store_url": "https://store.school.test",
                                                         "bearer_token": TOKEN}).get_json()
    artifact = store_bundle_artifact(app, client)
    calls = []
    monkeypatch.setattr("prg32_construction_kit.routes.publish_bundle", lambda *args, **kw: calls.append(args))
    app.config["STORE_ALLOWED_ORIGINS"] = ["https://new-store.school.test"]  # the teacher changed the list
    response = client.post("/api/publish", json={"profile_id": profile["id"], "bundle_artifact_id": artifact["id"]})
    assert response.status_code == 400 and response.get_json()["reason"] == "not_allowed"
    assert calls == []
    event = audit(client)[0]
    assert event["outcome"] == "refused" and event["metadata"]["reason"] == "not_allowed"
    everything = response.get_data(as_text=True) + json.dumps(audit(client)) + caplog.text
    assert TOKEN not in everything


def test_publish_errors_never_contain_the_token_or_addresses(app, client, monkeypatch, caplog, dns):
    caplog.set_level(logging.DEBUG)
    app.config["STORE_ALLOWED_ORIGINS"] = ["https://store.school.test"]
    dns["store.school.test"] = ["10.20.30.40"]  # resolves inside the school network
    profile = client.post("/api/publish_profiles", json={"name": "School", "store_url": "https://store.school.test",
                                                         "bearer_token": TOKEN}).get_json()
    artifact = store_bundle_artifact(app, client)
    response = client.post("/api/publish", json={"profile_id": profile["id"], "bundle_artifact_id": artifact["id"]})
    assert response.status_code == 400 and response.get_json()["reason"] == "private_address"
    everything = response.get_data(as_text=True) + json.dumps(audit(client)) + caplog.text
    assert TOKEN not in everything and "10.20.30.40" not in response.get_data(as_text=True)


def test_local_development_store_works_only_when_explicitly_trusted(app, client, store_server, dns):
    dns["store.test"] = ["127.0.0.1"]
    origin = f"http://store.test:{store_server.server_port}"
    app.config.update(STORE_ALLOWED_ORIGINS=[origin], STORE_TRUSTED_LOCAL=False)
    assert client.post("/api/publish_profiles", json={"name": "Dev", "store_url": origin}).status_code == 400
    app.config["STORE_TRUSTED_LOCAL"] = True
    profile = client.post("/api/publish_profiles", json={"name": "Dev", "store_url": origin,
                                                         "bearer_token": TOKEN}).get_json()
    artifact = store_bundle_artifact(app, client)
    response = client.post("/api/publish", json={"profile_id": profile["id"], "bundle_artifact_id": artifact["id"]})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["result"]["response"]["submission_id"] == 7
    assert TOKEN not in response.get_data(as_text=True)
    assert audit(client)[0]["outcome"] == "success"
    app.config["KIT_ENV"] = "production"  # never plain http in production
    response = client.post("/api/publish", json={"profile_id": profile["id"], "bundle_artifact_id": artifact["id"]})
    assert response.status_code == 400 and response.get_json()["reason"] == "insecure"


def test_publish_profile_listing_still_works_for_old_rows(app, client):
    """A profile saved before the policy (now disallowed) is still listed, so a teacher can fix it."""
    app.config["STORE_ALLOWED_ORIGINS"] = ["https://store.school.test"]
    assert client.get("/api/publish_profiles").status_code == 200


def test_bundle_bytes_are_sent_unchanged(store_server, dns, bundle):
    origin, rule = local_store(store_server, dns)
    publisher.publish_bundle(origin, "", bundle, policy=rule)
    seen = store_server.seen[0]
    assert seen["authorization"] is None
    assert bundle.read_bytes() in seen["body"]
    assert zipfile.ZipFile(io.BytesIO(bundle.read_bytes())).namelist() == ["manifest.json"]
