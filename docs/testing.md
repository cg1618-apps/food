# Testing

```bash
venv/Scripts/python.exe -m pytest -q      # backend
venv/Scripts/ruff.exe check .             # backend lint
cd frontend && npm test                   # vitest, colocated with the source
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
  And the `g1roups` test: lines and steps carrying sections before the
  upgrade - one section split by another (醬汁, 主料, 醬汁), one matching a
  seeded value, a padded one, a blank one, two spellings of one name and rows
  with none - are what prove the first-use order, the vocabulary match, the
  trim, the de-duplication and the ungrouped-first re-numbering, and the
  downgrade's re-flattening; on empty tables the upgrade makes no group and
  passes. And the `s1tepkinds` test: a step stored before the upgrade is what
  proves existing rows take the `step` default; on an empty table a NOT NULL
  column without one would pass too. And the `d1ishes` test: recipes linked
  as versions before the upgrade - an original with an alias, a serves-as
  course and a label, one version with its own name and description, one
  sharing the original's name and description with labels of its own, a
  `base` recipe a version's line names, and a lone recipe - are what prove one
  dish per family, the original's names, the labels' union, base -> sauce, a
  version's own name kept and an identical one dropped, a differing
  description appended to the notes after 「原簡介：」, and the line repointed
  at the sauce's dish; the downgrade back to `t1bd` is asserted on the same
  rows (names, kind, course, description and labels back on every recipe,
  versions pointing at the lowest-id recipe, the line at the sauce's
  recipe). On empty tables the upgrade makes no dish and passes.
- `recipe_statuses` and `source_platforms` (`tests/api/conftest.py`) are the
  rows `v2ocabulary` seeds, which `create_all` does not. `recipe.status_id`
  is NOT NULL, so every module that saves a recipe takes `recipe_statuses`
  (most through `pytestmark`), as an ingredient takes `fallback_category`. The
  test that a create with no status at all is a 422 empties the table first,
  on purpose. The 409 tests for a status, a platform and an author put a
  recipe or sources on the value; an unused value beside it deletes, as the
  mirror. Authors are not seeded and have no fixture: each test that needs
  one makes it, and the `new_author` reuse test's existing author is what
  makes "reuses, does not create" able to fail. A recipe also needs a dish:
  the API tests send `new_dish` (which the save finds or makes by name) or
  create the dish first, and the model tests' `make` makes one per recipe
  unless given `dish_id`.
- `line_groups` and `step_groups` (`tests/api/conftest.py`) are the
  材料分組 and 步驟分組 values `g1roups` seeds. They are what let a one-off
  group name be "stored as the 設定 value": with no value to match, every
  name stays one-off and that test would pass for the wrong reason. The 409
  test for a group value puts a recipe group on 主料 / 備料, and the unused
  配料 / 烹飪 beside them delete, as the mirror.
- `image_dir` (`tests/api/test_images.py`) is **autouse**, and points
  `IMAGE_DIR` at the test's own `tmp_path`. It has to be: the `/images` mount is
  built when the app is, and the `client` fixture builds the app, so a test that
  chose its directory afterwards would have mounted the real one.
- `soy` (`tests/api/test_ingredient_used_in.py`) is 醬油 with 生抽 and 老抽
  under it, a recipe naming **both** children, a sauce's recipe naming 生抽,
  and a recipe whose only line names the sauce's dish. Each piece is
  load-bearing for one claim: two children in one recipe is what makes "counts
  once on the parent" able to fail (one child could only ever count once);
  the recipe-through-a-sauce is what makes "depth through sub-dishes is zero"
  able to fail; and the lines are what give the delete refusal something to
  refuse.
- The schedule's refusals (`tests/api/test_schedule.py`) each make the thing
  they refuse. The dish-delete refusal puts the dish in **three real meal
  items** on two dates, two of them on one date and one beside another dish -
  so the count (items), the dates list (each once) and the join can each
  fail - and clears them as its mirror; `test_an_unscheduled_dish_deletes`
  has a scheduled dish beside the free one, so "nothing is scheduled at all"
  cannot pass it. The recipe/dish mismatch has **two dishes**, the recipe
  belonging to the other one, and its mirror sends the matching dish. The
  duplicate-item refusal sends the same dish twice, and the same recipe once
  with its dish and once alone; its mirrors are the same dish with two
  different recipes and the same dish in two meals.
- **`tests/test_schedule_migration.py` seeds rows at `s3chedule` before
  running `s4chedule`** - a non-blank mark, a whitespace one, a NULL one, a
  meal with a dish and recipe, one with text alone - because on an empty
  schedule every conversion succeeds whatever it does. The downgrade test
  inserts a meal's items out of position order, so "first" has to mean the
  position.
- **A dish's delete refusals each have a referencing row and a mirror**
  (`tests/api/test_dish_crud.py`). `test_a_dish_with_recipes_cannot_be_deleted`
  makes a recipe of the dish, asserts the 409 lists it under `recipes`, then
  deletes the recipe and the dish goes; `test_a_dish_a_line_names_cannot_be_deleted`
  makes a recipe of another dish whose line names it, asserts it under
  `used_in`, then clears the line and the dish goes. With no recipe and no
  line the refusal has nothing to refuse and passes vacuously. At the model
  level `test_a_dish_with_a_recipe_cannot_be_deleted` and
  `test_a_dish_named_by_a_line_cannot_be_deleted` assert the foreign key's
  name, so `passive_deletes="all"` on `Dish.recipes` and `RecipeLine.sub_dish`
  is what refuses, not something incidental; their mirrors are
  `test_a_dish_without_recipes_deletes_with_what_it_owns` and
  `test_a_recipe_using_a_dish_can_be_deleted`.
- `test_a_new_dish_whose_name_exists_reuses_that_dish` makes the dish first,
  answering by an alias in another case: with none, every `new_dish` creates
  and a reuse that never happened would pass. The own-dish refusal
  (`test_a_recipe_cannot_use_its_own_dish`) has a second recipe of the dish
  and a mirror naming a different dish.
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
  check deleted, so `test_a_missing_dish_is_422_naming_it`, the line tests
  for a missing ingredient or dish, and the gallery unknown-image tests
  assert the id in `detail`, with a real row beside the missing one and its
  permitted mirror.
- The cycle tests come in a set: the own dish, a two-dish cycle, a cycle
  closed through another recipe of the dish, a three-dish cycle, moving a
  recipe to a dish its lines name, and `test_a_chain_without_a_cycle_is_fine`.
  The last is the mirror; without it a guard refusing every sub-dish line
  would pass the others.
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
- `body_refs` (`tests/api/test_recipe_templates.py`) gives a template one of
  everything its body can name - an ingredient, a dish, a 材料分組 value, a
  method, a piece of equipment - so the stale-reference test has something to
  drop, and that test reads the same template first and asserts `dropped`
  is 0: a count that was always 4, or always 0, fails one of the two reads.
  The merge test names a third ingredient beside the source, so a rewrite
  that changed every line would fail; it was proved to fail with the rewrite
  removed from `merge()`. The `new_ingredient` / `new_dish` refusal has its
  mirror in a line naming an existing ingredient, and the unique-name
  refusal in a template renamed to its own name in another case.

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
| `tests/api/test_vocabularies.py` | the nine vocabularies, parametrised over one factory, the in-use 409 for each (a course or region a dish is filed in), and authors in name order |
| `tests/api/test_images.py` | upload, re-encode, deduplication, ingredient, dish and recipe galleries (kitchen-note galleries are in `test_kitchen_notes.py`), a dish's cover falling back to its first recipe's, an image's owners, deletion, serving |
| `tests/api/test_recipe_model.py` | every named dish and recipe constraint, each refusal with its mirror; a recipe's display name falling back to its dish's; CASCADE and RESTRICT on delete, and a recipe's delete leaving its dish |
| `tests/api/test_dish_crud.py` | the dish round trip, kind, names, unknown ids, its recipes and "used in", the two delete refusals with their mirrors, the stale alias count, 404s |
| `tests/api/test_dish_library.py` | the dish list's summary, search and "any of" filters, and the recipe list's filters that read through the dish (dish, kind, course, region, label) and its search over the dish's names |
| `tests/api/test_recipe_crud.py` | the recipe round trip, its dish (`dish_id`, `new_dish`, reuse by name, moving), 其他版本, `PATCH` list semantics, status, the default status and the 422 with none, the moved fields refused, sources and their platforms, delete leaving the dish, stale counts |
| `tests/api/test_recipe_lines.py` | line targets (ingredient, dish, new ingredient, new dish), the claimed-type refusal, the own-dish rule and the cycle guard through dishes, stub and dish creation and reuse |
| `tests/api/test_recipe_step_kinds.py` | a step's kind: the `step` default, the round trip through create, read and `PATCH` in and out of groups, the 422 for an unknown or null kind, the `step_kinds` fixed list |
| `tests/api/test_recipe_groups.py` | lines and steps in groups: order and positions, a name stored as its 設定 value, the empty group, duplicate and malformed groups, the `PATCH` pair rule, stubs, cycles and a dish's "used in" through grouped lines, the delete counts, the in-use 409, SET NULL from a group to its rows |
| `tests/api/test_recipe_library.py` | the list's summary (its dish), search over the dish's names and aliases (wildcards literal) and the recipe's own filters (`author_id` among them), and the query count |
| `tests/api/test_kitchen_notes.py` | every named kitchen-note constraint with its mirror, CASCADE on delete, the round trip, title, kind, link and label refusals, newest-first order, `q` over title and body (wildcards literal), the "any of" filters, the query count, the gallery and the image 409 naming a note |
| `tests/api/test_ingredient_used_in.py` | "used in" over descendants, the list filter agreeing with it, the delete refusal, the query count |
| `tests/api/test_ingredient_merge.py` | merge preview against merge outcome, conflict rules, ordering after the target's rows, the fingerprint and its 409, refusals |
| `tests/api/test_common_ingredients.py` | 常用食材: the whole-list `PUT` and its order, the unknown-id and duplicate 422s that change nothing, the write only under the gated prefix, CASCADE on an ingredient's delete, and a merge moving or dropping the source's entry |
| `tests/api/test_heating.py` | 加熱: the blank-name CHECK, the round trip with line breaks kept, a blank body stored as null, the no-name 422 on create and the blank-name `PATCH` 422 with the mirror that renames, a `PATCH` applying only what it sends, a new note last, the delete, the order `PUT` and each of its 422s against three real notes, the writes only under the gated prefix |
| `tests/api/test_tbd.py` | TBD: the blank-url CHECK and CASCADE to links, the round trip, the name-or-link 422 on create and on a `PATCH` that would leave neither (with the mirror that keeps a name), a new entry last, `https://` given to a link without a scheme and the 422 for a blank or non-web one, links replaced wholesale or left alone, the delete, the order `PUT` and each of its 422s against three real entries, the writes only under the gated prefix |
| `tests/api/test_schedule.py` | the schedule: the Saturday a week starts on, the default range from a pinned today, every date answered stored or not, the `days` bounds, the day round trip with its meals, marks defaulting to false and refusing text, `PUT` replacing the whole day, blanks as null and empty meals and days not stored, unknown slots and fields, a meal of text only, of items only and of both, several items kept in order, a recipe implying its dish, a recipe of another dish, an item naming nothing and a duplicate item refused, unknown ids, a refused `PUT` changing nothing, a dish delete refused while meal items name it (with the dates) and its mirrors, a recipe delete leaving the item its dish, `meal_slots` in the fixed vocabularies |
| `tests/test_schedule_migration.py` | `s4chedule` on a scratch database: marks turned into booleans from the stored text, each meal's dish and recipe moved into one item, and the downgrade writing ✓ and keeping the first item |
| `tests/api/test_recipe_templates.py` | recipe templates: the round trip with every reference resolved, the empty template, a group name stored as its 設定 value, the list's order and counts, the `new_*` 422 that creates nothing (with its mirror), unknown ids, the case-insensitive unique name and blank name, fields a template does not carry, `PATCH` semantics and a refused `PATCH` changing nothing, delete, the order `PUT` and its 422s, stale references dropped and counted (a dropped group's lines kept as ungrouped), a template from a recipe's structure, and an ingredient merge rewriting template lines |
| `tests/test_seed_migration.py` | the seeds, the storage migration's copy and lossy downgrade, `v2ocabulary`'s string-to-row mapping, `a1uthors`'s creator-to-author mapping, `g1roups`' sections-to-groups move, `s1tepkinds`' default for existing steps and `d1ishes`' grouping of recipes into dishes, each with its downgrade, on a scratch database |
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

