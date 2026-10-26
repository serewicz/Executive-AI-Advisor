"""Command-line entry point: ``python -m app.mcp_server``."""

from __future__ import annotations

import argparse

from app.mcp_server.server import create_server


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
    args = parser.parse_args(argv)

    server = create_server()
    if args.transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
