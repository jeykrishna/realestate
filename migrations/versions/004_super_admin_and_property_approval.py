"""Add super_admin role and property approval workflow

Introduces a `super_admin` user role that sits above `admin`: admins can still
create/edit properties, but new properties they create start out
`approval_status = pending` until a super admin approves or rejects them.
Properties created by a super admin (or existing rows, backfilled here) are
`approved` immediately so current data keeps behaving exactly as before.

Revision ID: 004
Revises: 003
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

approvalstatus = sa.Enum("pending", "approved", "rejected", name="approvalstatus")


def upgrade() -> None:
    # New enum value must be committed before it can be referenced elsewhere.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'super_admin'")

    approvalstatus.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "properties",
        sa.Column(
            "approval_status", approvalstatus,
            nullable=False, server_default="approved",
        ),
    )
    op.add_column("properties", sa.Column("approved_by", sa.String(), nullable=True))
    op.add_column("properties", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("properties", sa.Column("rejection_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "rejection_reason")
    op.drop_column("properties", "approved_at")
    op.drop_column("properties", "approved_by")
    op.drop_column("properties", "approval_status")
    approvalstatus.drop(op.get_bind(), checkfirst=True)
    # Postgres has no DROP VALUE for enums — 'super_admin' stays in `userrole`
    # on downgrade (harmless, matches Postgres's own ADD VALUE limitation).
