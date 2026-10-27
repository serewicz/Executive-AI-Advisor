"""Bearer-token authentication and bind-address policy for HTTP transport.

Tokens are configured as ``label:sha256hex`` pairs in ``MCP_AUTH_TOKENS``. The
server stores only hashes. The label identifies the client in rate limits and
the audit log. Generate a token with ``python -m app.mcp_server.tokens <label>``.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
from dataclasses import dataclass

from mcp.server.auth.provider import AccessToken

logger = logging.getLogger(__name__)

LOOPBACK_NAMES = {"localhost"}


class InsecureBindError(RuntimeError):
    """Raised when HTTP transport would expose tools without authentication."""


@dataclass(frozen=True)
class TokenEntry:
    label: str
    sha256_hex: str


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def parse_token_entries(raw: str | None) -> list[TokenEntry]:
    """Parse ``label:sha256hex,label2:sha256hex``. Rejects malformed entries."""
    if not raw or not raw.strip():
        return []
    entries: list[TokenEntry] = []
    labels: set[str] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        label, sep, digest = item.partition(":")
        label, digest = label.strip(), digest.strip().lower()
        if not sep or not label or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("MCP_AUTH_TOKENS entries must be 'label:<64 hex sha256>'.")
        if label in labels:
            raise ValueError(f"Duplicate MCP_AUTH_TOKENS label: {label}")
        labels.add(label)
        entries.append(TokenEntry(label=label, sha256_hex=digest))
    return entries


class StaticTokenVerifier:
    """Verifies bearer tokens against configured SHA-256 hashes."""

    def __init__(self, entries: list[TokenEntry]) -> None:
        if not entries:
            raise ValueError("StaticTokenVerifier needs at least one token entry.")
        self._entries = list(entries)

    async def verify_token(self, token: str) -> AccessToken | None:
        candidate = hash_token(token)
        match: TokenEntry | None = None
        # Compare against every entry so timing does not reveal the position of a match.
        for entry in self._entries:
            if hmac.compare_digest(candidate, entry.sha256_hex):
                match = entry
        if match is None:
            return None
        return AccessToken(token="redacted", client_id=match.label, scopes=[])


def is_loopback_host(host: str) -> bool:
    if host.strip().lower() in LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def check_http_bind(host: str, has_tokens: bool, allow_insecure: bool) -> None:
    """Refuse to serve unauthenticated HTTP on a non-loopback address."""
    if has_tokens or is_loopback_host(host):
        if not has_tokens:
            logger.warning(
                "MCP HTTP transport on %s without authentication. Only local processes can connect.", host
            )
        return
    if allow_insecure:
        logger.warning(
            "MCP HTTP transport on %s without authentication because MCP_ALLOW_INSECURE_BIND=true. "
            "Any host that can reach this port can call every tool, including paid model calls.",
            host,
        )
        return
    raise InsecureBindError(
        f"Refusing to serve MCP over HTTP on {host} without authentication. "
        "Set MCP_AUTH_TOKENS (see docs/runbooks/mcp-operations.md) or bind to 127.0.0.1."
    )
