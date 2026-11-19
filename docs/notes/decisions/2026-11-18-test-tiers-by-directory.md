# Test tiers by directory, and where food differs from media

The tiers and the per-run database are described in `docs/testing.md`. What a
reader comparing with `media` would trip on:

- **A directory, not a pytest marker.** A database test someone forgot to mark
  would land in the fast tier and fail there on every pull request; a file in
  the wrong directory is visible in review.
- **`tests/migrations` is its own directory**, where `media` keeps its
  migration tests in `tests/api`. food's migration tests share nothing with
  the API fixtures (no `db`, no `client`), and one directory lets
  `scripts/pr_tests.py` find "the tests for the revisions this pull request
  adds" by looking in one place.
- **Names follow `media`'s `food_test_<epoch>_<hex>`, not a bare uuid.** The
  epoch lets a run's start-up cleanup tell an abandoned database from one a
  neighbouring run has just created and not yet connected to; "no
  connections" alone would drop a scratch database in the gap between `CREATE
  DATABASE` and the Alembic subprocess opening it.
- **The run's database is created by a session fixture**, not at import of
  the root conftest as `media` does. media checks its schema at import time
  and has to; food's app opens no connection until a request, so the fixture
  is enough and the unit tier never touches the server.
