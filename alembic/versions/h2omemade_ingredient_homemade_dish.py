"""ingredients: a homemade version, the dish that makes the bought thing

Revision ID: h2omemade
Revises: c2ategory
Create Date: 2026-10-12

`ingredient.homemade_dish_id`, a nullable Integer -> `dish.id`, indexed,
`ON DELETE SET NULL`. Caramel, 雞高湯 and 油蔥酥 can be bought or made: the
bought thing is an ingredient, the made one is a dish (usually a 醬料), and
this column links the two. Not unique - making 油蔥酥 also yields 紅蔥油, so
one dish may be the homemade version of several ingredients.

SET NULL rather than RESTRICT: the link is a cross-reference, not a usage,
so deleting a dish never has to wait for it to be unlinked in the
ingredient library first.

Every existing ingredient starts with none; nothing is guessed from names.
Downgrade drops the column, and every link with it.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "h2omemade"
down_revision = "c2ategory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ingredient", sa.Column("homemade_dish_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "ingredient_homemade_dish_id_fkey", "ingredient", "dish", ["homemade_dish_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_ingredient_homemade_dish_id", "ingredient", ["homemade_dish_id"])


def downgrade() -> None:
    op.drop_index("ix_ingredient_homemade_dish_id", "ingredient")
    op.drop_constraint("ingredient_homemade_dish_id_fkey", "ingredient", type_="foreignkey")
    op.drop_column("ingredient", "homemade_dish_id")
