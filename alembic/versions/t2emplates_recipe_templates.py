"""recipe templates: named skeletons a new recipe can start from

Revision ID: t2emplates
Revises: d1ishes
Create Date: 2026-10-03

New table `recipe_template`: a NOT NULL `name`, refused when blank by
`ck_recipe_template_has_a_name` and unique case-insensitively through the
expression index `uq_recipe_template_name` on lower(name); a NOT NULL
`sort_order`; a NOT NULL JSONB `body` holding the recipe-shaped skeleton; the
timestamps every entity here carries. Nothing references the table, and the
body's ids are not foreign keys - the service drops a reference that no longer
exists when it reads a template.

Nothing is seeded and no existing row changes. Downgrade drops the table and
every template in it; nothing else is touched.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "t2emplates"
down_revision = "d1ishes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recipe_template",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_recipe_template_has_a_name"),
    )
    op.create_index(
        "uq_recipe_template_name",
        "recipe_template",
        [sa.text("lower(name)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_recipe_template_name", "recipe_template")
    op.drop_table("recipe_template")
