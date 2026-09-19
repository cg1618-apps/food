"""the ingredient library

Revision ID: i1ngredients
Revises: 0001_baseline
Create Date: 2026-09-19

The first tables this application has: ingredients, the category tree they are
filed in, their aliases, the ways each one keeps, and cross-cutting labels.

Written by hand rather than taken from autogenerate, and it imports nothing
from `app.models`. A migration that selects through a live model breaks the
moment a later revision adds a column the model does not yet declare - the
model is always at head, the migration is not.

Four things here would not survive a naive autogenerate and are the reason to
read this file rather than trust the diff:

- The unique name indexes are on `lower(<column>)` and use Postgres's DEFAULT
  null handling, which is the correct choice for a single column and is worth
  stating because the opposite looks like the lesson. NULLS NOT DISTINCT is
  what a MULTI-column name constraint needs - media's `uq_person_name` is
  inert without it - but on one nullable column it makes NULL equal NULL and
  permits only one row with that name slot empty. Most ingredients here have
  only a Chinese name.
- `uq_ingredient_category_sibling_cn` indexes `coalesce(parent_id, 0)` rather
  than `parent_id`, because a NULL parent means "top level" and two root
  categories sharing a name would otherwise not collide at all. It is also
  partial, on `name_cn IS NOT NULL`, so any number of siblings may have no
  Chinese name.
- `uq_ingredient_category_one_fallback` is a PARTIAL unique index. It permits
  any number of rows with is_fallback false and exactly one with it true,
  which is what lets `ingredient.category_id` be NOT NULL without a required
  category blocking stub creation.
- The fallback category row is seeded here, because the NOT NULL column above
  has nowhere to point on a fresh database otherwise. It is the only row this
  revision inserts; the rest of the taxonomy is the owner's to build.

Downgrade drops all six tables and everything in them. There is no way to keep
the data: the tables are where it lives.
"""

import sqlalchemy as sa

from alembic import op

revision = "i1ngredients"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingredient_category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("name_cn", sa.String(), nullable=True),
        sa.Column("name_en", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "is_fallback", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["ingredient_category.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "num_nonnulls(name_cn, name_en) >= 1", name="ck_ingredient_category_has_a_name"
        ),
    )
    op.create_index(
        "uq_ingredient_category_sibling_cn",
        "ingredient_category",
        [sa.text("coalesce(parent_id, 0)"), sa.text("lower(name_cn)")],
        unique=True,
        postgresql_where=sa.text("name_cn IS NOT NULL"),
    )
    op.create_index(
        "uq_ingredient_category_one_fallback",
        "ingredient_category",
        ["is_fallback"],
        unique=True,
        postgresql_where=sa.text("is_fallback"),
    )

    op.create_table(
        "label",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name_cn", sa.String(), nullable=True),
        sa.Column("name_en", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("num_nonnulls(name_cn, name_en) >= 1", name="ck_label_has_a_name"),
    )
    op.create_index("uq_label_name_cn", "label", [sa.text("lower(name_cn)")], unique=True)
    op.create_index("uq_label_name_en", "label", [sa.text("lower(name_en)")], unique=True)

    op.create_table(
        "ingredient",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name_cn", sa.String(), nullable=True),
        sa.Column("name_en", sa.String(), nullable=True),
        sa.Column("name_alt", sa.String(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("selection_notes", sa.Text(), nullable=True),
        sa.Column("sourcing_notes", sa.Text(), nullable=True),
        sa.Column("preservation_notes", sa.Text(), nullable=True),
        sa.Column(
            "needs_detail", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["category_id"], ["ingredient_category.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["ingredient.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "num_nonnulls(name_cn, name_en, name_alt) >= 1", name="ck_ingredient_has_a_name"
        ),
    )
    op.create_index(
        "uq_ingredient_name_cn", "ingredient", [sa.text("lower(name_cn)")], unique=True
    )
    op.create_index(
        "uq_ingredient_name_en", "ingredient", [sa.text("lower(name_en)")], unique=True
    )

    op.create_table(
        "ingredient_alias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("ingredient_id", "value", name="uq_ingredient_alias"),
    )
    op.create_index(
        "ix_ingredient_alias_ingredient_id", "ingredient_alias", ["ingredient_id"]
    )
    op.create_index(
        "ix_ingredient_alias_lookup", "ingredient_alias", [sa.text("lower(value)")]
    )

    op.create_table(
        "ingredient_preservation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "ingredient_id", "method", name="uq_ingredient_preservation_method"
        ),
        sa.CheckConstraint(
            "duration_days IS NULL OR duration_days > 0",
            name="ck_ingredient_preservation_duration_positive",
        ),
    )
    op.create_index(
        "ix_ingredient_preservation_ingredient_id",
        "ingredient_preservation",
        ["ingredient_id"],
    )

    op.create_table(
        "ingredient_label",
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("ingredient_id", "label_id"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["label_id"], ["label.id"], ondelete="CASCADE"),
    )

    # The one row this revision inserts. `ingredient.category_id` is NOT NULL,
    # so without it the first ingredient on a fresh database has nowhere to be
    # filed - including a stub created from a recipe line, which is precisely
    # the case that must not stop to ask.
    op.execute(
        sa.text(
            "INSERT INTO ingredient_category (name_cn, name_en, sort_order, is_fallback) "
            "VALUES ('未分類', 'Uncategorised', 9999, true)"
        )
    )


def downgrade() -> None:
    op.drop_table("ingredient_label")
    op.drop_index("ix_ingredient_preservation_ingredient_id", "ingredient_preservation")
    op.drop_table("ingredient_preservation")
    op.drop_index("ix_ingredient_alias_lookup", "ingredient_alias")
    op.drop_index("ix_ingredient_alias_ingredient_id", "ingredient_alias")
    op.drop_table("ingredient_alias")
    op.drop_index("uq_ingredient_name_en", "ingredient")
    op.drop_index("uq_ingredient_name_cn", "ingredient")
    op.drop_table("ingredient")
    op.drop_index("uq_label_name_en", "label")
    op.drop_index("uq_label_name_cn", "label")
    op.drop_table("label")
    op.drop_index("uq_ingredient_category_one_fallback", "ingredient_category")
    op.drop_index("uq_ingredient_category_sibling_cn", "ingredient_category")
    op.drop_table("ingredient_category")
