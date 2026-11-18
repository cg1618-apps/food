"""Test-wide fixtures.

`app.config.settings` is a module-level object built from the environment at
import time, so a test that monkeypatches the environment and reloads the
module leaves the reloaded object behind for every later test in the session.

The reload has to happen AFTER monkeypatch has undone its changes. Fixture
teardown is LIFO, and an autouse fixture is set up before the function-scoped
monkeypatch it shares a test with — so this fixture's teardown runs last, with
the real environment restored, which is exactly the window the reload needs.

Every database a test uses is created under a name of its own and dropped
afterwards - `tests/databases.py` says how, and `docs/testing.md`, "One
database per run", why.
"""

import importlib

import pytest


@pytest.fixture(autouse=True)
def restore_config_defaults():
    yield
    from app import config

    importlib.reload(config)


@pytest.fixture(scope="session")
def test_database_server():
    """The shared PostgreSQL, with what crashed runs left behind cleared.

    Once per run, and only by a test that needs the server: the unit tier
    never asks for it, so it still runs with no PostgreSQL at all. See
    `tests/databases.py` for which leftovers count.
    """
    from tests import databases

    databases.drop_leftovers()
