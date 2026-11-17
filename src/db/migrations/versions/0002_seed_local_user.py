"""Seed the single `local` user that owns every review and run until authentication exists.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

LOCAL_USER_EMAIL = "local@localhost"


def upgrade() -> None:
    op.execute(f"INSERT INTO users (email) VALUES ('{LOCAL_USER_EMAIL}')")


def downgrade() -> None:
    op.execute(f"DELETE FROM users WHERE email = '{LOCAL_USER_EMAIL}'")
