"""Which backend tests a pull request into `dev` runs in its own CI run.

    python scripts/pr_tests.py <base-sha> <head-sha>

Prints the pytest arguments, one per line, or the single word `FULL`.

A pull request into `dev` is tested twice: on its own, and again in the merge
queue on `dev` plus everything queued ahead of it - and only the second run
tests the tree that lands. So the full suite runs in the merge queue and on a
release into `main`, and the pull request's own run is the fast feedback:

- `tests/unit`, which needs no PostgreSQL;
- every test file the pull request adds or edits;
- when it touches the schema (`alembic/` or `app/models/`), the from-zero
  build, the release round trip, and every migration test naming a revision
  the pull request adds or edits.

A change to the test harness, the dependencies or the workflow changes what
every test means, so it runs everything. `media`'s `scripts/pr_tests.py` is
the shape this follows. See docs/testing.md, "What CI runs".
"""

import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALWAYS = ["tests/unit"]

# The guards every schema change needs: the chain builds from zero and matches
# the models, and the release comes back.
MIGRATION_GUARDS = [
    "tests/migrations/test_migrations_build_the_schema.py",
    "tests/migrations/test_migration_round_trip.py",
]

FULL_TRIGGERS = (
    "tests/conftest.py",
    "tests/databases.py",
    "tests/api/conftest.py",
    "tests/migrations/conftest.py",
    "requirements.txt",
    "requirements-dev.txt",
    ".github/workflows/ci.yml",
    "scripts/pr_tests.py",
)

SCHEMA_PREFIXES = ("alembic/", "app/models/")
VERSIONS_PREFIX = "alembic/versions/"
MIGRATION_TESTS_PREFIX = "tests/migrations/"

_REVISION = re.compile(r"^revision(?:\s*:\s*[^=]+)?\s*=\s*['\"]([^'\"]+)['\"]", re.M)


def select(
    changed: list[str], read: Callable[[str], str | None], test_files: list[str]
) -> list[str] | None:
    """The pytest arguments for these changed paths, or None for the full suite.

    `read(path)` returns a file's text at the head, or None if it is gone;
    `test_files` is every `tests/**/test_*.py` at the head. Both are parameters
    so the decision can be tested without git.
    """
    if any(path in FULL_TRIGGERS for path in changed):
        return None

    selected = list(ALWAYS)
    existing = set(test_files)

    def add(path: str) -> None:
        if path not in selected and not any(path.startswith(d + "/") for d in ALWAYS):
            selected.append(path)

    for path in changed:
        if path in existing:
            add(path)

    if any(path.startswith(SCHEMA_PREFIXES) for path in changed):
        for guard in MIGRATION_GUARDS:
            add(guard)
        revisions = set()
        for path in changed:
            if path.startswith(VERSIONS_PREFIX) and path.endswith(".py"):
                match = _REVISION.search(read(path) or "")
                if match:
                    revisions.add(match.group(1))
        for test_file in sorted(existing):
            if test_file.startswith(MIGRATION_TESTS_PREFIX):
                body = read(test_file) or ""
                if any(f'"{revision}"' in body for revision in revisions):
                    add(test_file)

    return selected


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def main(base: str, head: str) -> int:
    changed = _git("diff", "--name-only", "--diff-filter=d", f"{base}...{head}").split()

    def read(path: str) -> str | None:
        file = ROOT / path
        return file.read_text(encoding="utf-8") if file.is_file() else None

    test_files = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").rglob("test_*.py"))
    selection = select(changed, read, test_files)
    print("FULL" if selection is None else "\n".join(selection))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
