"""a recipe source's creator becomes an author from a managed vocabulary

Revision ID: a1uthors
Revises: v2ocabulary
Create Date: 2026-10-03

One more table of the v1ocabulary shape - `author` - because the owner wants
authors as a 設定 vocabulary: picked in a source, renamed in one place, and
created from the recipe form by typing a name nobody has yet. Authors are
listed by name, so every row here gets sort_order 0.

`recipe_source.creator` (free text) becomes `recipe_source.author_id`,
nullable - a source may have no author - and RESTRICT, so an author in use
cannot be deleted. The content CHECK becomes num_nonnulls(author_id, url,
title) >= 1.

Each distinct creator becomes one author. Distinct means trimmed and compared
lower-cased, so "Babish" and "babish" are one author; the spelling kept is
the first one saved, by source id. A name containing Han characters, kana or
Hangul is filed as name_cn, anything else as name_en - the rule the recipe
form uses for a name typed into a new ingredient or author. A blank creator
(the API never stored one) is treated as none.

Downgrade puts back `creator` from each source's author's display name
(name_cn, else name_en), restores the old CHECK and drops the table. A source
whose creator was a later spelling of a name comes back with the first
spelling; that is the de-duplication, not a loss the downgrade could undo.

Imports nothing from `app.models`, as every revision here.
"""

import re

import sqlalchemy as sa

from alembic import op

revision = "a1uthors"
down_revision = "v2ocabulary"
branch_labels = None
depends_on = None

# frontend/src/lib/recipeLines.js's CJK class, as code points: kana, CJK
# unified ideographs (with extension A), CJK compatibility ideographs, Hangul.
CJK = re.compile("[぀-ヿ㐀-鿿豈-﫿가-힯]")

CHECK = "ck_recipe_source_has_content"


def upgrade() -> None:
    op.create_table(
        "author",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name_cn", sa.String(), nullable=True),
        sa.Column("name_en", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("num_nonnulls(name_cn, name_en) >= 1", name="ck_author_has_a_name"),
    )
    op.create_index("uq_author_name_cn", "author", [sa.text("lower(name_cn)")], unique=True)
    op.create_index("uq_author_name_en", "author", [sa.text("lower(name_en)")], unique=True)

    op.add_column("recipe_source", sa.Column("author_id", sa.Integer(), nullable=True))

    conn = op.get_bind()
    sources = conn.execute(
        sa.text("SELECT id, creator FROM recipe_source WHERE creator IS NOT NULL ORDER BY id")
    ).all()
    authors: dict[str, int] = {}
    for source_id, creator in sources:
        name = creator.strip()
        if not name:
            continue
        key = name.lower()
        if key not in authors:
            slot = "name_cn" if CJK.search(name) else "name_en"
            authors[key] = conn.execute(
                sa.text(f"INSERT INTO author ({slot}, sort_order) VALUES (:name, 0) RETURNING id"),
                {"name": name},
            ).scalar()
        conn.execute(
            sa.text("UPDATE recipe_source SET author_id = :author WHERE id = :source"),
            {"author": authors[key], "source": source_id},
        )

    op.create_foreign_key(
        "recipe_source_author_id_fkey",
        "recipe_source",
        "author",
        ["author_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_recipe_source_author_id", "recipe_source", ["author_id"])
    op.drop_constraint(CHECK, "recipe_source", type_="check")
    op.create_check_constraint(CHECK, "recipe_source", "num_nonnulls(author_id, url, title) >= 1")
    op.drop_column("recipe_source", "creator")


def downgrade() -> None:
    op.add_column("recipe_source", sa.Column("creator", sa.String(), nullable=True))
    op.execute(
        "UPDATE recipe_source rs SET creator = coalesce(a.name_cn, a.name_en) "
        "FROM author a WHERE a.id = rs.author_id"
    )
    op.drop_constraint(CHECK, "recipe_source", type_="check")
    op.create_check_constraint(CHECK, "recipe_source", "num_nonnulls(creator, url, title) >= 1")
    op.drop_index("ix_recipe_source_author_id", "recipe_source")
    op.drop_constraint("recipe_source_author_id_fkey", "recipe_source", type_="foreignkey")
    op.drop_column("recipe_source", "author_id")

    op.drop_index("uq_author_name_en", "author")
    op.drop_index("uq_author_name_cn", "author")
    op.drop_table("author")
