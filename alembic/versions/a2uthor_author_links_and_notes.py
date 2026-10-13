"""authors: a remark and links

Revision ID: a2uthor
Revises: h2omemade
Create Date: 2026-10-12

`author` gains `notes`, a nullable Text - the owner's remark on an author,
line breaks kept. `author_link` is the author's links, `tbd_link`'s shape and
rules exactly: ON DELETE CASCADE from the author, indexed, a NOT NULL
`position` (the order sent - no unique constraint, since a save replaces the
rows wholesale), a NOT NULL `url` that the CHECK refuses when blank, and an
optional `label`. Nothing references `author_link`.

Every existing author starts with no remark and no links; nothing is
backfilled.

Downgrade drops `author_link` and `author.notes`, and with them every link
and remark - nothing else is touched.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "a2uthor"
down_revision = "h2omemade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("author", sa.Column("notes", sa.Text(), nullable=True))
    op.create_table(
        "author_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["author_id"], ["author.id"], ondelete="CASCADE"),
        sa.CheckConstraint("btrim(url) <> ''", name="ck_author_link_has_a_url"),
    )
    op.create_index("ix_author_link_author_id", "author_link", ["author_id"])


def downgrade() -> None:
    op.drop_index("ix_author_link_author_id", "author_link")
    op.drop_table("author_link")
    op.drop_column("author", "notes")
