"""add document chunk metadata

Revision ID: 20260604_0005
Revises: 20260604_0004
Create Date: 2026-06-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "20260604_0005"
down_revision: Union[str, None] = "20260604_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("document_chunks")}

    if "page_start" not in columns:
        op.add_column(
            "document_chunks",
            sa.Column("page_start", sa.Integer(), server_default="1", nullable=False),
        )
    if "page_end" not in columns:
        op.add_column(
            "document_chunks",
            sa.Column("page_end", sa.Integer(), server_default="1", nullable=False),
        )
    if "chunk_metadata" not in columns:
        op.add_column(
            "document_chunks",
            sa.Column(
                "chunk_metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'{}'::jsonb"),
                nullable=False,
            ),
        )

    op.alter_column("document_chunks", "token_count", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    op.alter_column("document_chunks", "token_count", existing_type=sa.Integer(), nullable=True)
    op.drop_column("document_chunks", "chunk_metadata")
    op.drop_column("document_chunks", "page_end")
    op.drop_column("document_chunks", "page_start")
