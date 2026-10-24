"""Which Cartridge Stores the kit may send bundles to (docs/adr/0008-store-egress-policy.md).

Publishing makes the *server* open a connection. Without rules, a student
could point it at services that only the server can reach (the school
network, the cloud provider's metadata address, the server itself). So:

1. the Store's origin (``https://host[:port]``) must be on a list set by the
   administrator (``PRG32_STORE_ALLOWED_ORIGINS``);
2. the URL must be plain and unambiguous: https, no user name or password,
   no query or fragment, a valid port, a normal host name;
3. every address the host name resolves to must be public; the upload then
   goes to that checked address, so a later DNS answer cannot redirect it;
4. a Store on a private or loopback address (a classroom LAN, a laptop) needs
   ``PRG32_STORE_TRUSTED_LOCAL=1``, and plain http also needs a
   non-production server.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

# What a student sees for each refusal: short, and never an address or a token.
MESSAGES = {
    "scheme": "The Store address must start with https://.",
    "credentials": "The Store address must not contain a user name or password.",
    "fragment": "The Store address must not contain a # part.",
    "query": "The Store address must not contain a ? part.",
    "port": "The Store address has an invalid port number.",
    "host": "The Store address has an invalid host name.",
    "ambiguous_ip": "Write the Store address as a host name, not as a number.",
    "not_allowed": "This Store is not on the list your teacher approved for publishing.",
    "insecure": "This Store does not use https, so the kit will not send bundles to it here.",
    "resolve": "The Store's host name could not be found.",
    "private_address": "This Store address leads into a private network, so the kit will not send bundles there.",
    "redirect": "The Store answered with a redirect; bundles are only sent to the approved address.",
}

DEFAULT_PORTS = {"https": 443, "http": 80}
_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
# Host names made only of digits, dots and hex: browsers and libraries read these
# as IP addresses in surprising ways (2130706433, 0x7f000001, 0177.0.0.1, 127.1).
_NUMERIC_HOST = re.compile(r"^[0-9a-fx.]+$")
_NUMERIC_LABEL = re.compile(r"^(?:0x[0-9a-f]*|[0-9]+)$")
# Ranges that Python's ipaddress may still call "global" but that are not a public Store.
_NOT_PUBLIC = [ipaddress.ip_network(net) for net in (
    "0.0.0.0/8", "100.64.0.0/10", "192.0.0.0/24", "192.0.2.0/24", "198.18.0.0/15", "198.51.100.0/24",
    "203.0.113.0/24", "240.0.0.0/4", "255.255.255.255/32", "64:ff9b::/96", "64:ff9b:1::/48", "2001:db8::/32",
    "2002::/16", "2001::/32",
)]


class StoreRefused(ValueError):
    """The kit will not send a bundle to this Store; ``reason`` is a short code, the text is student-safe."""

    def __init__(self, reason: str):
        super().__init__(MESSAGES.get(reason, "This Store address is not allowed."))
        self.reason = reason


@dataclass(frozen=True)
class StorePolicy:
    allowed_origins: frozenset[str]
    trusted_local: bool = False
    production: bool = False
    ca_bundle: str | None = None
    connect_timeout: float = 5.0
    read_timeout: float = 30.0
    max_response_bytes: int = 64 * 1024


@dataclass(frozen=True)
class StoreTarget:
    scheme: str
    host: str          # lower-case ASCII host name, or an IP address without brackets
    port: int
    path: str          # path prefix of the Store, without a trailing slash ("" for the root)
    ip_literal: str | None

    @property
    def origin(self) -> str:
        return origin_text(self.scheme, self.host, self.port)

    @property
    def host_header(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return host if self.port == DEFAULT_PORTS[self.scheme] else f"{host}:{self.port}"


def origin_text(scheme: str, host: str, port: int) -> str:
    shown = f"[{host}]" if ":" in host else host
    return f"{scheme}://{shown}" if port == DEFAULT_PORTS[scheme] else f"{scheme}://{shown}:{port}"


def parse(url: str) -> StoreTarget:
    """Check the shape of a Store URL (no allow-list, no DNS)."""
    text = str(url or "").strip()
    if any(ord(ch) < 33 or ord(ch) == 127 for ch in text):
        raise StoreRefused("host")
    parts = urlsplit(text)
    scheme = parts.scheme.lower()
    if scheme not in DEFAULT_PORTS:
        raise StoreRefused("scheme")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise StoreRefused("credentials")
    if parts.fragment or text.endswith("#"):
        raise StoreRefused("fragment")
    if parts.query or "?" in text:
        raise StoreRefused("query")
    try:
        port = parts.port
    except ValueError:
        raise StoreRefused("port") from None
    if port is not None and not 1 <= port <= 65535:
        raise StoreRefused("port")
    host = parts.hostname or ""
    if not host or host.endswith(".") or "%" in host:
        raise StoreRefused("host")
    ip_literal = None
    if parts.netloc.split("@")[-1].startswith("["):
        try:
            ip_literal = str(ipaddress.IPv6Address(host))
        except ValueError:
            raise StoreRefused("host") from None
        host = ip_literal
    elif _NUMERIC_HOST.match(host) and _NUMERIC_LABEL.match(host.split(".")[-1]):
        try:
            address = ipaddress.IPv4Address(host)
        except ValueError:
            raise StoreRefused("ambiguous_ip") from None
        if str(address) != host:
            raise StoreRefused("ambiguous_ip")
        ip_literal = host
    else:
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            raise StoreRefused("host") from None
        if len(host) > 253 or not all(_LABEL.match(label) for label in host.split(".")):
            raise StoreRefused("host")
    path = parts.path.rstrip("/")
    if any(segment in (".", "..") for segment in path.split("/")):
        raise StoreRefused("host")
    return StoreTarget(scheme, host, port or DEFAULT_PORTS[scheme], path, ip_literal)


def check_url(url: str, policy: StorePolicy) -> StoreTarget:
    """Shape, allow-list and https rules. Raises StoreRefused."""
    target = parse(url)
    if target.origin not in policy.allowed_origins:
        raise StoreRefused("not_allowed")
    if target.scheme == "http" and (not policy.trusted_local or policy.production):
        raise StoreRefused("insecure")
    return target


def address_allowed(address: ipaddress.IPv4Address | ipaddress.IPv6Address, trusted_local: bool) -> bool:
    """Public addresses always; loopback and private ones only for a trusted local Store."""
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    if address.is_unspecified or address.is_multicast or address.is_link_local:
        return False
    # Before "reserved": Python files ::1 under the reserved ::/8 block.
    if address.is_loopback:
        return trusted_local
    if address.is_reserved or any(address in network for network in _NOT_PUBLIC if network.version == address.version):
        return False
    if address.is_private:
        return trusted_local
    return address.is_global


def resolve(host: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """All addresses of a host name (tests replace this function)."""
    try:
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError, OSError):
        raise StoreRefused("resolve") from None
    addresses = []
    for *_rest, sockaddr in answers:
        try:
            addresses.append(ipaddress.ip_address(sockaddr[0].split("%")[0]))
        except ValueError:
            continue
    if not addresses:
        raise StoreRefused("resolve")
    return addresses


def choose_address(target: StoreTarget, policy: StorePolicy) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Resolve once; every answer must be allowed (one bad answer refuses the Store)."""
    if target.ip_literal is not None:
        addresses = [ipaddress.ip_address(target.ip_literal)]
    else:
        addresses = resolve(target.host, target.port)
    if not all(address_allowed(address, policy.trusted_local) for address in addresses):
        raise StoreRefused("private_address")
    return addresses[0]


def _origins(values: Any) -> frozenset[str]:
    origins = set()
    for value in values or []:
        try:
            target = parse(value)
        except StoreRefused:
            continue  # a broken entry allows nothing
        if target.path in ("", "/"):
            origins.add(target.origin)
    return frozenset(origins)


def policy_from_config(config: Any) -> StorePolicy:
    """The policy for this server: the explicit allow-list, or the administrator's Store and SSO peer."""
    configured = config.get("STORE_ALLOWED_ORIGINS")
    if configured is None:
        origins = set()
        for key in ("DEFAULT_STORE_URL", "SSO_PEER_URL"):
            if config.get(key):
                try:
                    origins.add(parse(config[key]).origin)
                except StoreRefused:
                    pass
        allowed = frozenset(origins)
    else:
        allowed = _origins(configured)
    return StorePolicy(allowed_origins=allowed, trusted_local=bool(config.get("STORE_TRUSTED_LOCAL")),
                       production=config.get("KIT_ENV") == "production", ca_bundle=config.get("STORE_CA_BUNDLE") or None)
