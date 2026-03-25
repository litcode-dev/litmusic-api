"""add drone pad categories

Revision ID: l1m03h82i9j5
Revises: k0l92g71h8i4
Create Date: 2026-03-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "l1m03h82i9j5"
down_revision = "k0l92g71h8i4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS drone_pad_categories (
            id UUID PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            created_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))
    op.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_drone_pad_categories_name ON drone_pad_categories (name)"))

    op.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE drone_pads
                ADD COLUMN category_id UUID REFERENCES drone_pad_categories(id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_column THEN null;
        END $$
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_drone_pads_category_id ON drone_pads (category_id)"))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_drone_pads_category_id"))
    op.execute(sa.text("ALTER TABLE drone_pads DROP COLUMN IF EXISTS category_id"))

    op.execute(sa.text("DROP INDEX IF EXISTS ix_drone_pad_categories_name"))
    op.execute(sa.text("DROP TABLE IF EXISTS drone_pad_categories"))
