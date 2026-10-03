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

- `air_fryer` (`tests/api/test_ingredient_storage.py`) is a cooking method that
  a heating row then points at. It is what makes
  `test_a_cooking_method_in_use_by_a_heating_row_cannot_be_deleted` bite: with
  no referencing row the delete is simply allowed, and the refusal is vacuous.
  It is also what gives the delete-count tests a non-zero `heating` count to get
  stale.
- `tests/test_seed_migration.py` inserts a label 飯 and a category 肉類 *before*
  the vocabulary migration runs. On an empty database every seed `INSERT`
  succeeds and `ON CONFLICT DO NOTHING` is never consulted, so a seed written
  without it passes. The pre-existing rows are the only thing that proves the
  clause is there. The storage test is built the same way: it needs old
  preservation rows to prove the range copy and the lossy downgrade, and a
  migration run over an empty table touches nothing. So is the `v2ocabulary`
  test: recipes and sources holding every old status and platform string
  before the upgrade are what prove the mapping, and a status and a platform
  created after it are what prove the downgrade's fallback. And the
  `a1uthors` test: sources holding creators before the upgrade - two
  spellings of one name, a padded one, a kana one and a source with none -
  are what prove the de-duplication, the trim, the slot rule and the
  null-skip; on an empty table the upgrade creates no author and passes.
- `recipe_statuses` and `source_platforms` (`tests/api/conftest.py`) are the
  rows `v2ocabulary` seeds, which `create_all` does not. `recipe.status_id`
  is NOT NULL, so every module that saves a recipe takes `recipe_statuses`
  (most through `pytestmark`), as an ingredient takes `fallback_category`. The
  test that a create with no status at all is a 422 empties the table first,
  on purpose. The 409 tests for a status, a platform and an author put a
  recipe or sources on the value; an unused value beside it deletes, as the
  mirror. Authors are not seeded and have no fixture: each test that needs
  one makes it, and the `new_author` reuse test's existing author is what
  makes "reuses, does not create" able to fail.
- `image_dir` (`tests/api/test_images.py`) is **autouse**, and points
  `IMAGE_DIR` at the test's own `tmp_path`. It has to be: the `/images` mount is
  built when the app is, and the `client` fixture builds the app, so a test that
  chose its directory afterwards would have mounted the real one.
- `soy` (`tests/api/test_ingredient_used_in.py`) is 醬油 with 生抽 and 老抽
  under it, a dish naming **both** children, a base naming 生抽, and a dish that
  uses only the base. Each piece is load-bearing for one claim: two children in
  one dish is what makes "counts once on the parent" able to fail (one child
  could only ever count once); the dish-through-a-base is what makes "depth
  through sub-recipes is zero" able to fail; and the lines are what give the
  delete refusal something to refuse.
- `pair` (`tests/api/test_ingredient_merge.py`) gives the source and the target
  something to **conflict** on: a shared label, a shared image, a storage row
  with the same `(state, method)`, a description on both, and a source
  `name_alt` that is the target's own English name in another case. A merge
  over two ingredients with nothing in common moves everything and drops
  nothing, so "the target wins" would pass against code that let the source
  win. Both storage rows also sit at `sort_order` 0 on their own ingredient,
  which is what lets the "numbered after the target's" test fail: a move that
  kept the source's number would tie rather than sort wrong.
- `test_a_source_edited_after_the_preview_is_409_and_changes_nothing` edits a
  prose field the preview did not list, so its plan really differs; its mirror
  merges with the fresh preview's fingerprint, so a guard refusing every merge
  cannot pass it.
- An unknown id in a body is refused twice over: by the service, which names
  the id, and by the foreign key behind it, which answers 422 with a generic
  sentence. A refusal test asserting only the status passes with the service
  check deleted, so `test_a_version_of_a_missing_recipe_is_refused` and the
  recipe gallery's unknown-image test assert the id in `detail`, with a real
  row beside the missing one and its permitted mirror.
- The cycle tests come in a set: a self-reference, a two-recipe cycle, a
  three-recipe cycle, and `test_a_chain_without_a_cycle_is_fine`. The last is
  the mirror; without it a guard refusing every sub-recipe line would pass the
  other three.
- `test_re_sending_the_same_lists_unchanged_does_not_collide_with_itself` is the
  test for the unit-of-work ordering trap: lines and steps have a unique
  position per recipe, so a replace that inserts before it deletes collides
  with itself on the first unchanged re-send. Module 1 shipped that defect for
  aliases; this is what keeps recipes from repeating it.
