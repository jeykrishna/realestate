"""Remove legacy OTP columns from users table

These columns (otp, otp_expires_at) were superseded by Redis-backed OTP storage
and were never written to in production. Removing them eliminates misleading dead
schema and reduces the attack surface on the users table.

Revision ID: 001
Revises: (initial)
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "otp")
    op.drop_column("users", "otp_expires_at")


def downgrade() -> None:
    op.add_column("users", sa.Column("otp_expires_at", sa.String(), nullable=True))
    op.add_column("users", sa.Column("otp", sa.String(), nullable=True))
