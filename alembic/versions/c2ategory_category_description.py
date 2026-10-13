"""ingredient categories: a description of their own

Revision ID: c2ategory
Revises: l1abels
Create Date: 2026-10-12

`ingredient_category.description`, a nullable Text column: notes about a
family as a whole - how to pick fresh chicken, how long chicken keeps - for a
category like 雞肉 whose members are bought but which is never itself bought
or cited on a recipe line. Every existing category starts with none; nothing
is copied in from anywhere.

Downgrade drops the column, and every category's description with it.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "c2ategory"
down_revision = "l1abels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ingredient_category", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ingredient_category", "description")
