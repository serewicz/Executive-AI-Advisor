"""add document upload fields

Revision ID: 20260603_0002
Revises: 20260603_0001
Create Date: 2026-06-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260603_0002"
down_revision: Union[str, None] = "20260603_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("documents")}
    constraints = {constraint["name"] for constraint in inspector.get_check_constraints("documents")}

    if "source_type" not in columns:
        op.add_column(
            "documents",
            sa.Column(
                "source_type",
                sa.String(length=100),
                server_default="technology_assessment",
                nullable=False,
            ),
        )
    if "status" not in columns:
        op.add_column(
            "documents",
            sa.Column("status", sa.String(length=50), server_default="uploaded", nullable=False),
        )
    if "classification" not in columns:
        op.add_column(
            "documents",
            sa.Column("classification", sa.String(length=50), server_default="internal", nullable=False),
        )
    if "filename" not in columns:
        op.add_column("documents", sa.Column("filename", sa.String(length=255), nullable=True))
    if "file_path" not in columns:
        op.add_column("documents", sa.Column("file_path", sa.String(length=1024), nullable=True))
    if "uploaded_at" not in columns:
        op.add_column(
            "documents",
            sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )

    if "ck_documents_status" not in constraints:
        op.create_check_constraint(
            "ck_documents_status",
            "documents",
            "status IN ('uploaded', 'parsed', 'chunked', 'embedded', 'indexed', 'failed')",
        )
    if "ck_documents_source_type" not in constraints:
        op.create_check_constraint(
            "ck_documents_source_type",
            "documents",
            "source_type IN ('sec_filing', 'diligence_report', 'technology_assessment', 'board_material')",
        )
    if "ck_documents_classification" not in constraints:
        op.create_check_constraint(
            "ck_documents_classification",
            "documents",
            "classification IN ('public', 'internal', 'confidential', 'restricted')",
        )


def downgrade() -> None:
    op.drop_constraint("ck_documents_classification", "documents", type_="check")
    op.drop_constraint("ck_documents_source_type", "documents", type_="check")
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.drop_column("documents", "uploaded_at")
    op.drop_column("documents", "file_path")
    op.drop_column("documents", "filename")
