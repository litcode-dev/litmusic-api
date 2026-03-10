"""add oauth and expand roles

Revision ID: a3f82b91c4d7
Revises: 01d01a48c42e
Create Date: 2026-03-02 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3f82b91c4d7"
down_revision: Union[str, None] = "01d01a48c42e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Recreate enum without 'free', adding 'user' and 'producer'.
    # We rename → create new → migrate data → alter column → drop old,
    # all within the transaction (avoids ALTER TYPE ADD VALUE which cannot
    # run inside a transaction block).
    op.execute(sa.text("ALTER TYPE userrole RENAME TO userrole_old"))
    op.execute(sa.text("CREATE TYPE userrole AS ENUM ('user', 'producer', 'admin')"))

    # Detach column from old enum before altering
    op.execute(sa.text(
        "ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(50)"
    ))
    op.execute(sa.text("DROP TYPE userrole_old"))

    # Migrate data: free → user
    op.execute(sa.text("UPDATE users SET role = 'user' WHERE role = 'free'"))

    # Re-attach column to new enum
    op.execute(sa.text(
        "ALTER TABLE users ALTER COLUMN role TYPE userrole "
        "USING role::text::userrole"
    ))

    # 4. Add OAuth columns
    op.add_column("users", sa.Column("oauth_provider", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("oauth_provider_id", sa.String(255), nullable=True))
    op.create_index("ix_users_oauth_provider_id", "users", ["oauth_provider_id"])

    # 5. Make password_hash nullable
    op.alter_column("users", "password_hash", nullable=True)


def downgrade() -> None:
    # Remove OAuth columns
    op.drop_index("ix_users_oauth_provider_id", table_name="users")
    op.drop_column("users", "oauth_provider_id")
    op.drop_column("users", "oauth_provider")

    # Restore password_hash as non-nullable (set NULL values to placeholder first)
    op.execute("UPDATE users SET password_hash = '' WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", nullable=False)

    # Recreate enum with 'free', remove 'user' and 'producer'
    op.execute("UPDATE users SET role = 'free' WHERE role = 'user'")
    op.execute("UPDATE users SET role = 'admin' WHERE role = 'producer'")
    op.execute("ALTER TYPE userrole RENAME TO userrole_old")
    op.execute("CREATE TYPE userrole AS ENUM ('free', 'admin')")
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE userrole "
        "USING role::text::userrole"
    )
    op.execute("DROP TYPE userrole_old")
