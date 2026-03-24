"""add drum kits

Revision ID: k0l92g71h8i4
Revises: j9k81f60g7h3
Create Date: 2026-03-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "k0l92g71h8i4"
down_revision = "j9k81f60g7h3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS drum_kits (
            id UUID PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            slug VARCHAR(300) NOT NULL,
            description TEXT,
            thumbnail_s3_key VARCHAR(500),
            tags TEXT[] NOT NULL DEFAULT '{}',
            is_free BOOLEAN NOT NULL DEFAULT true,
            created_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))
    op.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_drum_kits_slug ON drum_kits (slug)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_drum_kits_created_at ON drum_kits (created_at)"))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS drum_kit_categories (
            id UUID PRIMARY KEY,
            drum_kit_id UUID NOT NULL REFERENCES drum_kits(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_drum_kit_categories_drum_kit_id ON drum_kit_categories (drum_kit_id)"))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS drum_samples (
            id UUID PRIMARY KEY,
            category_id UUID NOT NULL REFERENCES drum_kit_categories(id) ON DELETE CASCADE,
            label VARCHAR(100) NOT NULL,
            file_s3_key VARCHAR(500),
            preview_s3_key VARCHAR(500),
            aes_key TEXT,
            aes_iv TEXT,
            duration INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'processing',
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_drum_samples_category_id ON drum_samples (category_id)"))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_drum_samples_category_id"))
    op.execute(sa.text("DROP TABLE IF EXISTS drum_samples"))

    op.execute(sa.text("DROP INDEX IF EXISTS ix_drum_kit_categories_drum_kit_id"))
    op.execute(sa.text("DROP TABLE IF EXISTS drum_kit_categories"))

    op.execute(sa.text("DROP INDEX IF EXISTS ix_drum_kits_created_at"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_drum_kits_slug"))
    op.execute(sa.text("DROP TABLE IF EXISTS drum_kits"))