- `labels` (`tests/api/test_kitchen_notes.py`) gives the unknown-label test a
  real label to send beside `999999`, and the test asserts the id in
  `detail`: with the service check removed, the foreign key still answers 422,
  but with a generic sentence. The note-image delete test asserts `owners` on
  the 409 for the same reason - the `RESTRICT` alone answers 409 too, with no
  owners on the body. Both were proved to fail with their service check
  removed.

One more that is weaker than it looks unless read carefully:
`test_uvicorns_own_loggers_are_taken_over` asserts the handler **by identity**
against the root console handler. Asserting merely that a handler exists passes
while the bug is present, because uvicorn installs one of its own — which is
the entire failure.

## Where the tests are

| File | What it covers |
| --- | --- |
| `tests/api/test_ingredient_crud.py` | create, read, update, delete and search over HTTP; re-sending existing aliases and storage rows on `PATCH` |
| `tests/api/test_category_crud.py`, `test_label_crud.py` | the same round trip for categories and labels |
| `tests/api/test_ingredient_storage.py` | storage state and range, heating, links, rating, the new list filters, the delete counts and the 409 that names the moved one, `/api/vocabularies/fixed` |
| `tests/api/test_vocabularies.py` | the six vocabularies, parametrised over one factory, the in-use 409 for each, and authors in name order |
| `tests/api/test_images.py` | upload, re-encode, deduplication, ingredient and recipe galleries (kitchen-note galleries are in `test_kitchen_notes.py`), an image's owners, deletion, serving |
| `tests/api/test_recipe_model.py` | every named recipe constraint, each refusal with its mirror; SET NULL on a version's parent; CASCADE and RESTRICT on delete |
| `tests/api/test_recipe_crud.py` | the recipe round trip, `PATCH` list semantics, kind and status, the default status and the 422 with none, sources and their platforms, the version rule, delete refusals and stale counts |
| `tests/api/test_recipe_lines.py` | line targets, the claimed-type refusal, the cycle guard, stub creation and reuse |
| `tests/api/test_recipe_library.py` | the list's search (wildcards literal) and "any of" filters (`author_id` among them), the summary's authors, and the query count |
| `tests/api/test_kitchen_notes.py` | every named kitchen-note constraint with its mirror, CASCADE on delete, the round trip, title, kind, link and label refusals, newest-first order, `q` over title and body (wildcards literal), the "any of" filters, the query count, the gallery and the image 409 naming a note |
| `tests/api/test_ingredient_used_in.py` | "used in" over descendants, the list filter agreeing with it, the delete refusal, the query count |
| `tests/api/test_ingredient_merge.py` | merge preview against merge outcome, conflict rules, ordering after the target's rows, the fingerprint and its 409, refusals |
| `tests/test_seed_migration.py` | the seeds, the storage migration's copy and lossy downgrade, `v2ocabulary`'s string-to-row mapping and `a1uthors`'s creator-to-author mapping, each with its downgrade, on a scratch database |
| `tests/test_ingredient_import.py` | `i3import`: the committed CSV passes validation, each validation refusal with a good mirror, and the load on a scratch database — stubs, aliases, parents, categories, the skip rule, the cycle guard, a second run, the no-op downgrade |
| `tests/unit/test_prod_compose.py` | the production compose file, including the image bind mount |

**The image tests never touch the real `data/images`.** `image_dir` redirects
the setting to a temporary directory for every test in the file. The upload code
reads `IMAGE_DIR` at call time, so the redirect works; a file turning up in the
real directory would mean that rule had broken.

**The `i2storage` downgrade is tested against a scratch database**
(`food_seed_test`, created and dropped by the test), because it is the one
migration here that loses data on purpose. The test asserts what survives: rows
in a state other than `unused` are gone, and the range collapses to its maximum.

**The `i3import` load is tested against its own scratch database**
(`food_import_test`). Its skip rule is only exercised by **pre-existing
ingredients whose names match CSV rows** — 醬油 typed by hand, and an
ingredient answering to `garlic` only through an alias. On an empty database
every row inserts and the rule has nothing to skip, so those rows are the
load-bearing fixture, and the test asserts the hand-typed row is unchanged and
still becomes the parent of the file's 醬油 children. The validation function
is imported straight from the migration file (by path, with `importlib`) and run
on the committed CSV, so a defect in the file fails the suite before it fails a
deploy.

**The API test client rolls the shared session back after a refused request.**
The real `get_db` opens a session per request, which discards a failed flush.
The fixture hands every request the test's one session, so a request the
database refused would otherwise leave it needing a rollback and fail the *next*
request with an unrelated 500.

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
