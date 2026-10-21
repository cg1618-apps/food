"""`c3ommon` groups 常用食材, and its downgrade flattens them back into one
list.

`test_migrations_build_the_schema.py` proves the upgrade builds what the
models declare. What it cannot see is either direction with chips in the
database: the upgrade must leave every existing chip ungrouped in its old
order, and the downgrade must keep every chip, ungrouped first, then each
group's in group order - and the chain must build again afterwards.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from app.config import settings

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = "food_common_groups_migration_test"


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


def _ingredients(conn, *names):
    return [
        conn.execute(
            text(
                "INSERT INTO ingredient (name_cn, category_id) "
                "VALUES (:name, (SELECT id FROM ingredient_category WHERE is_fallback)) "
                "RETURNING id"
            ),
            {"name": name},
        ).scalar()
        for name in names
    ]


def _flat(conn):
    return [
        row.ingredient_id
        for row in conn.execute(
            text("SELECT ingredient_id FROM common_ingredient ORDER BY sort_order, ingredient_id")
        )
    ]


def test_the_upgrade_leaves_every_chip_ungrouped_in_its_order(scratch):
    _alembic("upgrade", "t3emplates")
    with scratch.begin() as conn:
        a, b, c = _ingredients(conn, "甲測試", "乙測試", "丙測試")
        for position, ingredient in enumerate((c, a, b)):
            conn.execute(
                text("INSERT INTO common_ingredient (ingredient_id, sort_order) VALUES (:i, :p)"),
                {"i": ingredient, "p": position},
            )

    _alembic("upgrade", "c3ommon")
    with scratch.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM common_ingredient WHERE group_id IS NOT NULL")).scalar() == 0
        assert _flat(conn) == [c, a, b]


def test_the_downgrade_flattens_the_groups_and_keeps_every_chip(scratch):
    _alembic("upgrade", "c3ommon")
    with scratch.begin() as conn:
        a, b, c, d, e = _ingredients(conn, "甲測試", "乙測試", "丙測試", "丁測試", "戊測試")
        # Groups inserted in the reverse of their order, so id order is not
        # what the flattening follows.
        second = conn.execute(
            text("INSERT INTO common_ingredient_group (name, sort_order) VALUES ('乙組', 1) RETURNING id")
        ).scalar()
        first = conn.execute(
            text("INSERT INTO common_ingredient_group (name, sort_order) VALUES ('甲組', 0) RETURNING id")
        ).scalar()
        for ingredient, group, position in (
            (a, second, 0),
            (b, first, 1),
            (c, first, 0),
            (d, None, 0),
            (e, None, 1),
        ):
            conn.execute(
                text(
                    "INSERT INTO common_ingredient (ingredient_id, group_id, sort_order) "
                    "VALUES (:i, :g, :p)"
                ),
                {"i": ingredient, "g": group, "p": position},
            )

    _alembic("downgrade", "t3emplates")
    with scratch.connect() as conn:
        assert "common_ingredient_group" not in inspect(conn).get_table_names()
        assert _flat(conn) == [d, e, c, b, a]
        positions = [r[0] for r in conn.execute(text("SELECT sort_order FROM common_ingredient ORDER BY 1"))]
        assert positions == [0, 1, 2, 3, 4]

    _alembic("upgrade", "head")
    with scratch.connect() as conn:
        assert "common_ingredient_group" in inspect(conn).get_table_names()
