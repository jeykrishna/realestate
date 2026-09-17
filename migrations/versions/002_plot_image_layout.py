"""Add polygon plot fields and image-map layout columns

Supports SVG-polygon "image map" plot layouts (admin plot tracer / publish
flow) alongside the existing grid "seat map" layout: plots gain a `polygon`
points string, and plot_configs gain layout_type/image_url/img_width/
img_height. plot_configs.rows/cols become nullable since image-map layouts
have no grid.

Revision ID: 002
Revises: 001
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plots", sa.Column("polygon", sa.Text(), nullable=True))

    op.add_column("plot_configs", sa.Column("layout_type", sa.String(), nullable=True, server_default="grid"))
    op.add_column("plot_configs", sa.Column("image_url", sa.String(), nullable=True))
    op.add_column("plot_configs", sa.Column("img_width", sa.Integer(), nullable=True))
    op.add_column("plot_configs", sa.Column("img_height", sa.Integer(), nullable=True))
    op.alter_column("plot_configs", "rows", existing_type=sa.Integer(), nullable=True)
    op.alter_column("plot_configs", "cols", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("plot_configs", "cols", existing_type=sa.Integer(), nullable=False)
    op.alter_column("plot_configs", "rows", existing_type=sa.Integer(), nullable=False)
    op.drop_column("plot_configs", "img_height")
    op.drop_column("plot_configs", "img_width")
    op.drop_column("plot_configs", "image_url")
    op.drop_column("plot_configs", "layout_type")

    op.drop_column("plots", "polygon")
