"""add document upload fields

Revision ID: 20260603_0002
Revises: 20260603_0001
Create Date: 2026-06-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260603_0002"
down_revision: Union[str, None] = "20260603_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("filename", sa.String(length=255), nullable=True))
    op.add_column("documents", sa.Column("file_path", sa.String(length=1024), nullable=True))
    op.add_column(
        "documents",
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status IN ('uploaded', 'parsed', 'chunked', 'embedded', 'indexed', 'failed')",
    )
    op.create_check_constraint(
        "ck_documents_source_type",
        "documents",
        "source_type IN ('sec_filing', 'diligence_report', 'technology_assessment', 'board_material')",
    )
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
