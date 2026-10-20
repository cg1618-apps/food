"""recipe difficulty (難易度) becomes a managed vocabulary, optional on a recipe

Revision ID: d2ifficulty
Revises: r2eheat
Create Date: 2026-10-20

One more table of the v1ocabulary shape - `recipe_difficulty` - and
`recipe.difficulty_id`, nullable, a RESTRICT foreign key to it, indexed, so
a value in use cannot be deleted.

Nothing is seeded, unlike the vocabularies before it: those replaced a list
the app already had (statuses, platforms) or gave a new structure something
to start from (courses, groups), while a difficulty is optional on a recipe
and the scale - 簡單 / 普通 / 困難, or anything else - is the owner's data,
made in 設定. Every existing recipe starts with none; no row is written.

Downgrade drops the column, the index and the foreign key with it, then the
table - every recipe's difficulty and every value with them.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "d2ifficulty"
down_revision = "r2eheat"
branch_labels = None
depends_on = None

TABLE = "recipe_difficulty"


def upgrade() -> None:
    # The v1ocabulary table shape, constraint for constraint.
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name_cn", sa.String(), nullable=True),
        sa.Column("name_en", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("num_nonnulls(name_cn, name_en) >= 1", name=f"ck_{TABLE}_has_a_name"),
    )
    op.create_index(f"uq_{TABLE}_name_cn", TABLE, [sa.text("lower(name_cn)")], unique=True)
    op.create_index(f"uq_{TABLE}_name_en", TABLE, [sa.text("lower(name_en)")], unique=True)

    op.add_column("recipe", sa.Column("difficulty_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "recipe_difficulty_id_fkey", "recipe", TABLE, ["difficulty_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_recipe_difficulty_id", "recipe", ["difficulty_id"])


def downgrade() -> None:
    op.drop_index("ix_recipe_difficulty_id", "recipe")
    op.drop_constraint("recipe_difficulty_id_fkey", "recipe", type_="foreignkey")
    op.drop_column("recipe", "difficulty_id")
    op.drop_table(TABLE)
