"""Add password_hash to users

Admin and super admin accounts now log in with a password instead of an
emailed OTP. Owners are unaffected and keep using OTP login. Existing
admin/super_admin rows are left with password_hash = NULL; they set a
password by registering again with the same email through /admin/signup,
which "claims" the existing account instead of rejecting it as a duplicate.

Revision ID: 005
Revises: 004
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
