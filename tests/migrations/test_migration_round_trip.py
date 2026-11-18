"""The release must come back: down to what `main` holds, and up again.

`test_migrations_build_the_schema.py` proves the chain builds FORWARD from an
empty database. This proves the RELEASE reverses: it downgrades to the
revision `origin/main` is at - what a rollback of the release does, and what
`deploy/migrations downgrade` is asked for - then upgrades to head and asserts
the schema is the one it started from.

One step back is not enough. Concurrent sessions put several revisions into one
release, and a downgrade of only the head would leave every earlier one in it
unexercised until the day a rollback needs it. When the branch holds no
revision beyond `main`, there is no release range and it falls back to one
step, so every branch still runs some `downgrade()`.

`origin/main` is read from git: the revision files `main` holds, by name. A
clone without it - a shallow checkout, or one that has never fetched `main` -
falls back to one step with a warning rather than failing, because the round
trip still says something there. CI checks out the whole history
(`fetch-depth: 0`), which carries `origin/main`, so CI always tests the range.
"""

import subprocess
import warnings
from pathlib import Path

import pytest
from sqlalchemy import text

from tests.migrations.conftest import ROOT, script_directory

# Every object the schema is made of, one row each, spelled so that two equal
# schemas give equal sets. Data is deliberately absent: a downgrade that
# deletes seeded rows and an upgrade that seeds them again is a round trip.
SCHEMA_SQL = """
SELECT 'column ' || table_name || '.' || column_name || ' ' || data_type
       || ' null=' || is_nullable || ' default=' || coalesce(column_default, '')
  FROM information_schema.columns WHERE table_schema = 'public'
UNION ALL
SELECT 'constraint ' || conrelid::regclass::text || ' ' || conname || ' '
       || pg_get_constraintdef(oid)
  FROM pg_constraint WHERE connamespace = 'public'::regnamespace
UNION ALL
SELECT 'index ' || indexdef FROM pg_indexes WHERE schemaname = 'public'
UNION ALL
SELECT 'type ' || t.typname || ' ' || string_agg(e.enumlabel, ',' ORDER BY e.enumsortorder)
  FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid
 WHERE t.typnamespace = 'public'::regnamespace GROUP BY t.typname
"""


def release_base(head: str, parent: dict[str, str | None], on_main: set[str]) -> str | None:
    """The revision a rollback of this release would downgrade to.

    Walks down from `head` through every revision `main` does not hold and
    stops at the first one it does - main's head, the release's base. When
    `head` is itself on main the release adds nothing, and the answer is the
    one step below it. None when there is nothing below to go to.
    """
    if head in on_main:
        return parent[head]
    revision = head
    while revision not in on_main:
        below = parent[revision]
        if below is None:
            return parent[head]  # nothing on main to return to: one step
        revision = below
    return revision


def _revision_files_on_main() -> set[str] | None:
    """Basenames of the revision files on `origin/main`, or None without it."""
    result = subprocess.run(
        ["git", "ls-tree", "--name-only", "origin/main", "alembic/versions/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return {Path(line).name for line in result.stdout.splitlines()}


def _release_range() -> tuple[str, str | None]:
    """(head, the revision to downgrade to) for this checkout."""
    script = script_directory()
    (head,) = script.get_heads()
    parent, files = {}, {}
    for rev in script.walk_revisions():
        assert not isinstance(rev.down_revision, tuple), f"merge revision {rev.revision}"
        parent[rev.revision] = rev.down_revision
        files[rev.revision] = Path(rev.path).name

    on_main_files = _revision_files_on_main()
    if on_main_files is None:
        warnings.warn(
            "origin/main is not available (run `git fetch origin main`); "
            "the round trip falls back to one step",
            stacklevel=2,
        )
        return head, parent[head]
    on_main = {rev for rev, name in files.items() if name in on_main_files}
    return head, release_base(head, parent, on_main)


def _schema(scratch) -> set[str]:
    with scratch.connect() as conn:
        return set(conn.execute(text(SCHEMA_SQL)).scalars())


def test_the_release_survives_a_downgrade_and_a_second_upgrade(scratch):
    head, target = _release_range()
    assert target is not None, f"{head} has nothing below it to downgrade to"

    scratch.alembic("upgrade", "head")
    before = _schema(scratch)
    # Not vacuous: an empty set on both sides would compare equal.
    assert len(before) > 100, "the migrated schema is empty; this check is vacuous"

    down = scratch.run_alembic("downgrade", target)
    assert down.returncode == 0, (
        f"downgrading from {head} to {target} failed - fix that revision's "
        f"downgrade():\n{down.stderr[-3000:]}"
    )
    with scratch.connect() as conn:
        landed = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert landed == target

    scratch.alembic("upgrade", "head")

    # Exit codes alone would pass a pair that runs cleanly and lands somewhere
    # else - an index never recreated, a constraint left behind. A rollback
    # leaves the box in exactly that state and serves traffic from it.
    after = _schema(scratch)
    assert after == before, (
        "the round trip did not restore the schema.\n"
        f"lost: {sorted(before - after)}\n"
        f"gained: {sorted(after - before)}"
    )


# A chain a <- b <- c <- d. Pure: no database, no git.
CHAIN = {"a": None, "b": "a", "c": "b", "d": "c"}


@pytest.mark.parametrize(
    ("head", "on_main", "expected"),
    [
        # The release adds c and d: both downgrades run, back to main's head.
        ("d", {"a", "b"}, "b"),
        # The release adds d alone: one step, which is also main's head.
        ("d", {"a", "b", "c"}, "c"),
        # Nothing beyond main: one step.
        ("b", {"a", "b"}, "a"),
        # Main holds none of it (a new app): one step rather than to base.
        ("d", set(), "c"),
    ],
)
def test_the_release_base_is_what_a_rollback_would_undo(head, on_main, expected):
    assert release_base(head, CHAIN, on_main) == expected
