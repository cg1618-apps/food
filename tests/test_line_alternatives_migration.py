"""`a2lternatives` adds `recipe_line_alternative`, and its downgrade removes
it and nothing else.

`test_migrations_build_the_schema.py` proves the upgrade builds the table the
models declare. What it cannot see is the downgrade, so this runs it with a
line and an alternative in the database: the line must survive, the table
must go, and the chain must build again afterwards.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from app.config import settings

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = "food_line_alternatives_migration_test"


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


def test_the_downgrade_drops_the_alternatives_and_keeps_the_lines(scratch):
    _alembic("upgrade", "a2lternatives")
    with scratch.begin() as conn:
        dish = conn.execute(text("INSERT INTO dish (name_cn) VALUES ('照燒雞') RETURNING id")).scalar()
        recipe = conn.execute(
            text(
                "INSERT INTO recipe (dish_id, status_id) "
                "VALUES (:dish, (SELECT min(id) FROM recipe_status)) RETURNING id"
            ),
            {"dish": dish},
        ).scalar()
        thigh, breast = (
            conn.execute(
                text(
                    "INSERT INTO ingredient (name_cn, category_id) "
                    "VALUES (:name, (SELECT id FROM ingredient_category WHERE is_fallback)) "
                    "RETURNING id"
                ),
                {"name": name},
            ).scalar()
            for name in ("雞腿測試", "雞胸肉測試")
        )
        line = conn.execute(
            text(
                "INSERT INTO recipe_line (recipe_id, position, ingredient_id) "
                "VALUES (:recipe, 0, :thigh) RETURNING id"
            ),
            {"recipe": recipe, "thigh": thigh},
        ).scalar()
        conn.execute(
            text(
                "INSERT INTO recipe_line_alternative (line_id, position, ingredient_id) "
                "VALUES (:line, 0, :breast)"
            ),
            {"line": line, "breast": breast},
        )

    _alembic("downgrade", "a2uthor")
    with scratch.connect() as conn:
        assert "recipe_line_alternative" not in inspect(conn).get_table_names()
        assert conn.execute(text("SELECT count(*) FROM recipe_line")).scalar() == 1

    _alembic("upgrade", "head")
    with scratch.connect() as conn:
        assert "recipe_line_alternative" in inspect(conn).get_table_names()
