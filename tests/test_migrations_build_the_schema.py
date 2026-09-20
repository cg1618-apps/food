"""The migration chain must build from nothing.

The media tracker ran for 145 revisions with a chain that could not: its
initial revision aborted its transaction on an empty database and rolled back
to zero tables, unnoticed because the test fixtures built their schema with
create_all and never ran Alembic. This test is what makes that impossible here,
and it is written before there is a single table to build.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.config import settings
from app.database import Base

ROOT = Path(__file__).resolve().parents[1]


def _admin_url(database: str) -> str:
    """settings.sqlalchemy_database_url with only the trailing db name swapped.

    The scratch-database test needs an administrative connection, but it may
    not assume the shared PostgreSQL's superuser password - that value is
    per-machine and not something a test should hardcode. Deriving it from
    the app's own settings means the test works wherever the app itself
    would.
    """
    base = settings.sqlalchemy_database_url
    return base.rsplit("/", 1)[0] + f"/{database}"


@pytest.fixture
def scratch_database():
    """A database created for this test and dropped afterwards."""
    admin = create_engine(_admin_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS food_migration_test"))
        conn.execute(text("CREATE DATABASE food_migration_test"))
    yield _admin_url("food_migration_test")
    # WITH (FORCE) because the test reads the scratch database back, and a
    # failed assertion leaves that connection open - a plain DROP would then
    # fail in teardown and bury the assertion that actually matters under an
    # unrelated error.
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS food_migration_test WITH (FORCE)"))


def test_upgrade_head_runs_against_an_empty_database(scratch_database):
    env = dict(os.environ)
    env["DATABASE_URL"] = scratch_database
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    # A return code on its own says nothing about WHERE the run landed: a run
    # that ignored DATABASE_URL and stamped the developer's real `food`
    # database would exit 0 and this test would stay green. Reading the scratch
    # database back is what pins it.
    #
    # The expected revision is spelled out rather than read from `alembic
    # heads`, which would compare the run against the same files it came from
    # and assert nothing. It is updated by hand with each new head.
    engine = create_engine(scratch_database)
    with engine.connect() as conn:
        stamped = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert stamped == "i1ngredients"

        # No longer vacuous: it bites from i1ngredients onwards, and a
        # revision that declares a model without creating its table fails
        # here rather than at the first request that touches it.
        tables = set(inspect(conn).get_table_names())
        assert tables >= set(Base.metadata.tables), set(Base.metadata.tables) - tables
    engine.dispose()


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
    assert "i1ngredients" in lines[0], result.stdout


def test_the_migrated_schema_matches_the_models(scratch_database):
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
    env = dict(os.environ)
    env["DATABASE_URL"] = scratch_database
    upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert upgrade.returncode == 0, upgrade.stderr

    engine = create_engine(scratch_database)
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        differences = compare_metadata(context, Base.metadata)
    engine.dispose()

    assert differences == [], differences


def test_the_fallback_category_is_seeded_by_the_migration(scratch_database):
    """`ingredient.category_id` is NOT NULL, so a fresh database with no
    category can hold no ingredient at all - including the stub that module 2
    creates mid-recipe, which is the one case that must never stop to ask a
    question. The migration seeds exactly one row for that, and the partial
    unique index is what keeps it exactly one."""
    env = dict(os.environ)
    env["DATABASE_URL"] = scratch_database
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    engine = create_engine(scratch_database)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name_cn FROM ingredient_category WHERE is_fallback")
        ).all()
    engine.dispose()

    assert len(rows) == 1, rows
