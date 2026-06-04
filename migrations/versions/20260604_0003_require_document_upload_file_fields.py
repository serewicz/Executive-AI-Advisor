"""require document upload file fields

Revision ID: 20260604_0003
Revises: 20260603_0002
Create Date: 2026-06-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260604_0003"
down_revision: Union[str, None] = "20260603_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE documents SET filename = title WHERE filename IS NULL")
    op.execute("UPDATE documents SET file_path = '' WHERE file_path IS NULL")
    op.alter_column("documents", "filename", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("documents", "file_path", existing_type=sa.String(length=1024), nullable=False)


def downgrade() -> None:
    op.alter_column("documents", "file_path", existing_type=sa.String(length=1024), nullable=True)
    op.alter_column("documents", "filename", existing_type=sa.String(length=255), nullable=True)
