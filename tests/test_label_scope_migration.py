"""`l1abels` gives every label the one library that uses it, deletes the
labels nothing uses, and refuses a label two libraries share; its downgrade
drops the scope and restores the global name uniqueness.

The labels written at `h1eating` are the fixture that makes this bite: on an
empty `label` table the backfill, the deletion and the refusal all succeed by
doing nothing. A label used by ingredients only, one used by dishes only, one
used by notes only and one used by nothing are each there so the opposite
outcome would show; the shared label is its own case, because it stops the
upgrade and the others could then prove nothing.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.config import settings

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = "food_label_scope_migration_test"


def _url(database: str) -> str:
    return settings.sqlalchemy_database_url.rsplit("/", 1)[0] + f"/{database}"


def _alembic(*args: str) -> subprocess.CompletedProcess:
    # UTF-8 both ways, because the refusals name labels in Chinese and a
    # Windows console encoding would turn them into escapes.
    env = dict(os.environ, DATABASE_URL=_url(SCRATCH), PYTHONUTF8="1")
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        encoding="utf-8",
    )


def _ok(*args: str) -> None:
    result = _alembic(*args)
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


def _insert(conn, sql: str, **params) -> int:
    return conn.execute(text(sql + " RETURNING id"), params).scalar()


def _owners(conn) -> dict:
    category = conn.execute(text("SELECT id FROM ingredient_category WHERE is_fallback")).scalar()
    # A name apart from the i3import list, which these revisions have loaded.
    return {
        "ingredient": _insert(
            conn, "INSERT INTO ingredient (name_cn, category_id) VALUES ('遷移測試食材', :c)", c=category
        ),
        "dish": _insert(conn, "INSERT INTO dish (name_cn) VALUES ('麻婆豆腐')"),
        "note": _insert(conn, "INSERT INTO kitchen_note (title) VALUES ('辣油')"),
    }


def _link(conn, owners: dict, owner: str, label: int) -> None:
    table, column = {
        "ingredient": ("ingredient_label", "ingredient_id"),
        "dish": ("dish_label", "dish_id"),
        "note": ("kitchen_note_label", "kitchen_note_id"),
    }[owner]
    conn.execute(
        text(f"INSERT INTO {table} ({column}, label_id) VALUES (:o, :l)"),
        {"o": owners[owner], "l": label},
    )


def _label(conn, name: str) -> int:
    return _insert(conn, "INSERT INTO label (name_cn) VALUES (:n)", n=name)


def test_upgrade_scopes_used_labels_and_deletes_unused_ones(scratch):
    _ok("upgrade", "h1eating")
    with scratch.begin() as conn:
        # The seeded 飯 麵 肉 ... are unused, so they are part of the fixture
        # too: the upgrade must delete them.
        seeded = conn.execute(text("SELECT count(*) FROM label")).scalar()
        assert seeded == 8
        owners = _owners(conn)
        hot = _label(conn, "辣")
        side = _label(conn, "下飯")
        video = _label(conn, "影片")
        unused = _label(conn, "閒置")
        _link(conn, owners, "ingredient", hot)
        _link(conn, owners, "dish", side)
        _link(conn, owners, "note", video)
    _ok("upgrade", "l1abels")

    with scratch.connect() as conn:
        rows = dict(conn.execute(text("SELECT id, scope FROM label")).all())
        assert rows == {hot: "ingredient", side: "dish", video: "note"}
        assert unused not in rows

        # Uniqueness is per scope now: 辣 may be a dish label too, and may
        # not be a second ingredient label.
        conn.execute(text("INSERT INTO label (name_cn, scope) VALUES ('辣', 'dish')"))
        with pytest.raises(IntegrityError) as excinfo:
            conn.execute(text("INSERT INTO label (name_cn, scope) VALUES ('辣', 'ingredient')"))
        assert "uq_label_name_cn" in str(excinfo.value)
        conn.rollback()


def test_upgrade_refuses_a_label_two_libraries_use(scratch):
    _ok("upgrade", "h1eating")
    with scratch.begin() as conn:
        owners = _owners(conn)
        shared = _label(conn, "常備")
        _link(conn, owners, "ingredient", shared)
        _link(conn, owners, "note", shared)

    result = _alembic("upgrade", "l1abels")
    assert result.returncode != 0
    assert "常備" in result.stderr

    # Nothing was changed: the revision is still h1eating and the label and
    # both links survive for the owner to sort out.
    with scratch.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "h1eating"
        assert conn.execute(text("SELECT count(*) FROM label WHERE id = :l"), {"l": shared}).scalar()
        links = conn.execute(
            text(
                "SELECT (SELECT count(*) FROM ingredient_label WHERE label_id = :l)"
                " + (SELECT count(*) FROM kitchen_note_label WHERE label_id = :l)"
            ),
            {"l": shared},
        ).scalar()
        assert links == 2


def test_downgrade_drops_the_scope_and_restores_global_uniqueness(scratch):
    _ok("upgrade", "l1abels")
    with scratch.begin() as conn:
        conn.execute(text("INSERT INTO label (name_cn, scope) VALUES ('辣', 'ingredient')"))
    _ok("downgrade", "h1eating")

    with scratch.connect() as conn:
        assert conn.execute(text("SELECT name_cn FROM label")).scalars().all() == ["辣"]
        columns = conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'label'")
        ).scalars().all()
        assert "scope" not in columns
        with pytest.raises(IntegrityError) as excinfo:
            conn.execute(text("INSERT INTO label (name_cn) VALUES ('辣')"))
        assert "uq_label_name_cn" in str(excinfo.value)
        conn.rollback()


def test_downgrade_refuses_two_labels_sharing_a_name(scratch):
    """Two scopes may share 辣; the global index the downgrade restores
    cannot hold both, so the downgrade stops naming it rather than picking
    one to delete."""
    _ok("upgrade", "l1abels")
    with scratch.begin() as conn:
        conn.execute(
            text("INSERT INTO label (name_cn, scope) VALUES ('辣', 'ingredient'), ('辣', 'dish')")
        )
    result = _alembic("downgrade", "h1eating")
    assert result.returncode != 0
    assert "辣" in result.stderr
