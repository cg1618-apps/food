"""Fixtures for anything that touches PostgreSQL.

The schema is built with `Base.metadata.create_all`, NOT by running Alembic.
That is deliberate and it has a known blind spot, which media paid for over 145
revisions: a migration chain that cannot build from nothing stays invisible to
a suite whose fixtures never run it. `tests/test_migrations_build_the_schema.py`
is what covers that, by running the real `alembic upgrade head` against a
scratch database. The two are complementary and neither is optional - anything
a migration creates but the models do not declare is invisible to both.

Isolation is an outer transaction rolled back at teardown, with the session
joined to it via savepoints so that code under test may call `commit()` without
destroying the fixture rows around it.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# `models` is imported for the side effect of registering every model on
# Base.metadata before create_all runs; without it the test schema is empty.
from app import models  # noqa: F401
from app.config import settings
from app.database import Base

TEST_DATABASE = "food_test"


def _url(database: str) -> str:
    """The app's own connection settings with the database name swapped.

    Derived rather than hardcoded: the password is per-machine and is not
    something a test may carry. A test that can reach the app's database can
    reach this one.
    """
    return settings.sqlalchemy_database_url.rsplit("/", 1)[0] + f"/{database}"


@pytest.fixture(scope="session")
def test_engine():
    admin = create_engine(_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DATABASE} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {TEST_DATABASE}"))
    admin.dispose()

    engine = create_engine(_url(TEST_DATABASE))
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

    admin = create_engine(_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DATABASE} WITH (FORCE)"))
    admin.dispose()


@pytest.fixture
def db(test_engine):
    """A session whose every write is rolled back when the test ends.

    `join_transaction_mode="create_savepoint"` is load-bearing: without it a
    `rollback()` inside the code under test unwinds this outer transaction as
    well, and the fixture rows vanish mid-test with nothing to say why.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = Session()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def fallback_category(db):
    """The one category every ingredient can be filed in.

    The migration seeds this row; `create_all` does not, because a migration's
    data statements are not part of the model metadata. Tests that need a
    category therefore have to make one, and this is it.
    """
    from app.models import IngredientCategory

    category = IngredientCategory(
        name_cn="未分類", name_en="Uncategorised", sort_order=9999, is_fallback=True
    )
    db.add(category)
    db.flush()
    return category
