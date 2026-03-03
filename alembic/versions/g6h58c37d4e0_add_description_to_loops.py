"""add description to loops

Revision ID: g6h58c37d4e0
Revises: f5g47b26c3d9
Create Date: 2026-03-03 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "g6h58c37d4e0"
down_revision: Union[str, None] = "f5g47b26c3d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("loops", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("loops", "description")
