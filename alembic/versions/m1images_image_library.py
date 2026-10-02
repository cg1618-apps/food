"""the image library and ingredient galleries

Revision ID: m1images
Revises: i2storage
Create Date: 2026-10-02

One table of stored pictures and one gallery table per owner type, with real
foreign keys rather than media's polymorphic owner columns - see
app/models/image.py. Recipes and kitchen notes add their own gallery tables in
their own revisions.

Downgrade drops the tables. The files under IMAGE_DIR are not touched: a
migration has no business deleting the only copy of a photograph.
"""

import sqlalchemy as sa

from alembic import op

revision = "m1images"
down_revision = "i2storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("thumb_key", sa.String(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checksum", name="uq_image_checksum"),
    )
    op.create_table(
        "ingredient_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("focus", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["image_id"], ["image.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("ingredient_id", "position", name="uq_ingredient_image_position"),
        sa.UniqueConstraint("ingredient_id", "image_id", name="uq_ingredient_image_once"),
    )
    op.create_index("ix_ingredient_image_ingredient_id", "ingredient_image", ["ingredient_id"])
    op.create_index("ix_ingredient_image_image_id", "ingredient_image", ["image_id"])


def downgrade() -> None:
    op.drop_index("ix_ingredient_image_image_id", "ingredient_image")
    op.drop_index("ix_ingredient_image_ingredient_id", "ingredient_image")
    op.drop_table("ingredient_image")
    op.drop_table("image")
