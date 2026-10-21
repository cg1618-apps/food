"""recipe templates are removed: drop recipe_template

Revision ID: t3emplates
Revises: d2ifficulty
Create Date: 2026-10-20

The recipe template feature (`t2emplates`) is removed at the owner's request,
so its one table goes: `recipe_template`, with its expression index
`uq_recipe_template_name` and its check `ck_recipe_template_has_a_name`.
Nothing references the table, so nothing else changes. Every template in it
is deleted; the owner confirmed there were none.

Downgrade recreates the table empty, exactly as `t2emplates` created it, so
the chain stays reversible. No template is restored - there is nothing to
restore them from.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "t3emplates"
down_revision = "d2ifficulty"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_recipe_template_name", "recipe_template")
    op.drop_table("recipe_template")


def downgrade() -> None:
    # t2emplates' upgrade, unchanged.
    op.create_table(
        "recipe_template",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_recipe_template_has_a_name"),
    )
    op.create_index(
        "uq_recipe_template_name",
        "recipe_template",
        [sa.text("lower(name)")],
        unique=True,
    )
