"""Add contact_phone to properties

Lets a property list its own contact number, overriding the owning user's
phone on the public listing (Call/WhatsApp buttons). Optional — falls back
to owner.phone when not set.

Revision ID: 006
Revises: 005
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("contact_phone", sa.String(length=15), nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "contact_phone")
