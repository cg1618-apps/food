"""The names `tests/databases.py` mints, and which leftovers it may drop.

Pure: no PostgreSQL. `tests/api/test_run_database.py` asserts the same rules
against a real server.
"""

from tests import databases

NOW = 2_000_000_000


def test_a_name_is_new_every_time_and_says_it_is_a_test_database():
    first, second = databases.new_name(), databases.new_name()
    assert first != second
    assert databases.is_test_database(first)
    assert first.startswith("food_test_")


def test_a_fixed_name_is_not_a_test_database():
    """The names the suite used before - and the app's own database - are
    never ones the cleanup or the drop may touch."""
    for name in ("food", "food_test", "food_migration_test", "food_test_x", "postgres"):
        assert not databases.is_test_database(name), name


def test_only_an_old_minted_name_is_stale():
    old = databases.new_name(now=NOW - databases.LEFTOVER_AGE - 1)
    young = databases.new_name(now=NOW - 60)
    assert databases.stale([old, young, "food_test", "food"], now=NOW) == [old]


def test_a_localhost_server_is_reached_on_127_0_0_1(monkeypatch):
    """Windows tries ::1 first for `localhost`, and the dev database listens on
    127.0.0.1 only, so every connection paid a ~21 s timeout. The mirror: a
    host that is not `localhost` is left as it is."""
    from app.config import settings

    monkeypatch.setattr(settings, "database_url", "postgresql://u:p@localhost:5432/food")
    assert databases.server_url("x") == "postgresql://u:p@127.0.0.1:5432/x"
    monkeypatch.setattr(settings, "database_url", "postgresql://u:p@db.example:5432/food")
    assert databases.server_url("x") == "postgresql://u:p@db.example:5432/x"
