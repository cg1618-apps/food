"""galleries: a caption per attachment

Revision ID: m2captions
Revises: c3ommon
Create Date: 2026-10-28

A nullable `caption` on each of the four gallery tables - `ingredient_image`,
`dish_image`, `recipe_image` and `kitchen_note_image` - beside `focus`, and
for the same reason: it belongs to the attachment, not to the `image` row, so
one picture in two galleries can say two different things. Trimmed and never
"" (the API stores a blank caption as NULL). Every existing attachment starts
with none.

Downgrade drops the four columns, and every caption with them; no picture and
no attachment is lost.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "m2captions"
down_revision = "c3ommon"
branch_labels = None
depends_on = None

TABLES = ("ingredient_image", "dish_image", "recipe_image", "kitchen_note_image")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("caption", sa.String(), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "caption")
