"""baseline

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-19

"""

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Deliberately empty.

    The chain has to exist before the first table does, so that the from-zero
    test is meaningful from the first commit rather than from whenever someone
    remembers to add it.
    """


def downgrade() -> None:
    """Also empty; there is nothing to reverse."""
