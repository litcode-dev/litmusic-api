"""add_subscription_ai_generation

Revision ID: h7i69d48e5f1
Revises: g6h58c37d4e0
Create Date: 2026-03-07 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

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

    # --- enums (raw SQL to avoid SQLAlchemy asyncpg create_type issues) ---
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE subscriptionplan AS ENUM ('premium');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE subscriptionstatus AS ENUM ('active', 'cancelled', 'expired');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE aiprovider AS ENUM ('suno', 'self_hosted');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE aigenerationstatus AS ENUM ('pending', 'processing', 'completed', 'failed');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))

    # --- subscriptions table (raw SQL to avoid SQLAlchemy re-creating existing enums) ---
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id          UUID PRIMARY KEY,
            user_id     UUID NOT NULL REFERENCES users(id),
            plan        subscriptionplan NOT NULL,
            status      subscriptionstatus NOT NULL DEFAULT 'active',
            provider    paymentprovider NOT NULL,
            payment_reference VARCHAR(255) NOT NULL UNIQUE,
            amount_paid NUMERIC(10, 2) NOT NULL,
            ai_quota    INTEGER NOT NULL DEFAULT 10,
            ai_quota_used INTEGER NOT NULL DEFAULT 0,
            billing_period_start TIMESTAMPTZ NOT NULL,
            expires_at  TIMESTAMPTZ NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_subscriptions_user_id ON subscriptions (user_id)"
    ))

    # --- ai_generations table ---
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS ai_generations (
            id              UUID PRIMARY KEY,
            user_id         UUID NOT NULL REFERENCES users(id),
            subscription_id UUID REFERENCES subscriptions(id),
            provider        aiprovider NOT NULL,
            prompt          TEXT NOT NULL,
            style_prompt    TEXT,
            status          aigenerationstatus NOT NULL DEFAULT 'pending',
            result_loop_id  UUID REFERENCES loops(id),
            is_extra        BOOLEAN NOT NULL DEFAULT false,
            error_message   TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_ai_generations_user_id ON ai_generations (user_id)"
    ))


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
