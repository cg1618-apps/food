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


def _preservation(conn):
    return conn.execute(
        text(
            "SELECT state, method, duration_min_days, duration_max_days "
            "FROM ingredient_preservation ORDER BY id"
        )
    ).all()


def test_the_storage_migration_copies_the_old_duration_and_downgrades_lossily(scratch):
    """Pre-existing rows are the fixture: on an empty table the copy and the
    delete in the downgrade touch nothing."""
    _alembic("upgrade", "v1ocabulary")
    with scratch.begin() as conn:
        category = conn.execute(
            text("SELECT id FROM ingredient_category WHERE name_cn = '肉類'")
        ).scalar()
        ingredient = conn.execute(
            text("INSERT INTO ingredient (name_cn, category_id) VALUES ('雞腿', :c) RETURNING id"),
            {"c": category},
        ).scalar()
        conn.execute(
            text(
                "INSERT INTO ingredient_preservation (ingredient_id, method, duration_days) "
                "VALUES (:i, '冷藏', 5)"
            ),
            {"i": ingredient},
        )

    _alembic("upgrade", "i2storage")
    with scratch.begin() as conn:
        assert _preservation(conn) == [("unused", "冷藏", 5, 5)]
        conn.execute(
            text(
                "INSERT INTO ingredient_preservation "
                "(ingredient_id, state, method, duration_min_days, duration_max_days) "
                "VALUES (:i, 'opened', '冷藏', 1, 2), (:i, 'unused', '冷凍', 30, NULL), "
                "(:i, 'unused', '常溫', 1, 2)"
            ),
            {"i": ingredient},
        )

    _alembic("downgrade", "v1ocabulary")
    with scratch.connect() as conn:
        rows = conn.execute(
            text("SELECT method, duration_days FROM ingredient_preservation ORDER BY id")
        ).all()
    # The opened row is gone (the old key cannot hold two states); the
    # minimum-only row keeps its minimum; a row with both ends keeps the
    # maximum (1..2 downgrades to 2, not 1).
    assert rows == [("冷藏", 5), ("冷凍", 30), ("常溫", 2)]


def test_the_status_and_platform_migration_maps_every_string_to_a_row_and_back(scratch):
    """Recipes and sources already holding each kind of value are the fixture:
    on empty tables the mapping and the downgrade's reverse mapping touch
    nothing, and a migration that dropped the columns unfilled would pass.

    The owner's own status and platform - created after the upgrade, so with
    no old key to return to - downgrade to the old defaults."""
    _alembic("upgrade", "i3import")
    with scratch.begin() as conn:
        recipes = {
            status: conn.execute(
                text("INSERT INTO recipe (name_cn, status) VALUES (:n, :s) RETURNING id"),
                {"n": f"菜-{status}", "s": status},
            ).scalar()
            for status in ("want_to_try", "can_cook", "regular")
        }
        for i, platform in enumerate(("youtube", "shorts", "website", "book", "other")):
            conn.execute(
                text(
                    "INSERT INTO recipe_source (recipe_id, platform, title, sort_order) "
                    "VALUES (:r, :p, :t, :i)"
                ),
                {"r": recipes["can_cook"], "p": platform, "t": f"來源-{platform}", "i": i},
            )

    _alembic("upgrade", "v2ocabulary")
    with scratch.begin() as conn:
        statuses = conn.execute(
            text("SELECT name_cn FROM recipe_status ORDER BY sort_order")
        ).scalars().all()
        platforms = conn.execute(
            text("SELECT name_cn FROM source_platform ORDER BY sort_order")
        ).scalars().all()
        filed = dict(
            conn.execute(
                text(
                    "SELECT r.name_cn, s.name_cn FROM recipe r "
                    "JOIN recipe_status s ON s.id = r.status_id"
                )
            ).all()
        )
        named = dict(
            conn.execute(
                text(
                    "SELECT rs.title, p.name_cn FROM recipe_source rs "
                    "JOIN source_platform p ON p.id = rs.platform_id"
                )
            ).all()
        )
        columns = {
            (table, column)
            for table, column in conn.execute(
                text(
                    "SELECT table_name, column_name FROM information_schema.columns "
                    "WHERE table_name IN ('recipe', 'recipe_source')"
                )
            ).all()
        }
        mine_status = conn.execute(
            text("INSERT INTO recipe_status (name_cn, sort_order) VALUES ('冷凍好', 40) RETURNING id")
        ).scalar()
        mine_platform = conn.execute(
            text("INSERT INTO source_platform (name_cn, sort_order) VALUES ('IG', 60) RETURNING id")
        ).scalar()
        conn.execute(
            text("UPDATE recipe SET status_id = :s WHERE id = :r"),
            {"s": mine_status, "r": recipes["regular"]},
        )
        conn.execute(
            text("UPDATE recipe_source SET platform_id = :p WHERE title = '來源-youtube'"),
            {"p": mine_platform},
        )

    assert statuses == ["想試", "可煮", "常煮"]
    assert platforms == ["YouTube", "Shorts", "網站", "書", "其他"]
    assert filed == {"菜-want_to_try": "想試", "菜-can_cook": "可煮", "菜-regular": "常煮"}
    assert named == {
        "來源-youtube": "YouTube",
        "來源-shorts": "Shorts",
        "來源-website": "網站",
        "來源-book": "書",
        "來源-other": "其他",
    }
    assert ("recipe", "status") not in columns and ("recipe", "status_id") in columns
    assert ("recipe_source", "platform") not in columns
    assert ("recipe_source", "platform_id") in columns

    _alembic("downgrade", "i3import")
    with scratch.connect() as conn:
        restored = dict(conn.execute(text("SELECT name_cn, status FROM recipe")).all())
        sources = dict(conn.execute(text("SELECT title, platform FROM recipe_source")).all())
        tables = conn.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_name IN ('recipe_status', 'source_platform')"
            )
        ).scalar()
    assert restored == {
        "菜-want_to_try": "want_to_try",
        "菜-can_cook": "can_cook",
        "菜-regular": "want_to_try",  # was on 冷凍好, which has no old key
    }
    assert sources == {
        "來源-youtube": "other",  # was on IG, which has no old key
        "來源-shorts": "shorts",
        "來源-website": "website",
        "來源-book": "book",
        "來源-other": "other",
    }
    assert tables == 0


