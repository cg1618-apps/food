"""recipes

Revision ID: r1recipes
Revises: m1images
Create Date: 2026-10-02

The recipe library: the recipe, its aliases, sources, ingredient lines and
steps, its links to courses, labels, cooking methods and equipment, and its
gallery. Written by hand and importing nothing from `app.models`, as every
revision here is.

Three things a reader should not take from the shape of the diff:

- Recipe names are NOT unique and carry no name index. Versions of one dish
  share its name; every other named table in this app is the opposite.
- The deletion rules differ per foreign key and the difference is the design.
  What a recipe owns CASCADEs; what it names - an ingredient, a base recipe
  (`recipe_line.sub_recipe_id`), its course, a method, equipment - is
  RESTRICT; a version's `variant_of_id` is SET NULL; serves-as and label
  links CASCADE from both sides. `recipe_line` references `recipe` twice, once
  each way.
- The CHECKs only cover what one row can state. "A version is one level deep"
  and "the nesting graph does not cycle" need other rows, and are refused on
  the write path.

Downgrade drops all ten tables and every recipe in them; there is nowhere to
keep the data. The pictures a recipe gallery attached stay in `image` and on
disk - only the attachments go.
"""

import sqlalchemy as sa

from alembic import op

revision = "r1recipes"
down_revision = "m1images"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recipe",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name_cn", sa.String(), nullable=True),
        sa.Column("name_en", sa.String(), nullable=True),
        sa.Column("name_alt", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False, server_default=sa.text("'dish'")),
        sa.Column("course_id", sa.Integer(), nullable=True),
        sa.Column("variant_of_id", sa.Integer(), nullable=True),
        sa.Column(
            "status", sa.String(), nullable=False, server_default=sa.text("'want_to_try'")
        ),
        sa.Column("servings", sa.String(), nullable=True),
        sa.Column("time", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("storage_notes", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["course_id"], ["recipe_course.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["variant_of_id"], ["recipe.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "num_nonnulls(name_cn, name_en, name_alt) >= 1", name="ck_recipe_has_a_name"
        ),
        sa.CheckConstraint(
            "variant_of_id IS NULL OR variant_of_id <> id", name="ck_recipe_not_its_own_version"
        ),
    )
    op.create_index("ix_recipe_course_id", "recipe", ["course_id"])
    op.create_index("ix_recipe_variant_of_id", "recipe", ["variant_of_id"])

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
    op.create_table(
        "recipe_label",
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("recipe_id", "label_id"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["label_id"], ["label.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "recipe_method",
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("method_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("recipe_id", "method_id"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["method_id"], ["cooking_method.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "recipe_equipment",
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("recipe_id", "equipment_id"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="RESTRICT"),
    )

    op.create_table(
        "recipe_source",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("creator", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "num_nonnulls(creator, url, title) >= 1", name="ck_recipe_source_has_content"
        ),
    )
    op.create_index("ix_recipe_source_recipe_id", "recipe_source", ["recipe_id"])

    op.create_table(
        "recipe_line",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(), nullable=True),
        sa.Column("ingredient_id", sa.Integer(), nullable=True),
        sa.Column("sub_recipe_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.String(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column(
            "is_optional", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sub_recipe_id"], ["recipe.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("recipe_id", "position", name="uq_recipe_line_position"),
        sa.CheckConstraint(
            "num_nonnulls(ingredient_id, sub_recipe_id) = 1", name="ck_recipe_line_one_target"
        ),
        sa.CheckConstraint(
            "sub_recipe_id IS NULL OR sub_recipe_id <> recipe_id",
            name="ck_recipe_line_not_itself",
        ),
    )
    op.create_index("ix_recipe_line_recipe_id", "recipe_line", ["recipe_id"])
    op.create_index("ix_recipe_line_ingredient_id", "recipe_line", ["ingredient_id"])
    op.create_index("ix_recipe_line_sub_recipe_id", "recipe_line", ["sub_recipe_id"])

    op.create_table(
        "recipe_step",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("recipe_id", "position", name="uq_recipe_step_position"),
    )
    op.create_index("ix_recipe_step_recipe_id", "recipe_step", ["recipe_id"])

    op.create_table(
        "recipe_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("focus", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["image_id"], ["image.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("recipe_id", "position", name="uq_recipe_image_position"),
        sa.UniqueConstraint("recipe_id", "image_id", name="uq_recipe_image_once"),
    )
    op.create_index("ix_recipe_image_recipe_id", "recipe_image", ["recipe_id"])
    op.create_index("ix_recipe_image_image_id", "recipe_image", ["image_id"])


def downgrade() -> None:
    op.drop_index("ix_recipe_image_image_id", "recipe_image")
    op.drop_index("ix_recipe_image_recipe_id", "recipe_image")
    op.drop_table("recipe_image")
    op.drop_index("ix_recipe_step_recipe_id", "recipe_step")
    op.drop_table("recipe_step")
    op.drop_index("ix_recipe_line_sub_recipe_id", "recipe_line")
    op.drop_index("ix_recipe_line_ingredient_id", "recipe_line")
    op.drop_index("ix_recipe_line_recipe_id", "recipe_line")
    op.drop_table("recipe_line")
    op.drop_index("ix_recipe_source_recipe_id", "recipe_source")
    op.drop_table("recipe_source")
    op.drop_table("recipe_equipment")
    op.drop_table("recipe_method")
    op.drop_table("recipe_label")
    op.drop_table("recipe_serves_as")
    op.drop_index("ix_recipe_alias_lookup", "recipe_alias")
    op.drop_index("ix_recipe_alias_recipe_id", "recipe_alias")
    op.drop_table("recipe_alias")
    op.drop_index("ix_recipe_variant_of_id", "recipe")
    op.drop_index("ix_recipe_course_id", "recipe")
    op.drop_table("recipe")
