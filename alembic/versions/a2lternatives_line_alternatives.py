"""recipe_line_alternative: what may stand in for a line's target

Revision ID: a2lternatives
Revises: a2uthor
Create Date: 2026-10-12

One new table, a child of `recipe_line`: `line_id` ON DELETE CASCADE and
indexed; a NOT NULL `position`, unique per line (`uq_recipe_line_alternative_position`);
`ingredient_id` and `sub_dish_id`, each ON DELETE RESTRICT and indexed, exactly
one of them set (`ck_recipe_line_alternative_one_target`, the line's own
rule); and optional free-text `amount` and `note`.

Nothing existing changes, and no row is written: every line starts with no
alternatives. A recipe template's JSONB body that predates this has no
`alternatives` key on its lines, and the service reads that as none.

Downgrade drops the table and every alternative with it; nothing else is
touched.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "a2lternatives"
down_revision = "a2uthor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recipe_line_alternative",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("line_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=True),
        sa.Column("sub_dish_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.String(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["line_id"], ["recipe_line.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sub_dish_id"], ["dish.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("line_id", "position", name="uq_recipe_line_alternative_position"),
        sa.CheckConstraint(
            "num_nonnulls(ingredient_id, sub_dish_id) = 1",
            name="ck_recipe_line_alternative_one_target",
        ),
    )
    op.create_index("ix_recipe_line_alternative_line_id", "recipe_line_alternative", ["line_id"])
    op.create_index(
        "ix_recipe_line_alternative_ingredient_id", "recipe_line_alternative", ["ingredient_id"]
    )
    op.create_index(
        "ix_recipe_line_alternative_sub_dish_id", "recipe_line_alternative", ["sub_dish_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_recipe_line_alternative_sub_dish_id", "recipe_line_alternative")
    op.drop_index("ix_recipe_line_alternative_ingredient_id", "recipe_line_alternative")
    op.drop_index("ix_recipe_line_alternative_line_id", "recipe_line_alternative")
    op.drop_table("recipe_line_alternative")
