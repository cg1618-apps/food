"""Configuration, and the one rule about it that has bitten this project."""

import importlib


def test_database_url_is_honoured_verbatim_when_set(monkeypatch):
    # A stale DATABASE_URL in a machine's .env wins over the POSTGRES_* parts
    # and breaks that machine. It is honoured deliberately - the surprise is
    # only a surprise to someone who does not know - so it is pinned here.
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@example:5432/db")
    from app import config

    importlib.reload(config)
    assert config.settings.sqlalchemy_database_url == "postgresql://u:p@example:5432/db"


def test_the_url_is_built_from_the_parts_when_it_is_not(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "food")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "food")
    monkeypatch.setenv("POSTGRES_HOST", "db")
    from app import config

    importlib.reload(config)
    assert config.settings.sqlalchemy_database_url == (
        "postgresql://food:secret@db:5432/food"
    )


def test_defaults_are_intact_for_a_test_that_patches_nothing():
    # Ordered after the two patching tests in this file. Under the leak this
    # sees postgres_host == "db" from the previous test and fails, which is
    # the whole point of asserting it here rather than trusting the fixture.
    from app import config

    assert config.settings.postgres_host == "localhost"
