"""常用食材 groups: named, ordered groups of chips

Revision ID: c3ommon
Revises: t3emplates
Create Date: 2026-10-21

`common_ingredient_group`: id, a required `name` (CHECK btrim(name) <> '',
and a unique index on lower(name)) and a NOT NULL `sort_order`.

`common_ingredient.group_id`: nullable, indexed, a foreign key to it with ON
DELETE SET NULL - a group deleted leaves its chips, ungrouped. A chip's
`sort_order` is now its place within its group, or within 未分組 when it has
none. Every existing chip is ungrouped and keeps its `sort_order`, so the
list reads exactly as before until a group is made. No group is created.

Downgrade keeps every chip and drops the groups: the chips are renumbered
into one list - 未分組 first, then each group's in group order, each in its
own order - before `group_id` and the table go. The group names are lost;
no chip is.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "c3ommon"
down_revision = "t3emplates"
branch_labels = None
depends_on = None

TABLE = "common_ingredient_group"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_common_ingredient_group_has_a_name"),
    )
    op.create_index(
        "uq_common_ingredient_group_name", TABLE, [sa.text("lower(name)")], unique=True
    )

    op.add_column("common_ingredient", sa.Column("group_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "common_ingredient_group_id_fkey",
        "common_ingredient",
        TABLE,
        ["group_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_common_ingredient_group_id", "common_ingredient", ["group_id"])


def downgrade() -> None:
    op.execute(
        """
        UPDATE common_ingredient AS c
        SET sort_order = flat.position
        FROM (
            SELECT ci.ingredient_id,
                   row_number() OVER (
                       ORDER BY ci.group_id IS NOT NULL, g.sort_order, g.id,
                                ci.sort_order, ci.ingredient_id
                   ) - 1 AS position
            FROM common_ingredient AS ci
            LEFT JOIN common_ingredient_group AS g ON g.id = ci.group_id
        ) AS flat
        WHERE c.ingredient_id = flat.ingredient_id
        """
    )
    op.drop_index("ix_common_ingredient_group_id", "common_ingredient")
    op.drop_constraint("common_ingredient_group_id_fkey", "common_ingredient", type_="foreignkey")
    op.drop_column("common_ingredient", "group_id")
    op.drop_table(TABLE)
