"""Postgres integration tests for the MCP audit table (ADR 0001).

These run only when EAIA_PG_INTEGRATION_URL points at a database migrated to head:

    alembic upgrade head
    EAIA_PG_INTEGRATION_URL=$DATABASE_URL python -m pytest tests/test_mcp_audit_postgres.py
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.mcp_server import create_server
from app.mcp_server.audit import AuditRecord, DatabaseAuditSink
from app.models.audit import MCPAuditEvent

URL = os.environ.get("EAIA_PG_INTEGRATION_URL")
pytestmark = pytest.mark.skipif(not URL, reason="EAIA_PG_INTEGRATION_URL not set")


@pytest.fixture(scope="module")
def session_factory():
    engine = create_engine(URL)
    yield sessionmaker(bind=engine)
    engine.dispose()


def write_record(session_factory, **overrides):
    record = AuditRecord(
        correlation_id=uuid4(),
        client_id="pytest",
        transport="stdio",
        kind="tool",
        name="search_evidence",
        arguments={"query": {"sha256": "0" * 64, "length": 4}},
        **overrides,
    )
    DatabaseAuditSink(session_factory).write(record)
    return record


def test_database_sink_writes_row(session_factory):
    record = write_record(session_factory, outcome="denied", provider="openai", model="x")
    with session_factory() as db:
        row = db.scalars(select(MCPAuditEvent).where(MCPAuditEvent.correlation_id == record.correlation_id)).one()
    assert (row.client_id, row.outcome, row.provider, row.model) == ("pytest", "denied", "openai", "x")
    assert row.arguments["query"]["length"] == 4


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE mcp_audit_events SET outcome = 'ok' WHERE correlation_id = :cid",
        "DELETE FROM mcp_audit_events WHERE correlation_id = :cid",
        "TRUNCATE mcp_audit_events",
    ],
)
def test_audit_table_is_append_only(session_factory, statement):
    record = write_record(session_factory)
    with session_factory() as db:
        with pytest.raises(DBAPIError, match="append-only"):
            db.execute(text(statement), {"cid": record.correlation_id})
        db.rollback()
        assert db.scalar(
            text("SELECT count(*) FROM mcp_audit_events WHERE correlation_id = :cid"), {"cid": record.correlation_id}
        ) == 1


def test_server_writes_audit_rows_to_database(session_factory):
    from mcp import Client

    server = create_server(session_factory)

    async def scenario():
        async with Client(server) as client:
            return await client.call_tool("list_investigations", {})

    result = asyncio.run(scenario())
    assert result.is_error is False
    with session_factory() as db:
        latest = db.scalars(select(MCPAuditEvent).order_by(MCPAuditEvent.occurred_at.desc()).limit(1)).one()
    assert (latest.name, latest.outcome, latest.kind) == ("list_investigations", "ok", "tool")
