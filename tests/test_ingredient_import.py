"""The one-time ingredient import, `i3import`.

Two halves. The validation runs on the committed CSV and on tiny bad files,
with no database: a malformed file must stop the migration before it writes
anything. The load runs against a scratch database, and the fixture that makes
its idempotency bite is a PRE-EXISTING ingredient whose name matches a CSV row
- on an empty database every row inserts and the skip rule is never consulted.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.config import settings

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = "food_import_test"
MIGRATION = ROOT / "alembic" / "versions" / "i3import_ingredient_names.py"
HEADER = "name_cn,name_en,aliases,parent,category\n"


def _load_migration():
    spec = importlib.util.spec_from_file_location("i3import_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration = _load_migration()


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


def _csv(tmp_path, body: str) -> Path:
    path = tmp_path / "ingredients.csv"
    path.write_text(HEADER + body, encoding="utf-8")
    return path


# --- validation -------------------------------------------------------------


def test_the_committed_csv_passes_validation():
    rows = migration.read_rows(migration.CSV_PATH)
    migration.validate(rows)
    assert len(rows) == 194


def test_a_good_tiny_file_passes(tmp_path):
    """The mirror of every refusal below: same shape, nothing wrong."""
    rows = migration.read_rows(
        _csv(tmp_path, "醬油,soy sauce,生抽,,調味料\n醬油膏,thick soy sauce,,醬油,\n")
    )
    migration.validate(rows)
    assert [r.aliases for r in rows] == [["生抽"], []]


@pytest.mark.parametrize(
    ("body", "complaint"),
    [
        ("醬油膏,thick soy sauce,,醬油,調味料\n", "parent"),
        ("醬油,soy sauce,,,醬料類\n", "category"),
        ("醬油,soy sauce,,,調味料\n醬油,dark soy sauce,,,調味料\n", "name_cn"),
        ("醬油,soy sauce,,,調味料\n老抽,Soy Sauce,,,調味料\n", "name_en"),
        ("醬油,soy sauce,老抽,,調味料\n老抽,dark soy sauce,,,調味料\n", "alias"),
        ("醬油,soy sauce,生抽|生抽,,調味料\n", "alias"),
        (",,,,調味料\n", "name"),
    ],
)
def test_a_malformed_file_is_refused(tmp_path, body, complaint):
    rows = migration.read_rows(_csv(tmp_path, body))
    with pytest.raises(ValueError, match=complaint):
        migration.validate(rows)


def test_a_wrong_header_is_refused(tmp_path):
    path = tmp_path / "ingredients.csv"
    path.write_text("name,english\n醬油,soy sauce\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        migration.read_rows(path)


# --- the load ---------------------------------------------------------------


def _ingredient(conn, name_cn):
    return conn.execute(
        text(
            "SELECT i.id, i.name_en, i.needs_detail, i.parent_id, c.name_cn AS category "
            "FROM ingredient i JOIN ingredient_category c ON c.id = i.category_id "
            "WHERE i.name_cn = :n"
        ),
        {"n": name_cn},
    ).one()


def test_upgrade_loads_every_row_with_aliases_and_parents(scratch):
    _alembic("upgrade", "i3import")
    with scratch.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM ingredient")).scalar()
        stubs = conn.execute(
            text("SELECT count(*) FROM ingredient WHERE needs_detail")
        ).scalar()
        thigh = _ingredient(conn, "去骨雞腿")
        leg = _ingredient(conn, "雞腿")
        aliases = conn.execute(
            text("SELECT value FROM ingredient_alias WHERE ingredient_id = :i ORDER BY value"),
            {"i": thigh.id},
        ).scalars().all()
        old_bay = conn.execute(
            text("SELECT name_cn FROM ingredient WHERE name_en = 'Old Bay Seasoning'")
        ).one()
    assert count == stubs == 194
    assert thigh.parent_id == leg.id
    assert thigh.category == "肉類"
    assert aliases == ["雞腿排", "雞腿肉"]
    assert old_bay.name_cn is None


def test_an_empty_category_files_in_the_fallback(scratch):
    _alembic("upgrade", "i3import")
    with scratch.connect() as conn:
        water = _ingredient(conn, "水")
        kelp = _ingredient(conn, "海帶")
    assert water.category == "未分類"
    assert kelp.category == "乾貨"


def test_a_row_the_owner_already_typed_is_skipped_and_left_alone(scratch):
    """The load-bearing fixture: 醬油 typed by hand, with notes and a category
    of the owner's own, and 蒜 as an alias of an ingredient named otherwise.
    Without them, the skip rule has nothing to skip."""
    _alembic("upgrade", "k1notes")
    with scratch.begin() as conn:
        fallback = conn.execute(
            text("SELECT id FROM ingredient_category WHERE is_fallback")
        ).scalar()
        soy = conn.execute(
            text(
                "INSERT INTO ingredient (name_cn, name_en, category_id, description) "
                "VALUES ('醬油', 'Soy', :c, 'mine') RETURNING id"
            ),
            {"c": fallback},
        ).scalar()
        garlic = conn.execute(
            text(
                "INSERT INTO ingredient (name_cn, category_id) "
                "VALUES ('大蒜', :c) RETURNING id"
            ),
            {"c": fallback},
        ).scalar()
        conn.execute(
            text("INSERT INTO ingredient_alias (ingredient_id, value) VALUES (:i, 'GARLIC')"),
            {"i": garlic},
        )

    _alembic("upgrade", "i3import")
    with scratch.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM ingredient")).scalar()
        mine = conn.execute(
            text(
                "SELECT name_en, description, needs_detail, category_id, parent_id "
                "FROM ingredient WHERE id = :i"
            ),
            {"i": soy},
        ).one()
        soy_aliases = conn.execute(
            text("SELECT count(*) FROM ingredient_alias WHERE ingredient_id = :i"), {"i": soy}
        ).scalar()
        thick = _ingredient(conn, "醬油膏")
        garlic_rows = conn.execute(
            text("SELECT count(*) FROM ingredient WHERE name_cn = '蒜頭'")
        ).scalar()
    # 194 rows, two of them (醬油, 蒜頭) skipped, plus the two typed by hand.
    assert count == 194
    assert tuple(mine) == ("Soy", "mine", False, fallback, None)
    assert soy_aliases == 0
    # The skipped row's existing twin is still the parent of its children.
    assert thick.parent_id == soy
    assert garlic_rows == 0


def test_running_the_load_twice_inserts_nothing_and_downgrade_keeps_the_rows(scratch):
    _alembic("upgrade", "i3import")
    _alembic("downgrade", "k1notes")
    with scratch.connect() as conn:
        after_downgrade = conn.execute(text("SELECT count(*) FROM ingredient")).scalar()
    assert after_downgrade == 194

    _alembic("upgrade", "i3import")
    with scratch.connect() as conn:
        ingredients = conn.execute(text("SELECT count(*) FROM ingredient")).scalar()
        aliases = conn.execute(text("SELECT count(*) FROM ingredient_alias")).scalar()
    assert ingredients == 194
    expected_aliases = sum(len(r.aliases) for r in migration.read_rows(migration.CSV_PATH))
    assert aliases == expected_aliases


def test_a_parent_link_that_would_make_a_cycle_or_point_at_itself_is_skipped(scratch, tmp_path):
    """Validation does not refuse a loop in the file; the load declines the
    link that would close it. Rows link in file order: 甲 -> 乙 is made first,
    so 乙 -> 甲 is the one refused; 丙 names itself. 丁 -> 甲 is the mirror:
    an ordinary link from the same file, which must still be made."""
    _alembic("upgrade", "k1notes")
    rows = migration.read_rows(
        _csv(tmp_path, "甲,,,乙,\n乙,,,甲,\n丙,,,丙,\n丁,,,甲,\n")
    )
    migration.validate(rows)
    with scratch.begin() as conn:
        assert migration.load(conn, rows) == 4
    with scratch.connect() as conn:
        parents = dict(
            conn.execute(
                text(
                    "SELECT c.name_cn, p.name_cn FROM ingredient c "
                    "LEFT JOIN ingredient p ON p.id = c.parent_id"
                )
            ).all()
        )
    assert parents["甲"] == "乙"
    assert parents["乙"] is None
    assert parents["丙"] is None
    assert parents["丁"] == "甲"
