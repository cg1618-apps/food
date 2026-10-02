"""managed vocabularies, and the starter data every select needs

Revision ID: v1ocabulary
Revises: i1ngredients
Create Date: 2026-10-02

Three small tables - recipe_course, cooking_method, equipment - and the rows
that make a fresh install usable: those three seeded from the owner's
reference sheets, plus a starter ingredient-category tree and starter labels.

Seeded here rather than by a script so production receives the same starting
vocabulary on deploy with nobody touching the box. Every seeded row is ordinary
editable data.

`ON CONFLICT DO NOTHING` on every seed: a database where the owner already
typed 肉類 or 飯 by hand must not fail on a unique index, and must keep the
owner's row as it is.

Downgrade deletes only seeded rows nothing references, then drops the tables.
It identifies seeded rows by name, so an unreferenced row the owner happened
to create with a seeded name goes too; that is accepted, because the
alternative is a marker column every row carries forever for a downgrade
nobody expects to run.
"""

import sqlalchemy as sa

from alembic import op

revision = "v1ocabulary"
down_revision = "i1ngredients"
branch_labels = None
depends_on = None

COURSES = ["主食", "配菜", "湯", "小吃點心", "甜點", "飲料", "醬料"]
METHODS = ["煮", "壓力鍋煮", "煎", "炒", "炸", "氣炸", "烤", "蒸", "川燙", "涼拌", "微波", "混合"]
EQUIPMENT = [
    "鍋子", "壓力鍋", "平底鍋", "氣炸鍋", "烤箱", "油鍋", "果汁機", "電鍋", "微波爐", "保鮮盒", "碗",
]
CATEGORIES = [
    "肉類", "海鮮", "蔬菜", "菇類", "水果", "蛋豆製品", "主食穀物", "調味料", "乳製品", "乾貨",
]
LABELS = ["飯", "麵", "肉", "麵包", "馬鈴薯", "地瓜", "沙拉", "鍋"]

TABLES = ["recipe_course", "cooking_method", "equipment"]


def _create(table: str) -> None:
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


def _seed(table: str, names: list[str]) -> None:
    for position, name in enumerate(names):
        op.execute(
            sa.text(
                f"INSERT INTO {table} (name_cn, sort_order) "
                "VALUES (:name, :sort) ON CONFLICT DO NOTHING"
            ).bindparams(name=name, sort=(position + 1) * 10)
        )


def upgrade() -> None:
    for table in TABLES:
        _create(table)
    _seed("recipe_course", COURSES)
    _seed("cooking_method", METHODS)
    _seed("equipment", EQUIPMENT)
    _seed("ingredient_category", CATEGORIES)
    for name in LABELS:
        op.execute(
            sa.text("INSERT INTO label (name_cn) VALUES (:name) ON CONFLICT DO NOTHING").bindparams(
                name=name
            )
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM label WHERE name_cn = ANY(:names) "
            "AND NOT EXISTS (SELECT 1 FROM ingredient_label l WHERE l.label_id = label.id)"
        ).bindparams(names=LABELS)
    )
    op.execute(
        sa.text(
            "DELETE FROM ingredient_category c WHERE c.name_cn = ANY(:names) "
            "AND c.parent_id IS NULL AND NOT c.is_fallback "
            "AND NOT EXISTS (SELECT 1 FROM ingredient i WHERE i.category_id = c.id) "
            "AND NOT EXISTS (SELECT 1 FROM ingredient_category k WHERE k.parent_id = c.id)"
        ).bindparams(names=CATEGORIES)
    )
    for table in reversed(TABLES):
        op.drop_index(f"uq_{table}_name_en", table)
        op.drop_index(f"uq_{table}_name_cn", table)
        op.drop_table(table)
