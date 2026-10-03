"""`s4chedule` turns the schedule's four marks into booleans and moves each
meal's dish and recipe into a meal item, and its downgrade puts them back.

The rows written at `s3chedule` are the fixture that makes this bite: on an
empty schedule every ALTER and every INSERT ... SELECT succeeds whatever it
does to the data. A non-blank mark, a NULL one and a meal with nothing but
text are each there so the opposite outcome would show.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.config import settings

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = "food_schedule_migration_test"


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


def _seed_at_s3chedule(conn) -> dict:
    dish = conn.execute(text("INSERT INTO dish (name_cn) VALUES ('咖哩') RETURNING id")).scalar()
    recipe = conn.execute(
        text(
            "INSERT INTO recipe (dish_id, status_id) "
            "VALUES (:dish, (SELECT min(id) FROM recipe_status)) RETURNING id"
        ),
        {"dish": dish},
    ).scalar()
    conn.execute(
        text(
            "INSERT INTO schedule_day (date, to_buy, thaw_morning, thaw_noon, thaw_evening, fruit) "
            "VALUES ('2026-10-05', '雞腿', NULL, '   ', 'V', '芭樂'), "
            "('2026-10-06', NULL, NULL, NULL, NULL, NULL)"
        )
    )
    conn.execute(
        text(
            "INSERT INTO schedule_meal (date, slot, text, dish_id, recipe_id) VALUES "
            "('2026-10-05', 'dinner', '配白飯', :dish, :recipe), "
            "('2026-10-05', 'lunch', '麵', NULL, NULL), "
            "('2026-10-06', 'breakfast', NULL, :dish, NULL)"
        ),
        {"dish": dish, "recipe": recipe},
    )
    return {"dish": dish, "recipe": recipe}


def test_upgrade_turns_marks_into_booleans_and_meals_into_items(scratch):
    _alembic("upgrade", "s3chedule")
    with scratch.begin() as conn:
        ids = _seed_at_s3chedule(conn)
    _alembic("upgrade", "s4chedule")

    with scratch.connect() as conn:
        days = conn.execute(
            text(
                "SELECT date::text, to_buy, thaw_morning, thaw_noon, thaw_evening, fruit "
                "FROM schedule_day ORDER BY date"
            )
        ).all()
        assert [tuple(row) for row in days] == [
            ("2026-10-05", True, False, False, True, "芭樂"),
            ("2026-10-06", False, False, False, False, None),
        ]
        items = conn.execute(
            text(
                "SELECT m.date::text, m.slot, m.text, i.position, i.dish_id, i.recipe_id "
                "FROM schedule_meal m LEFT JOIN schedule_meal_item i ON i.meal_id = m.id "
                "ORDER BY m.date, m.slot"
            )
        ).all()
        assert [tuple(row) for row in items] == [
            ("2026-10-05", "dinner", "配白飯", 0, ids["dish"], ids["recipe"]),
            ("2026-10-05", "lunch", "麵", None, None, None),
            ("2026-10-06", "breakfast", None, 0, ids["dish"], None),
        ]
        # The new day takes the default: an INSERT naming no mark is all false.
        conn.execute(text("INSERT INTO schedule_day (date, fruit) VALUES ('2026-10-07', '梨')"))
        assert conn.execute(
            text("SELECT to_buy OR thaw_morning FROM schedule_day WHERE date = '2026-10-07'")
        ).scalar() is False
        conn.rollback()


def test_downgrade_writes_true_as_a_tick_and_keeps_the_first_item(scratch):
    _alembic("upgrade", "s4chedule")
    with scratch.begin() as conn:
        dish = conn.execute(text("INSERT INTO dish (name_cn) VALUES ('咖哩') RETURNING id")).scalar()
        other = conn.execute(text("INSERT INTO dish (name_cn) VALUES ('拉麵') RETURNING id")).scalar()
        conn.execute(
            text(
                "INSERT INTO schedule_day (date, to_buy, thaw_evening) "
                "VALUES ('2026-10-05', true, false)"
            )
        )
        meal = conn.execute(
            text(
                "INSERT INTO schedule_meal (date, slot, text) "
                "VALUES ('2026-10-05', 'dinner', '配白飯') RETURNING id"
            )
        ).scalar()
        # Inserted out of order, so "first" has to mean the position.
        conn.execute(
            text(
                "INSERT INTO schedule_meal_item (meal_id, position, dish_id) "
                "VALUES (:meal, 1, :other), (:meal, 0, :dish)"
            ),
            {"meal": meal, "dish": dish, "other": other},
        )
    _alembic("downgrade", "s3chedule")

    with scratch.connect() as conn:
        day = conn.execute(
            text("SELECT to_buy, thaw_morning, thaw_evening FROM schedule_day")
        ).one()
        assert tuple(day) == ("✓", None, None)
        row = conn.execute(text("SELECT text, dish_id, recipe_id FROM schedule_meal")).one()
        assert tuple(row) == ("配白飯", dish, None)
        assert (
            conn.execute(text("SELECT to_regclass('schedule_meal_item')")).scalar() is None
        )
