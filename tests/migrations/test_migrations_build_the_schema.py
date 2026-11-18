"""The migration chain must build from nothing.

The media tracker ran for 145 revisions with a chain that could not: its
initial revision aborted its transaction on an empty database and rolled back
to zero tables, unnoticed because the test fixtures built their schema with
create_all and never ran Alembic. This test is what makes that impossible here,
and it is written before there is a single table to build.
"""

import subprocess
import sys

from sqlalchemy import inspect, text

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

# Imported for its side effect: every model registers on Base.metadata. Without
# it the comparison below sees an empty metadata whenever this file runs on its
# own, and reports every table and index as one to remove.
from app import models  # noqa: F401
from app.database import Base
from tests.migrations.conftest import ROOT


def test_upgrade_head_runs_against_an_empty_database(scratch):
    scratch.alembic("upgrade", "head")

    # A return code on its own says nothing about WHERE the run landed: a run
    # that ignored DATABASE_URL and stamped the developer's real `food`
    # database would exit 0 and this test would stay green. Reading the scratch
    # database back is what pins it.
    #
    # The expected revision is spelled out rather than read from `alembic
    # heads`, which would compare the run against the same files it came from
    # and assert nothing. It is updated by hand with each new head.
    with scratch.connect() as conn:
        stamped = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert stamped == "a3uthor"

        # No longer vacuous: it bites from i1ngredients onwards, and a
        # revision that declares a model without creating its table fails
        # here rather than at the first request that touches it.
        tables = set(inspect(conn).get_table_names())
        assert tables >= set(Base.metadata.tables), set(Base.metadata.tables) - tables


def test_there_is_exactly_one_head():
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, result.stdout
    assert "a3uthor" in lines[0], result.stdout


def test_the_migrated_schema_matches_the_models(scratch):
    """The migration and the models must describe the same database.

    The two are written by hand and separately - a migration may not import
    from `app.models` - so nothing but this makes them agree. The test above
    compares TABLE NAMES only, which a forgotten index, constraint or column
    passes straight through.

    This closes the same gap from the other side as `tests/api/conftest.py`,
    which builds its schema with `create_all` and so never runs the migration
    at all. Between them: create_all proves the models work, `upgrade head`
    proves the chain builds, and this proves they are the same thing.
    """
    scratch.alembic("upgrade", "head")

    with scratch.connect() as conn:
        context = MigrationContext.configure(conn)
        differences = compare_metadata(context, Base.metadata)

    assert differences == [], differences


def test_the_fallback_category_is_seeded_by_the_migration(scratch):
    """`ingredient.category_id` is NOT NULL, so a fresh database with no
    category can hold no ingredient at all - including the stub that module 2
    creates mid-recipe, which is the one case that must never stop to ask a
    question. The migration seeds exactly one row for that, and the partial
    unique index is what keeps it exactly one."""
    scratch.alembic("upgrade", "head")

    with scratch.connect() as conn:
        rows = conn.execute(
            text("SELECT name_cn FROM ingredient_category WHERE is_fallback")
        ).all()

    assert len(rows) == 1, rows
