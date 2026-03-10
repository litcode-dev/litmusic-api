"""add upload status to loops and drone_pads

Revision ID: j9k81f60g7h3
Revises: i8j70e59f6a2
Create Date: 2026-03-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "j9k81f60g7h3"
down_revision = "i8j70e59f6a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE loops ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ready'"
    ))
    op.execute(sa.text(
        "ALTER TABLE drone_pads ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ready'"
    ))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE loops DROP COLUMN IF EXISTS status"))
    op.execute(sa.text("ALTER TABLE drone_pads DROP COLUMN IF EXISTS status"))
