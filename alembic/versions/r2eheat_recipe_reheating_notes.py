"""recipe.reheating_notes: how to reheat what a recipe makes (加熱)

Revision ID: r2eheat
Revises: a2lternatives
Create Date: 2026-10-13

`recipe` gains `reheating_notes`, a nullable Text column - free text beside
`storage_notes`, shown between 保存 and 筆記. Every existing recipe starts
with none; no row is written.

Downgrade drops the column and every recipe's 加熱 text with it; nothing else
is touched.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "r2eheat"
down_revision = "a2lternatives"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recipe", sa.Column("reheating_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("recipe", "reheating_notes")
