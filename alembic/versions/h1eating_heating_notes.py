"""加熱: a standalone page of heating notes

Revision ID: h1eating
Revises: s4chedule
Create Date: 2026-10-03

`heating_note`: a NOT NULL `name` that the CHECK refuses when blank, an
optional `body`, a NOT NULL `sort_order`, and the timestamps every entity here
carries. Nothing references it and it references nothing - the page is
standalone, as TBD's is.

Downgrade drops the table and every note on the page; nothing else is
touched.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "h1eating"
down_revision = "s4chedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "heating_note",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_heating_note_has_a_name"),
    )


def downgrade() -> None:
    op.drop_table("heating_note")
