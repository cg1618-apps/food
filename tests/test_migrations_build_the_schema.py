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

    # A return code on its own says nothing about WHERE the run landed. With
    # 0001_baseline empty, a run that ignored DATABASE_URL and stamped the
    # developer's real `food` database would exit 0 and this test would stay
    # green. Reading the scratch database back is what pins it.
    engine = create_engine(scratch_database)
    with engine.connect() as conn:
        stamped = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert stamped == "0001_baseline"

        # Vacuous while there are no models, and deliberately so: it starts
        # biting the moment the first table is declared, which is when a
        # revision that forgets a table would otherwise ship.
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
    assert "0001_baseline" in lines[0], result.stdout
