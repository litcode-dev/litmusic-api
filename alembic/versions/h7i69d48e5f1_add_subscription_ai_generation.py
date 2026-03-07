"""add_subscription_ai_generation

Revision ID: h7i69d48e5f1
Revises: g6h58c37d4e0
Create Date: 2026-03-07 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "h7i69d48e5f1"
down_revision: Union[str, None] = "g6h58c37d4e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users: new columns ---
    op.add_column(
        "users",
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "users",
        sa.Column("ai_extra_credits", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    # --- enums ---
    subscriptionplan = postgresql.ENUM(
        "premium", name="subscriptionplan", create_type=False
    )
    subscriptionstatus = postgresql.ENUM(
        "active", "cancelled", "expired", name="subscriptionstatus", create_type=False
    )
    aiprovider = postgresql.ENUM(
        "suno", "self_hosted", name="aiprovider", create_type=False
    )
    aigenerationstatus = postgresql.ENUM(
        "pending", "processing", "completed", "failed", name="aigenerationstatus", create_type=False
    )

    subscriptionplan.create(op.get_bind(), checkfirst=True)
    subscriptionstatus.create(op.get_bind(), checkfirst=True)
    aiprovider.create(op.get_bind(), checkfirst=True)
    aigenerationstatus.create(op.get_bind(), checkfirst=True)

    # --- subscriptions table ---
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("plan", sa.Enum("premium", name="subscriptionplan"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "cancelled", "expired", name="subscriptionstatus"),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "provider",
            sa.Enum("flutterwave", "paystack", name="paymentprovider"),
            nullable=False,
        ),
        sa.Column("payment_reference", sa.String(255), nullable=False, unique=True),
        sa.Column("amount_paid", sa.Numeric(10, 2), nullable=False),
        sa.Column("ai_quota", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("ai_quota_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("billing_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    # --- ai_generations table ---
    op.create_table(
        "ai_generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subscriptions.id"),
            nullable=True,
        ),
        sa.Column("provider", sa.Enum("suno", "self_hosted", name="aiprovider"), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("style_prompt", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed", name="aigenerationstatus"),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "result_loop_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("loops.id"),
            nullable=True,
        ),
        sa.Column("is_extra", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_ai_generations_user_id", "ai_generations", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_generations_user_id", table_name="ai_generations")
    op.drop_table("ai_generations")

    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_column("users", "ai_extra_credits")
    op.drop_column("users", "ai_enabled")

    # Drop enums created in upgrade (paymentprovider is shared — do NOT drop it here)
    sa.Enum(name="aigenerationstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="aiprovider").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="subscriptionstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="subscriptionplan").drop(op.get_bind(), checkfirst=True)
