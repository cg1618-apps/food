"""a recipe's ingredient lines and steps sit in real groups

Revision ID: g1roups
Revises: a1uthors
Create Date: 2026-10-03

Two more tables of the v1ocabulary shape - `line_group` (材料分組, seeded 主料,
配料, 調味料) and `step_group` (步驟分組, seeded 備料, 烹飪, 醬汁), sort_order
10, 20, 30 - and two per-recipe group tables, `recipe_line_group` and
`recipe_step_group`. A group names a value (RESTRICT) or carries a one-off
`name`, exactly one of the two; a recipe holds a value once and a one-off
name once, case-insensitively. `recipe_line.section` and
`recipe_step.section` (free text) give way to `group_id`, SET NULL.

Each recipe's distinct non-blank sections, trimmed and compared lower-cased,
become its groups in first-use order - separately for lines and steps - the
first spelling kept. A section matching a seeded value's name in any case
becomes that value; any other is a one-off name. Rows keep their relative
order and are re-positioned through the recipe in the order the page now
shows them: ungrouped rows first, then group by group. Rows without a
section stay ungrouped.

Downgrade puts each grouped row's group display name (the value's name_cn,
else its name_en, else the one-off name) back into `section`, re-positions
the rows the same way - ungrouped first, then by group - and drops the four
tables. A section that was a later spelling of a name comes back with the
first spelling; that is the de-duplication, not a loss the downgrade could
undo. An empty group has no row to carry its name and is not restored.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "g1roups"
down_revision = "a1uthors"
branch_labels = None
depends_on = None

# (vocabulary, seeded names, recipe group table, owning row table)
PAIRS = [
    ("line_group", ["主料", "配料", "調味料"], "recipe_line_group", "recipe_line"),
    ("step_group", ["備料", "烹飪", "醬汁"], "recipe_step_group", "recipe_step"),
]


def _create_vocabulary(table: str, names: list[str]) -> None:
    """The v1ocabulary table shape, constraint for constraint, seeded."""
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
    for position, name in enumerate(names):
        op.execute(
            sa.text(f"INSERT INTO {table} (name_cn, sort_order) VALUES (:name, :sort)").bindparams(
                name=name, sort=(position + 1) * 10
            )
        )


def _create_groups(table: str, vocabulary: str) -> None:
    value = f"{vocabulary}_id"
    op.create_table(
        table,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(value, sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint([value], [f"{vocabulary}.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("recipe_id", "position", name=f"uq_{table}_position"),
        sa.UniqueConstraint("recipe_id", value, name=f"uq_{table}_value"),
        sa.CheckConstraint(f"num_nonnulls({value}, name) = 1", name=f"ck_{table}_one_name"),
    )
    op.create_index(f"ix_{table}_recipe_id", table, ["recipe_id"])
    op.create_index(f"ix_{table}_{value}", table, [value])
    op.create_index(f"uq_{table}_name", table, ["recipe_id", sa.text("lower(name)")], unique=True)


def _reposition(conn, rows: str, ordered: list[tuple[int, int]]) -> None:
    """Set `(row id, new position)` without tripping the per-recipe unique on
    position halfway: every row goes negative first, then to its place."""
    for row_id, position in ordered:
        conn.execute(
            sa.text(f"UPDATE {rows} SET position = :p WHERE id = :i"),
            {"p": -position - 1, "i": row_id},
        )
    conn.execute(sa.text(f"UPDATE {rows} SET position = -position - 1 WHERE position < 0"))


def _display_order(conn, rows: str, groups: str) -> list[tuple[int, int]]:
    """Every row's id and its position in display order, per recipe:
    ungrouped first, then by group position, rows by their own position."""
    found = conn.execute(
        sa.text(
            f"SELECT r.id, r.recipe_id FROM {rows} r LEFT JOIN {groups} g ON g.id = r.group_id "
            "ORDER BY r.recipe_id, r.group_id IS NOT NULL, g.position, r.position"
        )
    ).all()
    ordered, recipe, position = [], None, 0
    for row_id, recipe_id in found:
        if recipe_id != recipe:
            recipe, position = recipe_id, 0
        ordered.append((row_id, position))
        position += 1
    return ordered


def upgrade() -> None:
    conn = op.get_bind()
    for vocabulary, names, groups, rows in PAIRS:
        _create_vocabulary(vocabulary, names)
        _create_groups(groups, vocabulary)
        op.add_column(rows, sa.Column("group_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"{rows}_group_id_fkey", rows, groups, ["group_id"], ["id"], ondelete="SET NULL"
        )
        op.create_index(f"ix_{rows}_group_id", rows, ["group_id"])

        values = {
            name.lower(): value_id
            for value_id, name_cn, name_en in conn.execute(
                sa.text(f"SELECT id, name_cn, name_en FROM {vocabulary} ORDER BY id")
            )
            for name in (name_cn, name_en)
            if name
        }
        found = conn.execute(
            sa.text(
                f"SELECT id, recipe_id, section FROM {rows} "
                "WHERE section IS NOT NULL ORDER BY recipe_id, position"
            )
        ).all()
        made: dict[tuple[int, str], int] = {}
        next_position: dict[int, int] = {}
        for row_id, recipe_id, section in found:
            name = section.strip()
            if not name:
                continue
            key = (recipe_id, name.lower())
            if key not in made:
                position = next_position.get(recipe_id, 0)
                next_position[recipe_id] = position + 1
                value_id = values.get(name.lower())
                made[key] = conn.execute(
                    sa.text(
                        f"INSERT INTO {groups} (recipe_id, position, {vocabulary}_id, name) "
                        "VALUES (:r, :p, :v, :n) RETURNING id"
                    ),
                    {
                        "r": recipe_id,
                        "p": position,
                        "v": value_id,
                        "n": None if value_id else name,
                    },
                ).scalar()
            conn.execute(
                sa.text(f"UPDATE {rows} SET group_id = :g WHERE id = :i"),
                {"g": made[key], "i": row_id},
            )

        _reposition(conn, rows, _display_order(conn, rows, groups))
        op.drop_column(rows, "section")


def downgrade() -> None:
    conn = op.get_bind()
    for vocabulary, _, groups, rows in reversed(PAIRS):
        op.add_column(rows, sa.Column("section", sa.String(), nullable=True))
        op.execute(
            f"UPDATE {rows} r SET section = coalesce(v.name_cn, v.name_en, g.name) "
            f"FROM {groups} g LEFT JOIN {vocabulary} v ON v.id = g.{vocabulary}_id "
            "WHERE g.id = r.group_id"
        )
        _reposition(conn, rows, _display_order(conn, rows, groups))

        op.drop_index(f"ix_{rows}_group_id", rows)
        op.drop_constraint(f"{rows}_group_id_fkey", rows, type_="foreignkey")
        op.drop_column(rows, "group_id")

        op.drop_index(f"uq_{groups}_name", groups)
        op.drop_index(f"ix_{groups}_{vocabulary}_id", groups)
        op.drop_index(f"ix_{groups}_recipe_id", groups)
        op.drop_table(groups)

        op.drop_index(f"uq_{vocabulary}_name_en", vocabulary)
        op.drop_index(f"uq_{vocabulary}_name_cn", vocabulary)
        op.drop_table(vocabulary)
