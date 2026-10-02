"""kitchen notes

Revision ID: k1notes
Revises: r1recipes
Create Date: 2026-10-02

Kitchen notes: the note, its label links and its gallery. Written by hand and
importing nothing from `app.models`, as every revision here is.

A note has a title, not name slots, and titles are not unique. The CHECK
refuses a title that is empty once trimmed - NOT NULL alone would accept "".
Both sides of the label link CASCADE; the gallery is the shape of every other
gallery, owner side CASCADE and image side RESTRICT.

Downgrade drops all three tables and every note in them; there is nowhere to
keep the data. The pictures a note gallery attached stay in `image` and on
disk - only the attachments go.
"""

import sqlalchemy as sa

from alembic import op

revision = "k1notes"
down_revision = "r1recipes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kitchen_note",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False, server_default=sa.text("'reference'")),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("btrim(title) <> ''", name="ck_kitchen_note_has_a_title"),
    )

    op.create_table(
        "kitchen_note_label",
        sa.Column("kitchen_note_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("kitchen_note_id", "label_id"),
        sa.ForeignKeyConstraint(["kitchen_note_id"], ["kitchen_note.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["label_id"], ["label.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_kitchen_note_label_label_id", "kitchen_note_label", ["label_id"])

    op.create_table(
        "kitchen_note_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kitchen_note_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("focus", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["kitchen_note_id"], ["kitchen_note.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["image_id"], ["image.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "kitchen_note_id", "position", name="uq_kitchen_note_image_position"
        ),
        sa.UniqueConstraint("kitchen_note_id", "image_id", name="uq_kitchen_note_image_once"),
    )
    op.create_index(
        "ix_kitchen_note_image_kitchen_note_id", "kitchen_note_image", ["kitchen_note_id"]
    )
    op.create_index("ix_kitchen_note_image_image_id", "kitchen_note_image", ["image_id"])


def downgrade() -> None:
    op.drop_index("ix_kitchen_note_image_image_id", "kitchen_note_image")
    op.drop_index("ix_kitchen_note_image_kitchen_note_id", "kitchen_note_image")
    op.drop_table("kitchen_note_image")
    op.drop_index("ix_kitchen_note_label_label_id", "kitchen_note_label")
    op.drop_table("kitchen_note_label")
    op.drop_table("kitchen_note")
