"""add drone pads

Revision ID: i8j70e59f6a2
Revises: h7i69d48e5f1
Create Date: 2026-03-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "i8j70e59f6a2"
down_revision = "h7i69d48e5f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "DO $$ BEGIN "
        "CREATE TYPE dronetype AS ENUM ('warm', 'shimmer', 'dark', 'bright', 'orchestral', 'ethereal'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$"
    ))
    op.execute(sa.text(
        "DO $$ BEGIN "
        "CREATE TYPE musicalkey AS ENUM ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$"
    ))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS drone_pads (
            id UUID PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            drone_type dronetype NOT NULL,
            key musicalkey NOT NULL,
            duration INTEGER NOT NULL,
            price NUMERIC(10, 2) NOT NULL,
            is_free BOOLEAN NOT NULL DEFAULT false,
            file_s3_key VARCHAR(500),
            preview_s3_key VARCHAR(500),
            thumbnail_s3_key VARCHAR(500),
            aes_key TEXT,
            aes_iv TEXT,
            download_count INTEGER NOT NULL DEFAULT 0,
            created_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))

    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_drone_pads_drone_type ON drone_pads (drone_type)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_drone_pads_key ON drone_pads (key)"))

    op.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE purchases ADD COLUMN drone_pad_id UUID REFERENCES drone_pads(id);
        EXCEPTION WHEN duplicate_column THEN null;
        END $$
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_purchases_drone_pad_id ON purchases (drone_pad_id)"))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_purchases_drone_pad_id"))
    op.execute(sa.text("ALTER TABLE purchases DROP COLUMN IF EXISTS drone_pad_id"))

    op.execute(sa.text("DROP INDEX IF EXISTS ix_drone_pads_key"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_drone_pads_drone_type"))
    op.execute(sa.text("DROP TABLE IF EXISTS drone_pads"))

    op.execute(sa.text("DROP TYPE IF EXISTS musicalkey"))
    op.execute(sa.text("DROP TYPE IF EXISTS dronetype"))
