"""add drone pads

Revision ID: i8j70e59f6a2
Revises: h7i69d48e5f1
Create Date: 2026-03-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "i8j70e59f6a2"
down_revision = "h7i69d48e5f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "CREATE TYPE dronetype AS ENUM ('warm', 'shimmer', 'dark', 'bright', 'orchestral', 'ethereal')"
    ))
    op.execute(sa.text(
        "CREATE TYPE musicalkey AS ENUM ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')"
    ))

    op.create_table(
        "drone_pads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("drone_type", sa.Enum("warm", "shimmer", "dark", "bright", "orchestral", "ethereal", name="dronetype"), nullable=False),
        sa.Column("key", sa.Enum("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B", name="musicalkey"), nullable=False),
        sa.Column("duration", sa.Integer, nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_free", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("file_s3_key", sa.String(500), nullable=True),
        sa.Column("preview_s3_key", sa.String(500), nullable=True),
        sa.Column("thumbnail_s3_key", sa.String(500), nullable=True),
        sa.Column("aes_key", sa.Text, nullable=True),
        sa.Column("aes_iv", sa.Text, nullable=True),
        sa.Column("download_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute(sa.text("CREATE INDEX ix_drone_pads_drone_type ON drone_pads (drone_type)"))
    op.execute(sa.text("CREATE INDEX ix_drone_pads_key ON drone_pads (key)"))

    op.add_column(
        "purchases",
        sa.Column("drone_pad_id", UUID(as_uuid=True), sa.ForeignKey("drone_pads.id"), nullable=True),
    )
    op.execute(sa.text("CREATE INDEX ix_purchases_drone_pad_id ON purchases (drone_pad_id)"))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_purchases_drone_pad_id"))
    op.drop_column("purchases", "drone_pad_id")

    op.execute(sa.text("DROP INDEX IF EXISTS ix_drone_pads_key"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_drone_pads_drone_type"))
    op.drop_table("drone_pads")

    sa.Enum(name="musicalkey").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="dronetype").drop(op.get_bind(), checkfirst=True)
