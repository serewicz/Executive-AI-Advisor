"""add mcp audit events

Revision ID: 20261025_0008
Revises: 20260608_0007
Create Date: 2026-10-25

Creates an append-only audit table for MCP tool calls. A trigger rejects
UPDATE, DELETE, and TRUNCATE so application code cannot alter history.
Retention is an operator task; see docs/runbooks/mcp-operations.md.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "20261025_0008"
down_revision: Union[str, None] = "20260608_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if not inspector.has_table("mcp_audit_events"):
        op.create_table(
            "mcp_audit_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("client_id", sa.String(length=128), nullable=False),
            sa.Column("transport", sa.String(length=32), nullable=False),
            sa.Column("kind", sa.String(length=16), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("document_set_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("outcome", sa.String(length=32), nullable=False),
            sa.Column("error_class", sa.String(length=128), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=64), nullable=True),
            sa.Column("model", sa.String(length=128), nullable=True),
            sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_mcp_audit_events_occurred_at", "mcp_audit_events", ["occurred_at"])
        op.create_index("ix_mcp_audit_events_correlation_id", "mcp_audit_events", ["correlation_id"])
        op.create_index("ix_mcp_audit_events_client_id", "mcp_audit_events", ["client_id"])
        op.create_index("ix_mcp_audit_events_document_set_id", "mcp_audit_events", ["document_set_id"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION mcp_audit_events_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'mcp_audit_events is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS mcp_audit_events_no_update_delete ON mcp_audit_events")
    op.execute(
        "CREATE TRIGGER mcp_audit_events_no_update_delete BEFORE UPDATE OR DELETE ON mcp_audit_events "
        "FOR EACH ROW EXECUTE FUNCTION mcp_audit_events_append_only()"
    )
    op.execute("DROP TRIGGER IF EXISTS mcp_audit_events_no_truncate ON mcp_audit_events")
    op.execute(
        "CREATE TRIGGER mcp_audit_events_no_truncate BEFORE TRUNCATE ON mcp_audit_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION mcp_audit_events_append_only()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS mcp_audit_events")
    op.execute("DROP FUNCTION IF EXISTS mcp_audit_events_append_only()")
