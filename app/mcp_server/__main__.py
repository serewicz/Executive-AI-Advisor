"""Command-line entry point: ``python -m app.mcp_server``."""

from __future__ import annotations

import argparse
import logging
import sys

from app.core.config import settings
from app.mcp_server.audit import AuditHashKeyError, resolve_hash_key
from app.mcp_server.auth import InsecureBindError, StaticTokenVerifier, check_http_bind, is_loopback_host, parse_token_entries
from app.mcp_server.server import create_server

logger = logging.getLogger("eaia.mcp")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the Executive AI Advisor MCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="stdio for desktop clients (default); streamable-http to serve over HTTP.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind address (streamable-http only).")
    parser.add_argument("--port", type=int, default=8765, help="HTTP port (streamable-http only).")
    parser.add_argument(
        "--public-url",
        default=None,
        help="URL clients use to reach this server, e.g. https://eaia.example.org/mcp. "
        "Used in OAuth protected-resource metadata. Defaults to http://<host>:<port>.",
    )
    args = parser.parse_args(argv)

    if args.transport == "stdio":
        create_server(transport="stdio").run("stdio")
        return

    try:
        entries = parse_token_entries(settings.mcp_auth_tokens)
        check_http_bind(args.host, has_tokens=bool(entries), allow_insecure=settings.mcp_allow_insecure_bind)
        hash_key = resolve_hash_key(settings.mcp_audit_hash_key, required=not is_loopback_host(args.host))
    except (InsecureBindError, AuditHashKeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None

    server = create_server(
        transport="http",
        token_verifier=StaticTokenVerifier(entries) if entries else None,
        public_url=args.public_url or f"http://{args.host}:{args.port}",
        audit_hash_key=hash_key,
    )
    server.run("streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
