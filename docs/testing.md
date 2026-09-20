# Testing

```bash
venv/Scripts/python.exe -m pytest -q      # backend
venv/Scripts/ruff.exe check .             # backend lint
```

**One pytest at a time across the whole machine.** All four apps share one
PostgreSQL, and concurrent runs produce spurious "relation does not exist" and
unique-constraint failures that look like real breakage. The lock is in the
platform's `CLAUDE.md`; take it around every run.

## How the database is set up

Two mechanisms, deliberately, because each is blind to what the other catches.

**`tests/api/conftest.py` builds the schema with `Base.metadata.create_all`**
against a scratch `food_test` database, and isolates each test in an outer
transaction rolled back at teardown. The session joins that transaction with
`join_transaction_mode="create_savepoint"`, which is load-bearing: without it a
`rollback()` inside the code under test unwinds the outer transaction too, and
the fixture rows vanish mid-test with nothing to explain why.

**`tests/test_migrations_build_the_schema.py` runs the real
`alembic upgrade head`** against a scratch database created for the test. This
is what `create_all` cannot tell you. Media ran for 145 revisions with a chain
that could not build from nothing, invisible because its fixtures never ran
Alembic.

And because those two could still describe different databases, a third test
compares them with `compare_metadata` and asserts no differences. The migration
is hand-written and may not import from `app/models`, so nothing else makes the
two agree.

## What a test is called

A full sentence saying what is asserted —
`test_a_nameless_ingredient_is_refused`, not `test_create_ingredient_error`.
Every non-obvious test carries a docstring restating the decision it guards.

## Refusal tests, and the fixture that makes them bite

**A test that asserts something is refused can pass because there was nothing
to refuse.** A constraint over an empty set is satisfied; a uniqueness
constraint over nullable columns is satisfied by nulls; a rule about write
routes is satisfied by an app with no write routes. All three are green on day
one and stay green through the change that breaks them.

So every refusal test here is paired with a mirror asserting the *permitted*
case still works, and where the refusal needs data to be possible, that fixture
is load-bearing and says so. Some examples worth knowing about:

- `test_any_number_of_ingredients_may_leave_a_name_slot_empty` is what refuses
  a reintroduction of `postgresql_nulls_not_distinct` on a single-column name
  index. Without it that change looks like a fix.
- `test_a_category_with_ingredients_in_it_cannot_be_deleted` asserts the
  constraint *name* in the error. Before `passive_deletes="all"` it passed for
  the wrong reason — SQLAlchemy nulled the child's foreign key first and the
  NOT NULL raised instead, same exception type, same green, and the tree's
  `RESTRICT` never ran.
- `test_a_write_route_outside_the_prefix_is_caught` registers a deliberately
  misplaced route and asserts the check fails. It tests a route that does not
  exist in the application, which makes it look like decoration; it is the only
  thing distinguishing "nothing escaped the prefix" from "the check does not
  work".
- `test_the_app_actually_has_write_routes_to_check` asserts there is something
  to be wrong about, so the prefix assertion cannot pass vacuously.
- `test_the_f_string_guard_can_actually_fail` proves the AST scan in
  `test_no_log_call_formats_its_own_message` fires. That scan walks `app/` and
  asserts it found nothing; a detector that matches nothing at all passes it
  identically, and would keep passing through the change that fills this app
  with f-string log calls.
- `test_an_id_of_exactly_sixty_four_characters_is_honoured` is the mirror for
  the request-id validator. Every rejection case asserts "a fresh id was
  generated instead" — which a validator that refused *everything* would also
  satisfy. It sits on the boundary rather than safely inside it, so an
  off-by-one in the pattern is caught too.

One more that is weaker than it looks unless read carefully:
`test_uvicorns_own_loggers_are_taken_over` asserts the handler **by identity**
against the root console handler. Asserting merely that a handler exists passes
while the bug is present, because uvicorn installs one of its own — which is
the entire failure.

## Constraint violations are tested through HTTP

`tests/api/test_constraint_statuses.py` drives one case per row of the SQLSTATE
mapping in `docs/api.md` through the test client.

This exists because media documented the same discipline — mirror constraints
in the schema layer so a violation is a 422 rather than a 500 — and had about
sixty tests asserting `IntegrityError`, every one at the ORM level and none at
the HTTP layer the promise was about. The discipline drifted for years with a
green suite.

`TestClient(app, raise_server_exceptions=False)` is required for these:
otherwise Starlette re-raises inside the test and the registered handlers never
turn the exception into a response.