## Frontend tests

Vitest with jsdom, each test file beside its source. The pages are tested
through the real route table (`AppRoutes`) against a stubbed `fetch`, so a
test reads what the page asks for and what it sends. jsdom cannot drag:
every reorder is driven through the handle's keyboard path.

The dish split is covered in: `pages/library/libraries.test.jsx` (the dish
library's filters going to the URL and the API, its card and table, the
empty library; the recipe library's 料理 and 種類 filters and the dish name
under a recipe's own), `pages/detail/details.test.jsx` (a dish page's
recipes, its 「＋ 新增食譜」 link with `?dish=`, a sauce's 用在, a refused
dish delete listing both `recipes` and `used_in`; a recipe page's dish link,
its read-only dish fields and 其他版本), `components/forms/forms.test.jsx`
(the recipe form's dish picker - an existing dish, a new one as 料理 or
醬料, the `?dish=` preset, the refusal with none - a line's 新增料理 sent as
a sauce `new_dish`, and the dish form's payload), `pages/edit/settings.test.jsx`
(the 地區 tab after 類別, label counts by 料理), `routes.test.jsx` (the dish
routes and the `/edit/dishes/:id/edit` redirect), `lib/nav.test.js` (料理
first), `lib/typeahead.test.js`, `lib/recipeLines.test.js` and
`lib/imageOwners.test.js`.

Recipe templates are covered in: `pages/edit/templates.test.jsx` (the
new-recipe chooser's three ways in and the URL each writes, `?dish=` kept
through them; the form prefilled from a template - the dropped notice, and
nothing written before 儲存 - and from another recipe - its dish unless
`?dish=` names one, and not its name, sources, status or pictures; a
template that cannot be read; the template form's payload, its refusal of
新增 and of a missing name, and a saved template sent back whole),
`pages/edit/settings.test.jsx` (the 範本 tab: order, counts and links, the
keyboard reorder frozen until the `PUT` lands and put back on a refusal,
rename with a refused name explained in the row, delete after asking),
`pages/detail/details.test.jsx` (存成範本: the name asked for, a refused
name, the link to the new template), `lib/newRecipe.test.js`,
`lib/recipeStructure.test.js` and `lib/typeahead.test.js` (recipes as
options).

The schedule is covered in: `pages/library/schedule.test.jsx`, with today
pinned to a Wednesday by faking `Date` alone (the read page asking for two
weeks from the Saturday, the tables' columns in the page's order, a ✓ for
a true mark and nothing for a false one, a meal's text and then each item on
its own line with its dish and recipe links, today marked, the phone card
listing only filled fields with a chip per true mark, `?week=` read as its
Saturday and the week links; the edit page laid out in the columns' order,
filled from what is stored with marks as checkboxes and each item's dish's
recipes in its select, one `PUT` of the whole day with the exact body, the
week buttons disabled while a day is unsaved, an item removed and dishes
appended one after another, a dish picked for an empty meal, 更換 replacing
an item's dish in place, a typed-but-unpicked dish refused with nothing
sent, and the server's refusal shown on the card with the typing kept),
`lib/schedule.test.js` (Saturday weeks across months, years and a leap day,
`?week=` parsing, ranges, the phone card's fields and marks, item keys, the
payload),
`pages/detail/details.test.jsx` (a dish delete refused with `meals`, each
date linked to its week), `lib/nav.test.js` and `routes.test.jsx`.

The recipe form's own tests in `components/forms/forms.test.jsx`
open it at `/edit/recipes/new?blank=1` and are otherwise unchanged by the
move of 材料, 步驟 and 做法、器材 into shared sections.

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
