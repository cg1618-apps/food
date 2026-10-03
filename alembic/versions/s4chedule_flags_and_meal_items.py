"""weekly schedule: the four marks become booleans, and a meal holds items

Revision ID: s4chedule
Revises: s3chedule
Create Date: 2026-10-03

`schedule_day.to_buy`, `thaw_morning`, `thaw_noon` and `thaw_evening` turn
from nullable Text into Boolean NOT NULL with a server default of false. A
stored text that is not blank becomes true; NULL and blank become false.
`fruit` and `note` stay text.

New table `schedule_meal_item`: an `id`; a NOT NULL `meal_id` referencing
`schedule_meal.id` ON DELETE CASCADE; a NOT NULL `position`, unique within
its meal through `uq_schedule_meal_item_position`; a NOT NULL `dish_id`
referencing `dish` ON DELETE RESTRICT and a nullable `recipe_id` referencing
`recipe` ON DELETE SET NULL; the three foreign keys indexed. Each existing
meal that named a dish (or only a recipe, whose dish it then takes) becomes
one item at position 0, and `schedule_meal` loses `dish_id` and `recipe_id`
with their indexes. A meal's text stays where it was.

Downgrade is lossy, by necessity: a true mark is written back as '✓' and a
false one as NULL, and a meal keeps only its first item (the lowest position)
as its dish and recipe - every later item is dropped with
`schedule_meal_item`.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "s4chedule"
down_revision = "s3chedule"
branch_labels = None
depends_on = None

FLAGS = ("to_buy", "thaw_morning", "thaw_noon", "thaw_evening")


def upgrade() -> None:
    for flag in FLAGS:
        op.execute(
            f"ALTER TABLE schedule_day ALTER COLUMN {flag} TYPE boolean "
            f"USING ({flag} IS NOT NULL AND btrim({flag}) <> '')"
        )
        op.execute(f"ALTER TABLE schedule_day ALTER COLUMN {flag} SET DEFAULT false")
        op.execute(f"ALTER TABLE schedule_day ALTER COLUMN {flag} SET NOT NULL")

    op.create_table(
        "schedule_meal_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meal_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("dish_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["meal_id"], ["schedule_meal.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dish_id"], ["dish.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("meal_id", "position", name="uq_schedule_meal_item_position"),
    )
    op.create_index("ix_schedule_meal_item_meal_id", "schedule_meal_item", ["meal_id"])
    op.create_index("ix_schedule_meal_item_dish_id", "schedule_meal_item", ["dish_id"])
    op.create_index("ix_schedule_meal_item_recipe_id", "schedule_meal_item", ["recipe_id"])

    op.execute(
        "INSERT INTO schedule_meal_item (meal_id, position, dish_id, recipe_id) "
        "SELECT m.id, 0, COALESCE(m.dish_id, r.dish_id), m.recipe_id "
        "FROM schedule_meal m LEFT JOIN recipe r ON r.id = m.recipe_id "
        "WHERE COALESCE(m.dish_id, r.dish_id) IS NOT NULL"
    )

    op.drop_index("ix_schedule_meal_recipe_id", "schedule_meal")
    op.drop_index("ix_schedule_meal_dish_id", "schedule_meal")
    op.drop_column("schedule_meal", "recipe_id")
    op.drop_column("schedule_meal", "dish_id")


def downgrade() -> None:
    op.add_column("schedule_meal", sa.Column("dish_id", sa.Integer(), nullable=True))
    op.add_column("schedule_meal", sa.Column("recipe_id", sa.Integer(), nullable=True))
    # The names PostgreSQL gave s3chedule's unnamed constraints, so a second
    # upgrade meets the same schema the first one did.
    op.create_foreign_key(
        "schedule_meal_dish_id_fkey",
        "schedule_meal",
        "dish",
        ["dish_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "schedule_meal_recipe_id_fkey",
        "schedule_meal",
        "recipe",
        ["recipe_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_schedule_meal_dish_id", "schedule_meal", ["dish_id"])
    op.create_index("ix_schedule_meal_recipe_id", "schedule_meal", ["recipe_id"])

    op.execute(
        "UPDATE schedule_meal m SET dish_id = first.dish_id, recipe_id = first.recipe_id "
        "FROM (SELECT DISTINCT ON (meal_id) meal_id, dish_id, recipe_id "
        "      FROM schedule_meal_item ORDER BY meal_id, position) AS first "
        "WHERE first.meal_id = m.id"
    )

    op.drop_index("ix_schedule_meal_item_recipe_id", "schedule_meal_item")
    op.drop_index("ix_schedule_meal_item_dish_id", "schedule_meal_item")
    op.drop_index("ix_schedule_meal_item_meal_id", "schedule_meal_item")
    op.drop_table("schedule_meal_item")

    for flag in FLAGS:
        op.execute(f"ALTER TABLE schedule_day ALTER COLUMN {flag} DROP NOT NULL")
        op.execute(f"ALTER TABLE schedule_day ALTER COLUMN {flag} DROP DEFAULT")
        op.execute(
            f"ALTER TABLE schedule_day ALTER COLUMN {flag} TYPE text "
            f"USING CASE WHEN {flag} THEN '✓' END"
        )
