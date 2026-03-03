"""add likes table

Revision ID: f5g47b26c3d9
Revises: e4f36a15b2c8
Create Date: 2026-03-03 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "f5g47b26c3d9"
down_revision: Union[str, None] = "e4f36a15b2c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "likes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("loop_id", sa.UUID(), nullable=True),
        sa.Column("stem_pack_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["loop_id"], ["loops.id"]),
        sa.ForeignKeyConstraint(["stem_pack_id"], ["stem_packs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "loop_id", name="uq_likes_user_loop"),
        sa.UniqueConstraint("user_id", "stem_pack_id", name="uq_likes_user_stem_pack"),
    )
    op.create_index("ix_likes_user_id", "likes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_likes_user_id", table_name="likes")
    op.drop_table("likes")
