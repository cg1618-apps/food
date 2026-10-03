"""recipe statuses and source platforms become managed vocabularies

Revision ID: v2ocabulary
Revises: i3import
Create Date: 2026-10-03

Two more tables of the v1ocabulary shape - recipe_status and source_platform -
because the owner wants to edit them in 設定 like courses, rather than have
them fixed in `app/constants.py`. Each is seeded from the list it replaces, in
that list's order, with the Chinese label as name_cn (YouTube and Shorts are
their own label) and sort_order 10, 20, 30 … as v1ocabulary seeds.

`recipe.status` becomes `recipe.status_id` and `recipe_source.platform`
becomes `recipe_source.platform_id`: each old string is mapped to the row
seeded for it, the column is set NOT NULL, and the string column is dropped.
Both foreign keys are RESTRICT, so a value in use cannot be deleted. The
status has no server default any more: which status comes first is the
owner's data, so the write path picks it.

A string outside the old lists cannot be in the database - the API refused
one - but if one were, the SET NOT NULL would stop the migration rather than
guess, and the transaction would leave everything as it was.

Downgrade maps each row back to its old key by name. A row whose name is not
one the old lists had - one the owner created or renamed - has no key to go
back to, and lands on the old defaults: `want_to_try` for a status, `other`
for a platform. The tables are then dropped.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "v2ocabulary"
down_revision = "i3import"
branch_labels = None
depends_on = None

# The constants these replace, copied as they were: old key -> label.
STATUSES = {"want_to_try": "想試", "can_cook": "可煮", "regular": "常煮"}
PLATFORMS = {
    "youtube": "YouTube",
    "shorts": "Shorts",
    "website": "網站",
    "book": "書",
    "other": "其他",
}

# (vocabulary table, owning table, old column, new column, old key -> label,
# the old key a row with no old key downgrades to)
MOVES = [
    ("recipe_status", "recipe", "status", "status_id", STATUSES, "want_to_try"),
    ("source_platform", "recipe_source", "platform", "platform_id", PLATFORMS, "other"),
]


def _create(table: str) -> None:
    """The v1ocabulary table shape, constraint for constraint."""
    op.create_table(
        table,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name_cn", sa.String(), nullable=True),
        sa.Column("name_en", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("num_nonnulls(name_cn, name_en) >= 1", name=f"ck_{table}_has_a_name"),
    )
    op.create_index(f"uq_{table}_name_cn", table, [sa.text("lower(name_cn)")], unique=True)
    op.create_index(f"uq_{table}_name_en", table, [sa.text("lower(name_en)")], unique=True)


def _key_case(vocabulary: str, labels: dict[str, str], fallback: str) -> str:
    """SQL mapping a vocabulary row's name back to its old key."""
    arms = " ".join(
        f"WHEN lower(v.name_cn) = lower('{label}') THEN '{key}'" for key, label in labels.items()
    )
    return f"CASE {arms} ELSE '{fallback}' END"


def upgrade() -> None:
    for vocabulary, owner, old, new, labels, _ in MOVES:
        _create(vocabulary)
        for position, label in enumerate(labels.values()):
            op.execute(
                sa.text(
                    f"INSERT INTO {vocabulary} (name_cn, sort_order) VALUES (:name, :sort)"
                ).bindparams(name=label, sort=(position + 1) * 10)
            )

        op.add_column(owner, sa.Column(new, sa.Integer(), nullable=True))
        for key, label in labels.items():
            op.execute(
                sa.text(
                    f"UPDATE {owner} SET {new} = "
                    f"(SELECT id FROM {vocabulary} WHERE name_cn = :label) "
                    f"WHERE {old} = :key"
                ).bindparams(label=label, key=key)
            )
        op.alter_column(owner, new, nullable=False)
        op.create_foreign_key(
            f"{owner}_{new}_fkey", owner, vocabulary, [new], ["id"], ondelete="RESTRICT"
        )
        op.create_index(f"ix_{owner}_{new}", owner, [new])
        op.drop_column(owner, old)


def downgrade() -> None:
    for vocabulary, owner, old, new, labels, fallback in reversed(MOVES):
        op.add_column(owner, sa.Column(old, sa.String(), nullable=True))
        op.execute(
            f"UPDATE {owner} o SET {old} = {_key_case(vocabulary, labels, fallback)} "
            f"FROM {vocabulary} v WHERE v.id = o.{new}"
        )
        op.alter_column(owner, old, nullable=False)
        op.drop_index(f"ix_{owner}_{new}", owner)
        op.drop_constraint(f"{owner}_{new}_fkey", owner, type_="foreignkey")
        op.drop_column(owner, new)

        op.drop_index(f"uq_{vocabulary}_name_en", vocabulary)
        op.drop_index(f"uq_{vocabulary}_name_cn", vocabulary)
        op.drop_table(vocabulary)

    op.alter_column("recipe", "status", server_default=sa.text("'want_to_try'"))
