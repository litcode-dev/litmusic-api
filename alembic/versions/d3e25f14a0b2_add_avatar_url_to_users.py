"""add avatar_url to users

Revision ID: d3e25f14a0b2
Revises: c2d14e03f9a1
Create Date: 2026-03-03 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3e25f14a0b2"
down_revision: Union[str, None] = "c2d14e03f9a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