def test_the_author_migration_makes_one_author_per_distinct_creator_and_back(scratch):
    """Sources already holding creators are the fixture: on an empty table the
    insert and the matching touch nothing, and a migration that dropped the
    column unfilled would pass. Two spellings of one name, a padded one and a
    source with no creator at all are what make the de-duplication, the trim
    and the null-skip each bite.

    The first spelling wins, by source id - the one saved first."""
    _alembic("upgrade", "v2ocabulary")
    with scratch.begin() as conn:
        status = conn.execute(text("SELECT id FROM recipe_status ORDER BY sort_order")).scalar()
        platform = conn.execute(
            text("SELECT id FROM source_platform ORDER BY sort_order")
        ).scalar()
        recipe = conn.execute(
            text("INSERT INTO recipe (name_cn, status_id) VALUES ('菜', :s) RETURNING id"),
            {"s": status},
        ).scalar()
        for i, (creator, title) in enumerate(
            [
                ("Babish", "一"),
                ("阿基師", "二"),
                ("babish", "三"),  # the same author, a later spelling
                ("  阿基師 ", "四"),  # the same author, padded
                ("Joshua Weissman", "五"),
                ("たかし", "六"),  # kana counts as the Chinese slot, as in the form
                (None, "七"),
            ]
        ):
            conn.execute(
                text(
                    "INSERT INTO recipe_source (recipe_id, platform_id, creator, title, sort_order) "
                    "VALUES (:r, :p, :c, :t, :i)"
                ),
                {"r": recipe, "p": platform, "c": creator, "t": title, "i": i},
            )

    _alembic("upgrade", "a1uthors")
    with scratch.begin() as conn:
        authors = sorted(
            conn.execute(text("SELECT name_cn, name_en, sort_order FROM author")).all(),
            key=lambda row: (row[0] or "", row[1] or ""),
        )
        named = dict(
            conn.execute(
                text(
                    "SELECT rs.title, coalesce(a.name_cn, a.name_en) FROM recipe_source rs "
                    "LEFT JOIN author a ON a.id = rs.author_id"
                )
            ).all()
        )
        columns = set(
            conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'recipe_source'"
                )
            ).scalars()
        )
        # The new CHECK lets a source stand on its author alone.
        babish = conn.execute(text("SELECT id FROM author WHERE name_en = 'Babish'")).scalar()
        conn.execute(
            text(
                "INSERT INTO recipe_source (recipe_id, platform_id, author_id, sort_order) "
                "VALUES (:r, :p, :a, 9)"
            ),
            {"r": recipe, "p": platform, "a": babish},
        )

    assert authors == [
        (None, "Babish", 0),
        (None, "Joshua Weissman", 0),
        ("たかし", None, 0),
        ("阿基師", None, 0),
    ]
    assert named == {
        "一": "Babish",
        "二": "阿基師",
        "三": "Babish",
        "四": "阿基師",
        "五": "Joshua Weissman",
        "六": "たかし",
        "七": None,
    }
    assert "creator" not in columns and "author_id" in columns

    _alembic("downgrade", "v2ocabulary")
    with scratch.connect() as conn:
        restored = dict(
            conn.execute(
                text("SELECT title, creator FROM recipe_source WHERE title IS NOT NULL")
            ).all()
        )
        only_author = conn.execute(
            text("SELECT creator FROM recipe_source WHERE title IS NULL")
        ).scalar()
        tables = conn.execute(
            text("SELECT count(*) FROM information_schema.tables WHERE table_name = 'author'")
        ).scalar()
    # Back from the author's display name: the later spelling and the padding
    # are not restored, which is the de-duplication doing what it was for.
    assert restored == {
        "一": "Babish",
        "二": "阿基師",
        "三": "Babish",
        "四": "阿基師",
        "五": "Joshua Weissman",
        "六": "たかし",
        "七": None,
    }
    assert only_author == "Babish"
    assert tables == 0
