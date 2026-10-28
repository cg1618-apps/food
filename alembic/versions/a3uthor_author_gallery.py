"""authors: a gallery

Revision ID: a3uthor
Revises: m2captions
Create Date: 2026-10-28

`author_image` is an author's gallery, the shape of the other four gallery
tables exactly: `author_id` ON DELETE CASCADE (an author deleted takes its
attachments, never the pictures), `image_id` ON DELETE RESTRICT (an attached
picture cannot be deleted), a NOT NULL `position` unique per author
(position 0 is the cover), each image at most once per author, and the
attachment's own `focus` and `caption`. Both foreign keys are indexed.

Every existing author starts with no pictures; nothing is backfilled.

Downgrade drops `author_image` and every attachment in it. The pictures stay
in `image` and on disk - only the attachments go.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "a3uthor"
down_revision = "m2captions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "author_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("focus", sa.String(), nullable=True),
        sa.Column("caption", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["author_id"], ["author.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["image_id"], ["image.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("author_id", "position", name="uq_author_image_position"),
        sa.UniqueConstraint("author_id", "image_id", name="uq_author_image_once"),
    )
    op.create_index("ix_author_image_author_id", "author_image", ["author_id"])
    op.create_index("ix_author_image_image_id", "author_image", ["image_id"])


def downgrade() -> None:
    op.drop_index("ix_author_image_image_id", "author_image")
    op.drop_index("ix_author_image_author_id", "author_image")
    op.drop_table("author_image")
