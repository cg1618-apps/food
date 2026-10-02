"""storage state and range, the heating guide, links, rating

Revision ID: i2storage
Revises: v1ocabulary
Create Date: 2026-10-02

The ingredient changes the reference sheets need. Existing preservation rows
become state 'unused', and their single duration is copied to both ends of the
new range - the closest statement of what was recorded.

Downgrade reverses that lossily: rows for any state but 'unused' are deleted,
because the old unique key (ingredient, method) cannot hold two states, and
the range collapses to its maximum (or its minimum when there is no maximum).
"""

import sqlalchemy as sa

from alembic import op

revision = "i2storage"
down_revision = "v1ocabulary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ingredient", sa.Column("rating", sa.String(), nullable=True))

    op.add_column(
        "ingredient_preservation",
        sa.Column("state", sa.String(), nullable=False, server_default=sa.text("'unused'")),
    )
    op.alter_column(
        "ingredient_preservation", "duration_days", new_column_name="duration_min_days"
    )
    op.add_column(
        "ingredient_preservation", sa.Column("duration_max_days", sa.Integer(), nullable=True)
    )
    op.execute("UPDATE ingredient_preservation SET duration_max_days = duration_min_days")
    op.drop_constraint(
        "ck_ingredient_preservation_duration_positive", "ingredient_preservation", type_="check"
    )
    op.create_check_constraint(
        "ck_ingredient_preservation_duration_positive",
        "ingredient_preservation",
        "(duration_min_days IS NULL OR duration_min_days > 0) "
        "AND (duration_max_days IS NULL OR duration_max_days > 0)",
    )
    op.create_check_constraint(
        "ck_ingredient_preservation_duration_order",
        "ingredient_preservation",
        "duration_min_days IS NULL OR duration_max_days IS NULL "
        "OR duration_min_days <= duration_max_days",
    )
    op.drop_constraint(
        "uq_ingredient_preservation_method", "ingredient_preservation", type_="unique"
    )
    op.create_unique_constraint(
        "uq_ingredient_preservation_state_method",
        "ingredient_preservation",
        ["ingredient_id", "state", "method"],
    )

    op.create_table(
        "ingredient_heating",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("method_id", sa.Integer(), nullable=False),
        sa.Column("temperature_c", sa.Integer(), nullable=True),
        sa.Column("duration", sa.String(), nullable=True),
        sa.Column("preheat", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("flip", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["method_id"], ["cooking_method.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "temperature_c IS NULL OR temperature_c > 0",
            name="ck_ingredient_heating_temperature_positive",
        ),
    )
    op.create_index("ix_ingredient_heating_ingredient_id", "ingredient_heating", ["ingredient_id"])
    op.create_index("ix_ingredient_heating_method_id", "ingredient_heating", ["method_id"])

    op.create_table(
        "ingredient_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ingredient_link_ingredient_id", "ingredient_link", ["ingredient_id"])


def downgrade() -> None:
    op.drop_index("ix_ingredient_link_ingredient_id", "ingredient_link")
    op.drop_table("ingredient_link")
    op.drop_index("ix_ingredient_heating_method_id", "ingredient_heating")
    op.drop_index("ix_ingredient_heating_ingredient_id", "ingredient_heating")
    op.drop_table("ingredient_heating")

    op.execute("DELETE FROM ingredient_preservation WHERE state <> 'unused'")
    op.drop_constraint(
        "uq_ingredient_preservation_state_method", "ingredient_preservation", type_="unique"
    )
    op.create_unique_constraint(
        "uq_ingredient_preservation_method", "ingredient_preservation", ["ingredient_id", "method"]
    )
    op.drop_constraint(
        "ck_ingredient_preservation_duration_order", "ingredient_preservation", type_="check"
    )
    op.drop_constraint(
        "ck_ingredient_preservation_duration_positive", "ingredient_preservation", type_="check"
    )
    op.execute(
        "UPDATE ingredient_preservation "
        "SET duration_min_days = coalesce(duration_max_days, duration_min_days)"
    )
    op.drop_column("ingredient_preservation", "duration_max_days")
    op.alter_column(
        "ingredient_preservation", "duration_min_days", new_column_name="duration_days"
    )
    op.create_check_constraint(
        "ck_ingredient_preservation_duration_positive",
        "ingredient_preservation",
        "duration_days IS NULL OR duration_days > 0",
    )
    op.drop_column("ingredient_preservation", "state")
    op.drop_column("ingredient", "rating")
