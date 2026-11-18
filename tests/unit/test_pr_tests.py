"""What a pull request into `dev` runs in its own CI run (scripts/pr_tests.py).

Pure: the changed paths and the files' text are handed in, so no git and no
PostgreSQL. The merge queue runs the full suite; these pin what the pull
request's own, faster run may leave to it.
"""

from scripts.pr_tests import ALWAYS, MIGRATION_GUARDS, select

TESTS = [
    "tests/unit/test_config.py",
    "tests/api/test_heating.py",
    "tests/api/test_schedule.py",
    "tests/migrations/test_migrations_build_the_schema.py",
    "tests/migrations/test_migration_round_trip.py",
    "tests/migrations/test_schedule_migration.py",
    "tests/migrations/test_seed_migration.py",
]

FILES = {
    "alembic/versions/s4chedule_flags_and_meal_items.py": 'revision = "s4chedule"\n',
    "tests/migrations/test_schedule_migration.py": 'previous_revision("s4chedule")\n',
    "tests/migrations/test_seed_migration.py": 'scratch.alembic("upgrade", "v1ocabulary")\n',
}


def _select(*changed):
    return select(list(changed), FILES.get, TESTS)


def test_a_route_change_runs_the_unit_tier_and_the_tests_it_touches():
    assert _select("app/routers/heating.py", "tests/api/test_heating.py") == [
        *ALWAYS,
        "tests/api/test_heating.py",
    ]


def test_a_frontend_change_runs_the_unit_tier_alone():
    assert _select("frontend/src/App.jsx") == ALWAYS


def test_a_new_revision_runs_the_guards_and_its_own_tests_only():
    """The mirror is in the same assertion: test_seed_migration.py names
    other revisions and must not be selected for this one."""
    assert _select("alembic/versions/s4chedule_flags_and_meal_items.py") == [
        *ALWAYS,
        *MIGRATION_GUARDS,
        "tests/migrations/test_schedule_migration.py",
    ]


def test_a_model_change_runs_the_migration_guards():
    assert _select("app/models/recipe.py") == [*ALWAYS, *MIGRATION_GUARDS]


def test_a_change_to_the_harness_runs_everything():
    for path in ("tests/conftest.py", "tests/databases.py", "requirements.txt", ".github/workflows/ci.yml"):
        assert _select(path, "app/routers/heating.py") is None, path
