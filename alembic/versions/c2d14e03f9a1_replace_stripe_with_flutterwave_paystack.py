"""replace stripe with flutterwave paystack

Revision ID: c2d14e03f9a1
Revises: b1c93d02e5f8
Create Date: 2026-03-02 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d14e03f9a1"
down_revision: Union[str, None] = "b1c93d02e5f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the new PaymentProvider enum type
    op.execute("CREATE TYPE paymentprovider AS ENUM ('flutterwave', 'paystack')")

    # Add new columns (nullable first so we can backfill)
    op.add_column("purchases", sa.Column("payment_reference", sa.String(255), nullable=True))
    op.add_column(
        "purchases",
        sa.Column(
            "payment_provider",
            sa.Enum("flutterwave", "paystack", name="paymentprovider", create_type=False),
            nullable=True,
        ),
    )

    # Backfill existing rows (treat all existing Stripe records as flutterwave)
    op.execute(
        "UPDATE purchases SET payment_reference = stripe_payment_intent_id, "
        "payment_provider = 'flutterwave' WHERE payment_reference IS NULL"
    )

    # Make columns NOT NULL
    op.alter_column("purchases", "payment_reference", nullable=False)
    op.alter_column("purchases", "payment_provider", nullable=False)

    # Add unique constraint on payment_reference
    op.create_unique_constraint(
        "uq_purchases_payment_reference", "purchases", ["payment_reference"]
    )

    # Drop the old Stripe column (its unique constraint is dropped automatically)
    op.drop_column("purchases", "stripe_payment_intent_id")


def downgrade() -> None:
    # Re-add Stripe column
    op.add_column(
        "purchases",
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
    )
    op.execute("UPDATE purchases SET stripe_payment_intent_id = payment_reference")
    op.alter_column("purchases", "stripe_payment_intent_id", nullable=False)
    op.create_unique_constraint(
        "uq_purchases_stripe_payment_intent_id",
        "purchases",
        ["stripe_payment_intent_id"],
    )

    # Drop new columns and constraint
    op.drop_constraint("uq_purchases_payment_reference", "purchases", type_="unique")
    op.drop_column("purchases", "payment_reference")
    op.drop_column("purchases", "payment_provider")

    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS paymentprovider")
