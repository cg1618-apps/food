"""The vocabulary migration seeds rows, and seeding must survive a database
where the owner already typed one of them by hand. The pre-existing row is the
fixture that makes this bite: on an empty database every INSERT succeeds and
the ON CONFLICT clause is never consulted."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.config import settings

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = "food_seed_test"


def _url(database: str) -> str:
    return settings.sqlalchemy_database_url.rsplit("/", 1)[0] + f"/{database}"


def _alembic(*args: str) -> None:
    env = dict(os.environ, DATABASE_URL=_url(SCRATCH))
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def scratch():
    admin = create_engine(_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {SCRATCH}"))
    engine = create_engine(_url(SCRATCH))
    yield engine
    engine.dispose()
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH} WITH (FORCE)"))
    admin.dispose()


def test_the_seeds_land_on_an_empty_database(scratch):
    _alembic("upgrade", "v1ocabulary")
    with scratch.connect() as conn:
        courses = conn.execute(text("SELECT name_cn FROM recipe_course")).scalars().all()
        methods = conn.execute(text("SELECT count(*) FROM cooking_method")).scalar()
        categories = conn.execute(
            text("SELECT name_cn FROM ingredient_category WHERE NOT is_fallback")
        ).scalars().all()
        labels = conn.execute(text("SELECT name_cn FROM label")).scalars().all()
    assert "主食" in courses and len(courses) == 7
    assert methods == 12
    assert "肉類" in categories
    assert "飯" in labels


def test_seeding_skips_a_value_the_owner_already_created(scratch):
    _alembic("upgrade", "i1ngredients")
    with scratch.begin() as conn:
        conn.execute(text("INSERT INTO label (name_cn) VALUES ('飯')"))
        conn.execute(
            text("INSERT INTO ingredient_category (name_cn, sort_order) VALUES ('肉類', 3)")
        )
    _alembic("upgrade", "v1ocabulary")
    with scratch.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM label WHERE name_cn = '飯'")).scalar() == 1
        assert (
            conn.execute(
                text("SELECT sort_order FROM ingredient_category WHERE name_cn = '肉類'")
            ).scalar()
            == 3
        )


def test_downgrade_keeps_a_seeded_category_that_is_in_use(scratch):
    _alembic("upgrade", "v1ocabulary")
    with scratch.begin() as conn:
        meat = conn.execute(
            text("SELECT id FROM ingredient_category WHERE name_cn = '肉類'")
        ).scalar()
        conn.execute(
            text("INSERT INTO ingredient (name_cn, category_id) VALUES ('雞腿', :c)"), {"c": meat}
        )
    _alembic("downgrade", "i1ngredients")
    with scratch.connect() as conn:
        names = conn.execute(text("SELECT name_cn FROM ingredient_category")).scalars().all()
    assert "肉類" in names
    assert "海鮮" not in names
