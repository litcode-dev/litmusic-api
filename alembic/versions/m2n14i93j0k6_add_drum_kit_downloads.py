"""add drum kit download support

Revision ID: m2n14i93j0k6
Revises: l1m03h82i9j5
Create Date: 2026-03-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "m2n14i93j0k6"
down_revision = "l1m03h82i9j5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # download_count on drum_kits
    op.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE drum_kits ADD COLUMN download_count INTEGER NOT NULL DEFAULT 0;
        EXCEPTION WHEN duplicate_column THEN null;
        END $$
    """))

    # drum_kit_id FK on downloads
    op.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE downloads
                ADD COLUMN drum_kit_id UUID REFERENCES drum_kits(id);
        EXCEPTION WHEN duplicate_column THEN null;
        END $$
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_downloads_drum_kit_id ON downloads (drum_kit_id)"))

    # drum_kit_id FK on purchases (for entitlement checks)
    op.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE purchases
                ADD COLUMN drum_kit_id UUID REFERENCES drum_kits(id);
        EXCEPTION WHEN duplicate_column THEN null;
        END $$
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_purchases_drum_kit_id ON purchases (drum_kit_id)"))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_purchases_drum_kit_id"))
    op.execute(sa.text("ALTER TABLE purchases DROP COLUMN IF EXISTS drum_kit_id"))

    op.execute(sa.text("DROP INDEX IF EXISTS ix_downloads_drum_kit_id"))
    op.execute(sa.text("ALTER TABLE downloads DROP COLUMN IF EXISTS drum_kit_id"))

    op.execute(sa.text("ALTER TABLE drum_kits DROP COLUMN IF EXISTS download_count"))
