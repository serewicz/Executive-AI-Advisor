"""add document sets

Revision ID: 20260608_0007
Revises: 20260606_0006
Create Date: 2026-06-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "20260608_0007"
down_revision: Union[str, None] = "20260606_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())

    if not inspector.has_table("document_sets"):
        op.create_table(
            "document_sets",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if not inspector.has_table("document_set_documents"):
        op.create_table(
            "document_set_documents",
            sa.Column("document_set_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["document_set_id"], ["document_sets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("document_set_id", "document_id"),
            sa.UniqueConstraint("document_set_id", "document_id", name="uq_document_set_documents"),
        )
        op.create_index(
            op.f("ix_document_set_documents_document_id"),
            "document_set_documents",
            ["document_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_document_set_documents_document_set_id"),
            "document_set_documents",
            ["document_set_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_set_documents_document_set_id"), table_name="document_set_documents")
    op.drop_index(op.f("ix_document_set_documents_document_id"), table_name="document_set_documents")
    op.drop_table("document_set_documents")
    op.drop_table("document_sets")
