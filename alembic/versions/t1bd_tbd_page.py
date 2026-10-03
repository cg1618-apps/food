"""TBD: a standalone page of names and links

Revision ID: t1bd
Revises: c1ommon
Create Date: 2026-10-03

`tbd_entry`: an optional `name` and a NOT NULL `sort_order`, with the
timestamps every entity here carries. `tbd_link`: the entry's links, ON DELETE
CASCADE from the entry, with a NOT NULL `position`, a NOT NULL `url` that the
CHECK refuses when blank, and an optional `label`. Nothing references either
table and neither references anything else - the page is standalone.

The rule that an entry has a name or a link is the service's: a CHECK cannot
see the child table.

Downgrade drops both tables and every entry on the page; nothing else is
touched.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "t1bd"
down_revision = "c1ommon"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tbd_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tbd_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["entry_id"], ["tbd_entry.id"], ondelete="CASCADE"),
        sa.CheckConstraint("btrim(url) <> ''", name="ck_tbd_link_has_a_url"),
    )
    op.create_index("ix_tbd_link_entry_id", "tbd_link", ["entry_id"])


def downgrade() -> None:
    op.drop_index("ix_tbd_link_entry_id", "tbd_link")
    op.drop_table("tbd_link")
    op.drop_table("tbd_entry")
