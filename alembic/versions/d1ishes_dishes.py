"""dishes: a recipe is a specific way of making a dish

Revision ID: d1ishes
Revises: t1bd
Create Date: 2026-10-03

New tables: `region` (地區, the v1ocabulary shape, seeded 台式, 中式, 日式,
韓式, 泰式, 西式 at sort_order 10..60), `dish` (three name slots, `kind`
'dish' or 'sauce', `course_id` and `region_id` RESTRICT, `description`, the
timestamps), and the dish's `dish_alias`, `dish_serves_as`, `dish_label` and
`dish_image`, each the shape of the recipe table it replaces.

`recipe` gains `dish_id` (NOT NULL, RESTRICT) and an optional `name`, and
loses its name slots, `kind`, `course_id`, `variant_of_id` and `description`;
`recipe_alias`, `recipe_label` and `recipe_serves_as` are dropped.
`recipe_line.sub_recipe_id` becomes `sub_dish_id` (RESTRICT), keeping the
exactly-one-target CHECK; `ck_recipe_line_not_itself` goes - "a recipe may not
use its own dish" needs the recipe row, so the write path holds it.

The grouping. Recipes linked through `variant_of_id` form a family - each
connected component of that graph - and each family becomes one dish. Its
ROOT, the recipe with no `variant_of_id` (the lowest id when there are several
or a cycle), gives the dish its names, aliases, course, serves-as and
description, and its kind with 'base' renamed 'sauce'. The dish's labels are
the UNION of the family's. Every recipe of the family points at the dish. The
root's `name` is null; any other recipe keeps its old display name as `name`
when that differs from the dish's display name, and a description of its own
that differs from the root's is appended to its notes after 「原簡介：」, so no
text is lost. A line's `sub_recipe_id` becomes that recipe's dish. Dish
galleries start empty; a dish shows its first recipe's cover until it has
pictures of its own.

What the grouping does not carry: a non-root recipe's aliases, and its name
slots other than the one that was its display name - the dish takes the
root's.

Downgrade puts the dish back onto every recipe of it: the dish's name slots
(or the recipe's own `name`, in `name_cn`, when it has one), kind ('sauce'
back to 'base'), course, description, aliases, labels and serves-as. The
lowest-id recipe of a dish is its original and every other recipe becomes a
version of it. A line naming a dish names that dish's lowest-id recipe other
than the line's own. What cannot come back, and is dropped: a dish with no
recipe, a line naming one (or naming only its own recipe's dish), the
dish galleries (the pictures stay in the library), the region, and the
「原簡介：」 split - an appended description stays in the notes.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "d1ishes"
down_revision = "t1bd"
branch_labels = None
depends_on = None

REGIONS = ["台式", "中式", "日式", "韓式", "泰式", "西式"]


def _display(*names):
    for name in names:
        if name and name.strip():
            return name
    return ""


def _create_region() -> None:
    op.create_table(
        "region",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name_cn", sa.String(), nullable=True),
        sa.Column("name_en", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("num_nonnulls(name_cn, name_en) >= 1", name="ck_region_has_a_name"),
    )
    op.create_index("uq_region_name_cn", "region", [sa.text("lower(name_cn)")], unique=True)
    op.create_index("uq_region_name_en", "region", [sa.text("lower(name_en)")], unique=True)
    for position, name in enumerate(REGIONS):
        op.execute(
            sa.text(
                "INSERT INTO region (name_cn, sort_order) VALUES (:name, :sort) "
                "ON CONFLICT DO NOTHING"
            ).bindparams(name=name, sort=(position + 1) * 10)
        )


def _create_dish_tables() -> None:
    op.create_table(
        "dish",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name_cn", sa.String(), nullable=True),
        sa.Column("name_en", sa.String(), nullable=True),
        sa.Column("name_alt", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False, server_default=sa.text("'dish'")),
        sa.Column("course_id", sa.Integer(), nullable=True),
        sa.Column("region_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["course_id"], ["recipe_course.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["region_id"], ["region.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "num_nonnulls(name_cn, name_en, name_alt) >= 1", name="ck_dish_has_a_name"
        ),
    )
    op.create_index("ix_dish_course_id", "dish", ["course_id"])
    op.create_index("ix_dish_region_id", "dish", ["region_id"])

    op.create_table(
        "dish_alias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dish_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["dish_id"], ["dish.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("dish_id", "value", name="uq_dish_alias"),
    )
    op.create_index("ix_dish_alias_dish_id", "dish_alias", ["dish_id"])
    op.create_index("ix_dish_alias_lookup", "dish_alias", [sa.text("lower(value)")])

    op.create_table(
        "dish_serves_as",
        sa.Column("dish_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("dish_id", "course_id"),
        sa.ForeignKeyConstraint(["dish_id"], ["dish.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["recipe_course.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_dish_serves_as_course_id", "dish_serves_as", ["course_id"])
    op.create_table(
        "dish_label",
        sa.Column("dish_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("dish_id", "label_id"),
        sa.ForeignKeyConstraint(["dish_id"], ["dish.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["label_id"], ["label.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_dish_label_label_id", "dish_label", ["label_id"])

    op.create_table(
        "dish_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dish_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("focus", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["dish_id"], ["dish.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["image_id"], ["image.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("dish_id", "position", name="uq_dish_image_position"),
        sa.UniqueConstraint("dish_id", "image_id", name="uq_dish_image_once"),
    )
    op.create_index("ix_dish_image_dish_id", "dish_image", ["dish_id"])
    op.create_index("ix_dish_image_image_id", "dish_image", ["image_id"])


def _families(recipes: list) -> dict[int, list]:
    """Root recipe id -> the recipes of its family, in id order.

    Union-find over `variant_of_id`, which the write path kept one level deep
    but which nothing in the database stops being deeper or cyclic.
    """
    parent = {r.id: r.id for r in recipes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for r in recipes:
        if r.variant_of_id is not None and r.variant_of_id in parent:
            a, b = find(r.id), find(r.variant_of_id)
            if a != b:
                parent[max(a, b)] = min(a, b)

    components: dict[int, list] = {}
    for r in sorted(recipes, key=lambda r: r.id):
        components.setdefault(find(r.id), []).append(r)
    families = {}
    for members in components.values():
        roots = [r for r in members if r.variant_of_id is None or r.variant_of_id not in parent]
        root = min(roots or members, key=lambda r: r.id)
        families[root.id] = members
    return families


def _group_into_dishes(conn) -> None:
    recipes = conn.execute(
        sa.text(
            "SELECT id, name_cn, name_en, name_alt, kind, course_id, variant_of_id, "
            "description, notes FROM recipe ORDER BY id"
        )
    ).all()
    dish_of: dict[int, int] = {}
    for root_id, members in _families(recipes).items():
        root = next(r for r in members if r.id == root_id)
        dish_id = conn.execute(
            sa.text(
                "INSERT INTO dish (name_cn, name_en, name_alt, kind, course_id, description, "
                "created_at, updated_at) "
                "SELECT name_cn, name_en, name_alt, :kind, course_id, description, "
                "created_at, updated_at FROM recipe WHERE id = :r RETURNING id"
            ),
            {"r": root.id, "kind": "sauce" if root.kind == "base" else "dish"},
        ).scalar()
        conn.execute(
            sa.text(
                "INSERT INTO dish_alias (dish_id, value) "
                "SELECT :d, value FROM recipe_alias WHERE recipe_id = :r ORDER BY id"
            ),
            {"d": dish_id, "r": root.id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO dish_serves_as (dish_id, course_id) "
                "SELECT :d, course_id FROM recipe_serves_as WHERE recipe_id = :r"
            ),
            {"d": dish_id, "r": root.id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO dish_label (dish_id, label_id) "
                "SELECT DISTINCT :d, label_id FROM recipe_label WHERE recipe_id = ANY(:ids)"
            ),
            {"d": dish_id, "ids": [r.id for r in members]},
        )
        dish_name = _display(root.name_cn, root.name_en, root.name_alt)
        for r in members:
            dish_of[r.id] = dish_id
            name, notes = None, r.notes
            if r.id != root.id:
                own = _display(r.name_cn, r.name_en, r.name_alt)
                name = own if own and own != dish_name else None
                if r.description and r.description.strip() and r.description != root.description:
                    appended = f"原簡介：{r.description}"
                    notes = f"{notes}\n\n{appended}" if notes and notes.strip() else appended
            conn.execute(
                sa.text("UPDATE recipe SET dish_id = :d, name = :n, notes = :notes WHERE id = :r"),
                {"d": dish_id, "n": name, "notes": notes, "r": r.id},
            )

    for line_id, sub_id in conn.execute(
        sa.text("SELECT id, sub_recipe_id FROM recipe_line WHERE sub_recipe_id IS NOT NULL")
    ).all():
        conn.execute(
            sa.text("UPDATE recipe_line SET sub_dish_id = :d WHERE id = :l"),
            {"d": dish_of[sub_id], "l": line_id},
        )


def upgrade() -> None:
    _create_region()
    _create_dish_tables()

    op.add_column("recipe", sa.Column("dish_id", sa.Integer(), nullable=True))
    op.add_column("recipe", sa.Column("name", sa.String(), nullable=True))
    op.add_column("recipe_line", sa.Column("sub_dish_id", sa.Integer(), nullable=True))

    _group_into_dishes(op.get_bind())

    # recipe_line: the target moves from a recipe to a dish.
    op.drop_constraint("ck_recipe_line_not_itself", "recipe_line", type_="check")
    op.drop_constraint("ck_recipe_line_one_target", "recipe_line", type_="check")
    op.drop_index("ix_recipe_line_sub_recipe_id", "recipe_line")
    op.drop_column("recipe_line", "sub_recipe_id")
    op.create_foreign_key(
        "recipe_line_sub_dish_id_fkey", "recipe_line", "dish", ["sub_dish_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_recipe_line_sub_dish_id", "recipe_line", ["sub_dish_id"])
    op.create_check_constraint(
        "ck_recipe_line_one_target", "recipe_line", "num_nonnulls(ingredient_id, sub_dish_id) = 1"
    )

    # recipe: what moved to the dish goes.
    op.drop_index("ix_recipe_alias_lookup", "recipe_alias")
    op.drop_index("ix_recipe_alias_recipe_id", "recipe_alias")
    op.drop_table("recipe_alias")
    op.drop_index("ix_recipe_label_label_id", "recipe_label")
    op.drop_table("recipe_label")
    op.drop_index("ix_recipe_serves_as_course_id", "recipe_serves_as")
    op.drop_table("recipe_serves_as")
    op.drop_constraint("ck_recipe_has_a_name", "recipe", type_="check")
    op.drop_constraint("ck_recipe_not_its_own_version", "recipe", type_="check")
    op.drop_index("ix_recipe_variant_of_id", "recipe")
    op.drop_index("ix_recipe_course_id", "recipe")
    for column in ("variant_of_id", "course_id", "kind", "name_cn", "name_en", "name_alt", "description"):
        op.drop_column("recipe", column)
    op.alter_column("recipe", "dish_id", nullable=False)
    op.create_foreign_key(
        "recipe_dish_id_fkey", "recipe", "dish", ["dish_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_recipe_dish_id", "recipe", ["dish_id"])


def _spread_dishes_onto_recipes(conn) -> None:
    dishes = {
        d.id: d
        for d in conn.execute(
            sa.text("SELECT id, name_cn, name_en, name_alt, kind, course_id, description FROM dish")
        ).all()
    }
    by_dish: dict[int, list[int]] = {}
    for recipe_id, dish_id, name in conn.execute(
        sa.text("SELECT id, dish_id, name FROM recipe ORDER BY id")
    ).all():
        by_dish.setdefault(dish_id, []).append(recipe_id)
        dish = dishes[dish_id]
        slots = (name, None, None) if name and name.strip() else (
            dish.name_cn, dish.name_en, dish.name_alt
        )
        conn.execute(
            sa.text(
                "UPDATE recipe SET name_cn = :cn, name_en = :en, name_alt = :alt, kind = :kind, "
                "course_id = :course, description = :description, variant_of_id = :original "
                "WHERE id = :r"
            ),
            {
                "cn": slots[0],
                "en": slots[1],
                "alt": slots[2],
                "kind": "base" if dish.kind == "sauce" else "dish",
                "course": dish.course_id,
                "description": dish.description,
                "original": None,
                "r": recipe_id,
            },
        )
    for dish_id, recipe_ids in by_dish.items():
        original, *versions = recipe_ids
        if versions:
            conn.execute(
                sa.text("UPDATE recipe SET variant_of_id = :o WHERE id = ANY(:ids)"),
                {"o": original, "ids": versions},
            )
        for table, column, source in (
            ("recipe_alias", "value", "dish_alias"),
            ("recipe_label", "label_id", "dish_label"),
            ("recipe_serves_as", "course_id", "dish_serves_as"),
        ):
            conn.execute(
                sa.text(
                    f"INSERT INTO {table} (recipe_id, {column}) "
                    f"SELECT r, s.{column} FROM unnest(CAST(:ids AS integer[])) AS r "
                    f"CROSS JOIN {source} s WHERE s.dish_id = :d"
                ),
                {"ids": recipe_ids, "d": dish_id},
            )

    for line_id, recipe_id, dish_id in conn.execute(
        sa.text("SELECT id, recipe_id, sub_dish_id FROM recipe_line WHERE sub_dish_id IS NOT NULL")
    ).all():
        target = next((r for r in by_dish.get(dish_id, []) if r != recipe_id), None)
        if target is None:
            conn.execute(sa.text("DELETE FROM recipe_line WHERE id = :l"), {"l": line_id})
        else:
            conn.execute(
                sa.text("UPDATE recipe_line SET sub_recipe_id = :s WHERE id = :l"),
                {"s": target, "l": line_id},
            )


def downgrade() -> None:
    op.add_column("recipe", sa.Column("name_cn", sa.String(), nullable=True))
    op.add_column("recipe", sa.Column("name_en", sa.String(), nullable=True))
    op.add_column("recipe", sa.Column("name_alt", sa.String(), nullable=True))
    op.add_column(
        "recipe", sa.Column("kind", sa.String(), nullable=False, server_default=sa.text("'dish'"))
    )
    op.add_column("recipe", sa.Column("course_id", sa.Integer(), nullable=True))
    op.add_column("recipe", sa.Column("variant_of_id", sa.Integer(), nullable=True))
    op.add_column("recipe", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("recipe_line", sa.Column("sub_recipe_id", sa.Integer(), nullable=True))

    op.create_table(
        "recipe_alias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("recipe_id", "value", name="uq_recipe_alias"),
    )
    op.create_index("ix_recipe_alias_recipe_id", "recipe_alias", ["recipe_id"])
    op.create_index("ix_recipe_alias_lookup", "recipe_alias", [sa.text("lower(value)")])
    op.create_table(
        "recipe_serves_as",
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("recipe_id", "course_id"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["recipe_course.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_recipe_serves_as_course_id", "recipe_serves_as", ["course_id"])
    op.create_table(
        "recipe_label",
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("recipe_id", "label_id"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["label_id"], ["label.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_recipe_label_label_id", "recipe_label", ["label_id"])

    _spread_dishes_onto_recipes(op.get_bind())

    op.drop_index("ix_recipe_dish_id", "recipe")
    op.drop_constraint("recipe_dish_id_fkey", "recipe", type_="foreignkey")
    op.drop_column("recipe", "dish_id")
    op.drop_column("recipe", "name")
    op.create_foreign_key(
        "recipe_course_id_fkey", "recipe", "recipe_course", ["course_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "recipe_variant_of_id_fkey", "recipe", "recipe", ["variant_of_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_recipe_course_id", "recipe", ["course_id"])
    op.create_index("ix_recipe_variant_of_id", "recipe", ["variant_of_id"])
    op.create_check_constraint(
        "ck_recipe_has_a_name", "recipe", "num_nonnulls(name_cn, name_en, name_alt) >= 1"
    )
    op.create_check_constraint(
        "ck_recipe_not_its_own_version", "recipe", "variant_of_id IS NULL OR variant_of_id <> id"
    )

    op.drop_constraint("ck_recipe_line_one_target", "recipe_line", type_="check")
    op.drop_index("ix_recipe_line_sub_dish_id", "recipe_line")
    op.drop_constraint("recipe_line_sub_dish_id_fkey", "recipe_line", type_="foreignkey")
    op.drop_column("recipe_line", "sub_dish_id")
    op.create_foreign_key(
        "recipe_line_sub_recipe_id_fkey", "recipe_line", "recipe", ["sub_recipe_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_recipe_line_sub_recipe_id", "recipe_line", ["sub_recipe_id"])
    op.create_check_constraint(
        "ck_recipe_line_one_target", "recipe_line", "num_nonnulls(ingredient_id, sub_recipe_id) = 1"
    )
    op.create_check_constraint(
        "ck_recipe_line_not_itself", "recipe_line", "sub_recipe_id IS NULL OR sub_recipe_id <> recipe_id"
    )

    op.drop_index("ix_dish_image_image_id", "dish_image")
    op.drop_index("ix_dish_image_dish_id", "dish_image")
    op.drop_table("dish_image")
    op.drop_index("ix_dish_label_label_id", "dish_label")
    op.drop_table("dish_label")
    op.drop_index("ix_dish_serves_as_course_id", "dish_serves_as")
    op.drop_table("dish_serves_as")
    op.drop_index("ix_dish_alias_lookup", "dish_alias")
    op.drop_index("ix_dish_alias_dish_id", "dish_alias")
    op.drop_table("dish_alias")
    op.drop_index("ix_dish_region_id", "dish")
    op.drop_index("ix_dish_course_id", "dish")
    op.drop_table("dish")
    op.drop_index("uq_region_name_en", "region")
    op.drop_index("uq_region_name_cn", "region")
    op.drop_table("region")
