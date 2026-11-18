"""Test databases: one per run, one per scratch use, none with a fixed name.

The platform's rule (`docs/registry.md`, "How an app's tests use the shared
server"): what makes two test runs collide is a shared database NAME, not the
shared server. So every database a test touches is created here under a name
nobody else can hold, and dropped when its user is done with it - the run's
own database (`tests/api/conftest.py`) and every scratch database a migration
test builds a chain in (`tests/conftest.py`'s `scratch_database`).

Names are `food_test_<epoch>_<hex>`, the shape `media` uses. The epoch is part
of the unique suffix and is what makes leftover cleanup safe: a database with
no connections is only dropped once it is older than LEFTOVER_AGE, so a run
that has just created a scratch database and not yet connected to it - the
gap between CREATE DATABASE and the Alembic subprocess opening it - cannot
lose it to a neighbour's cleanup.

This module imports nothing from `app` at module scope, so the unit tier can
import it on a machine with no PostgreSQL.
"""

import re
import time
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager

PREFIX = "food_test"
LEFTOVER_AGE = 2 * 60 * 60  # seconds
_NAME = re.compile(rf"^{PREFIX}_(\d+)_[0-9a-f]+$")


def new_name(now: float | None = None) -> str:
    """A database name no other run or test can be using."""
    epoch = int(time.time() if now is None else now)
    return f"{PREFIX}_{epoch}_{uuid.uuid4().hex}"


def is_test_database(name: str) -> bool:
    return _NAME.match(name) is not None


def stale(names: Iterable[str], now: float) -> list[str]:
    """The names, among unconnected databases, that a cleanup may drop.

    Only names this module mints, and only once older than LEFTOVER_AGE. A
    fixed name such as `food` or `food_test` is never in the answer, whatever
    its age, because it carries no epoch to be old by.
    """
    found = []
    for name in names:
        match = _NAME.match(name)
        if match and now - int(match.group(1)) > LEFTOVER_AGE:
            found.append(name)
    return found


def server_url(database: str) -> str:
    """The app's configured server, pointed at one named database.

    Derived from the app's own settings rather than hard-coded: the password
    is per-machine and not something a test may carry. `render_as_string`
    rather than `str()`, which masks the password as `***`.

    `localhost` becomes `127.0.0.1`. Windows resolves `localhost` to `::1`
    first, the dev database listens on 127.0.0.1 only, and every new
    connection waited about 21 seconds before falling back - which, with an
    Alembic subprocess per migration step, made one scratch-database test
    take minutes. `media` found and fixed the same thing.
    """
    from sqlalchemy.engine import make_url

    from app.config import settings

    url = make_url(settings.sqlalchemy_database_url)
    if url.host == "localhost":
        url = url.set(host="127.0.0.1")
    return url.set(database=database).render_as_string(hide_password=False)


def _admin():
    from sqlalchemy import create_engine

    return create_engine(server_url("postgres"), isolation_level="AUTOCOMMIT")


def create(name: str) -> None:
    from sqlalchemy import text

    assert is_test_database(name), f"not a test database name: {name!r}"
    admin = _admin()
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        admin.dispose()


def drop(name: str) -> None:
    """Drop one test database, ending any session still connected to it.

    WITH (FORCE) because a failed assertion can leave a test's own engine
    connected, and a plain DROP would then fail in teardown and bury the
    assertion that matters under an unrelated error.
    """
    from sqlalchemy import text

    assert is_test_database(name), f"refusing to drop a non-test database: {name!r}"
    admin = _admin()
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        admin.dispose()


def drop_leftovers(now: float | None = None) -> list[str]:
    """Drop the test databases a crashed or interrupted run left behind.

    A database with a connection belongs to a run in progress and is left
    alone, however old; so is a young one (see the module docstring). The
    plain DROP, not WITH (FORCE), is the second half of that rule: a run that
    connects between the query and the DROP makes the DROP fail, and the
    failure is swallowed rather than taking the database from under it.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    now = time.time() if now is None else now
    admin = _admin()
    dropped = []
    try:
        with admin.connect() as conn:
            unconnected = conn.execute(
                text(
                    "SELECT d.datname FROM pg_database d "
                    "WHERE d.datname LIKE :prefix AND NOT EXISTS ("
                    "  SELECT 1 FROM pg_stat_activity a WHERE a.datname = d.datname)"
                ),
                {"prefix": f"{PREFIX}\\_%"},
            ).scalars()
            for name in stale(list(unconnected), now):
                try:
                    conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
                except DBAPIError:
                    continue
                dropped.append(name)
    finally:
        admin.dispose()
    return dropped


@contextmanager
def scratch() -> Iterator[str]:
    """A fresh, empty database for one use, dropped afterwards whatever happens."""
    name = new_name()
    create(name)
    try:
        yield name
    finally:
        drop(name)
