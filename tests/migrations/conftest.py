"""Fixtures for the tests that run the real Alembic chain.

Every test here gets a `scratch` database of its own - empty, under a name no
other run or test can hold, dropped afterwards - and runs `alembic` against it
as a subprocess, which is what a human runs and what the deploy runs.

A test of one revision finds the revision before it with `previous_revision`,
never by writing the parent's id down. Reparenting a revision to fix two heads
changes its parent, and a test with the old id in it would then test the wrong
step without failing.
"""

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from alembic.config import Config
from alembic.script import ScriptDirectory
from tests import databases

ROOT = Path(__file__).resolve().parents[2]


def script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))


def previous_revision(revision: str) -> str:
    """The revision `revision` is built on, as Alembic's own graph says."""
    parent = script_directory().get_revision(revision).down_revision
    assert isinstance(parent, str), f"{revision} has no single parent: {parent!r}"
    return parent


def run_alembic(url: str, *args: str) -> subprocess.CompletedProcess:
    """`alembic <args>` against the database at `url`.

    `alembic/env.py` reads the URL from `app.config.settings`, which honours
    DATABASE_URL verbatim, so that is the one variable to set. UTF-8 both ways,
    because some refusals name rows in Chinese and a Windows console encoding
    would turn them into escapes.
    """
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": url, "PYTHONUTF8": "1"},
        capture_output=True,
        encoding="utf-8",
    )


@dataclass
class ScratchDatabase:
    """One empty database for one test, with Alembic pointed at it."""

    name: str
    url: str
    engine: Engine

    def run_alembic(self, *args: str) -> subprocess.CompletedProcess:
        """Run Alembic and hand back the result, for a test expecting a refusal."""
        return run_alembic(self.url, *args)

    def alembic(self, *args: str) -> None:
        """Run Alembic and require it to succeed."""
        result = self.run_alembic(*args)
        assert result.returncode == 0, f"alembic {' '.join(args)}:\n{result.stderr}"

    def begin(self):
        return self.engine.begin()

    def connect(self):
        return self.engine.connect()


@pytest.fixture
def scratch(test_database_server):
    with databases.scratch() as name:
        url = databases.server_url(name)
        engine = create_engine(url)
        try:
            yield ScratchDatabase(name=name, url=url, engine=engine)
        finally:
            engine.dispose()
