"""常用食材: the ordered list of ingredients the recipe form offers as chips

Revision ID: c1ommon
Revises: s1tepkinds
Create Date: 2026-10-03

`common_ingredient`: one row per listed ingredient, keyed by `ingredient_id`
(so nothing is listed twice) with ON DELETE CASCADE - an ingredient deleted
leaves the list - and a NOT NULL `sort_order`. Created empty; the owner fills
it from 設定.

Downgrade drops the table, and the list with it. No ingredient is touched.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "c1ommon"
down_revision = "s1tepkinds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "common_ingredient",
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("ingredient_id"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("common_ingredient")
