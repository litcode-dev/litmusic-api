"""remove drone_type from drone_pads

Revision ID: n3o25j04k1l7
Revises: m2n14i93j0k6
Create Date: 2026-03-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "n3o25j04k1l7"
down_revision = "m2n14i93j0k6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_drone_pads_drone_type"))
    op.execute(sa.text("ALTER TABLE drone_pads DROP COLUMN IF EXISTS drone_type"))


def downgrade() -> None:
    op.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE drone_pads
                ADD COLUMN drone_type VARCHAR(20) NOT NULL DEFAULT 'warm';
        EXCEPTION WHEN duplicate_column THEN null;
        END $$
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_drone_pads_drone_type ON drone_pads (drone_type)"))
