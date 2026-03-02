"""add thumbnail_s3_key to loops

Revision ID: b1c93d02e5f8
Revises: a3f82b91c4d7
Create Date: 2026-03-02 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c93d02e5f8"
down_revision: Union[str, None] = "a3f82b91c4d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("loops", sa.Column("thumbnail_s3_key", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("loops", "thumbnail_s3_key")
