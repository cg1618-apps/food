"""weekly schedule: a day's plain fields and its four meals

Revision ID: s3chedule
Revises: t2emplates
Create Date: 2026-10-03

New table `schedule_day`, keyed by its DATE, with six nullable Text fields:
`to_buy`, `thaw_morning`, `thaw_noon`, `thaw_evening`, `fruit`, `note`.

New table `schedule_meal`: an `id`; a NOT NULL `date` referencing
`schedule_day.date` ON DELETE CASCADE; a NOT NULL `slot` (validated in the
API against MEAL_SLOTS, not by the database); a nullable `text`; a nullable
`dish_id` referencing `dish` ON DELETE RESTRICT and a nullable `recipe_id`
referencing `recipe` ON DELETE SET NULL, each indexed; one meal per slot per
date through `uq_schedule_meal_slot`.

Nothing is seeded and no existing row changes. Downgrade drops both tables and
every planned day in them; nothing else is touched.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "s3chedule"
down_revision = "t2emplates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schedule_day",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("to_buy", sa.Text(), nullable=True),
        sa.Column("thaw_morning", sa.Text(), nullable=True),
        sa.Column("thaw_noon", sa.Text(), nullable=True),
        sa.Column("thaw_evening", sa.Text(), nullable=True),
        sa.Column("fruit", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("date"),
    )
    op.create_table(
        "schedule_meal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("slot", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("dish_id", sa.Integer(), nullable=True),
        sa.Column("recipe_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["date"], ["schedule_day.date"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dish_id"], ["dish.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("date", "slot", name="uq_schedule_meal_slot"),
    )
    op.create_index("ix_schedule_meal_dish_id", "schedule_meal", ["dish_id"])
    op.create_index("ix_schedule_meal_recipe_id", "schedule_meal", ["recipe_id"])


def downgrade() -> None:
    op.drop_index("ix_schedule_meal_recipe_id", "schedule_meal")
    op.drop_index("ix_schedule_meal_dish_id", "schedule_meal")
    op.drop_table("schedule_meal")
    op.drop_table("schedule_day")
