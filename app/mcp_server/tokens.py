"""Generate an MCP bearer token: ``python -m app.mcp_server.tokens <label>``.

Prints the token once and the ``MCP_AUTH_TOKENS`` entry to configure. The
token itself is not stored anywhere by this command.
"""

from __future__ import annotations

import argparse
import re
import secrets

from app.mcp_server.auth import hash_token

LABEL_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate an MCP bearer token for one client.")
    parser.add_argument("label", help="Client label shown in rate limits and the audit log, e.g. cursor-tim.")
    args = parser.parse_args(argv)
    if not LABEL_PATTERN.match(args.label):
        parser.error("label must be 1-64 characters: letters, digits, '.', '_' or '-'.")
    token = secrets.token_urlsafe(32)
    print(f"Token (give to the client, shown once): {token}")
    print(f"MCP_AUTH_TOKENS entry: {args.label}:{hash_token(token)}")


if __name__ == "__main__":
    main()
