"""The run's database is its own, and a cleanup takes only what is abandoned.

A refusal test needs something there to refuse: each case below creates the
database it expects the cleanup to keep, beside the one it expects dropped,
so a cleanup that dropped nothing - or everything - fails.
"""

from sqlalchemy import create_engine, text

from tests import databases


def _exists(name: str) -> bool:
    admin = create_engine(databases.server_url("postgres"))
    try:
        with admin.connect() as conn:
            return bool(
                conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}
                ).scalar()
            )
    finally:
        admin.dispose()


def test_the_run_has_a_database_of_its_own(test_engine):
    name = test_engine.url.database
    assert databases.is_test_database(name), name
    assert name != "food_test"


def test_a_cleanup_drops_an_abandoned_database_and_keeps_the_rest(test_engine):
    old = databases.new_name(now=1_000_000_000)
    young = databases.new_name()
    connected = databases.new_name(now=1_000_000_000)
    for name in (old, young, connected):
        databases.create(name)
    holder = create_engine(databases.server_url(connected))
    try:
        with holder.connect():
            dropped = databases.drop_leftovers()

            assert old in dropped
            assert not _exists(old)
            # A young one may be a run that has not connected yet.
            assert _exists(young)
            # A connected one belongs to a run in progress, however old.
            assert _exists(connected)
            # Nor is this run's own database touched.
            assert _exists(test_engine.url.database)
    finally:
        holder.dispose()
        for name in (old, young, connected):
            databases.drop(name)
