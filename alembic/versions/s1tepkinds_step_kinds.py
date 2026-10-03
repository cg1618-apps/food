"""a recipe step has a kind: step, optional or note

Revision ID: s1tepkinds
Revises: g1roups
Create Date: 2026-10-03

`recipe_step.kind`, a String NOT NULL with server default 'step', so every
existing step becomes an ordinary numbered one. The values (step, optional,
note) are validated by the API against STEP_KINDS, not by the database - no
Postgres enum, as across this schema. No step text is read to guess a kind:
a note the owner wrote as a step stays a step until they change it.

Downgrade drops the column. The kinds go with it; every row stays, as a step.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "s1tepkinds"
down_revision = "g1roups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recipe_step",
        sa.Column("kind", sa.String(), nullable=False, server_default=sa.text("'step'")),
    )


def downgrade() -> None:
    op.drop_column("recipe_step", "kind")
