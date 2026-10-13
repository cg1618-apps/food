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
- `meat_tree` (`tests/api/test_ingredient_storage.py`) is 肉類 with nothing
  filed directly in it, 雞肉 below it holding 雞腿, 去骨 below that holding
  one more, and a sibling 海鮮 holding 蝦. The empty parent is what makes the
  subtree test bite - an exact filter answers 肉類 with nothing - and the
  sibling is what makes the mirror bite: a filter ignoring the category would
  return 蝦 too.
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
- The line-alternative refusals (`tests/api/test_recipe_line_alternatives.py`)
  each make the thing they refuse. The unknown-id 422 has a real ingredient
  and a real dish in the database, sends a second, valid new-name alternative
  beside the bad one to prove the refused save created nothing, and its
  mirror saves alternatives naming the real rows. Both delete refusals put a
  **real alternative** on the row - the only thing naming it - and their
  mirrors remove the alternative and delete. The cycle test builds a loop that
  runs **only through an alternative** (A's line offers B; B's line names A),
  so a guard that read lines alone would pass B's save; its mirror removes
  A's alternative and B then saves. The merge test has one line for each case
  - an alternative that moves, one dropped because its line names the target,
  one dropped because its line named the source, and two that collapse - so
  each count in the preview can fail on its own.
- `soy` (`tests/api/test_ingredient_used_in.py`) is 醬油 with 生抽 and 老抽
  under it, a recipe naming **both** children, a sauce's recipe naming 生抽,
  and a recipe whose only line names the sauce's dish. Each piece is
  load-bearing for one claim: two children in one recipe is what makes "counts
  once on the parent" able to fail (one child could only ever count once);
  the recipe-through-a-sauce is what makes "depth through sub-dishes is zero"
  able to fail; and the lines are what give the delete refusal something to
  refuse.
- `shallot_crisps` (`tests/api/test_homemade_version.py`) is a real dish in
  every test there. It is what makes the 422 for a `homemade_dish_id` naming
  no dish mean "no such id" rather than "no dishes at all", and the test also
  asserts the sentence, since an unknown field is a 422 too. The SET NULL
  test deletes a dish an ingredient really names, with no recipes - the
  mirror of the dish-delete refusals - and asserts the ingredient survives
  with a null link; a second test deletes in raw SQL, so the schema's
  `ON DELETE` is proven and not the ORM's. The merge tests cover both
  branches: the target with a link of its own keeps it, and the target
  without one takes the source's.
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
- `labels` (`tests/api/test_label_scope.py`) makes a 辣 in **every**
  library, so each owner's wrong-scope refusal has a real label of another
  library to send, and each has its mirror sending its own library's label
  through the same route; without the other scopes' labels a check that
  refused nothing would pass. The move refusal puts the label on a dish
  first - an unused label moves - and its mirror renames the same in-use
  label and sends its own scope back. `tests/test_label_scope_migration.py`
  seeds labels at `h1eating` before running `l1abels`: one per library, one
  carried by nothing (and the eight seeded ones), and separately one carried
  by two libraries. On an empty `label` table the backfill, the deletion and
  the refusal all pass by doing nothing.
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

- `chicken_tree` (`tests/api/test_category_clash.py`) gives the clashing
  category 雞肉 every kind of row a conversion touches - a top-level
  ingredient, one already a variety of an ingredient filed elsewhere, a child
  category with its own ingredient, and notes - so the conversion test
  asserts each outcome rather than passing on an empty category, and the
  preview's lists are checked against real rows. Every refusal has its
  mirror with the same rows: a name no category has saves (an ingredient, a
  category, a recipe's stub), a save not changing a name is not checked, a
  freed sibling name lets the blocked conversion run, the fresh fingerprint
  goes through after the stale one is refused, and one clash alone is the
  ordinary offer beside the two-category refusal. The blocked and stale
  tests commit their rows and roll the session back after the refusal - what
  closing the request session does - then assert every row where it was: a
  refusal that had committed part of the conversion first would fail them.
  The update test rolls back the refused rename for the same reason; left in
  the shared session it makes the resend change no name, and the conversion
  silently does not run.

One more that is weaker than it looks unless read carefully:
`test_uvicorns_own_loggers_are_taken_over` asserts the handler **by identity**
against the root console handler. Asserting merely that a handler exists passes
while the bug is present, because uvicorn installs one of its own — which is
the entire failure.

## Where the tests are

| File | What it covers |
| --- | --- |
| `tests/api/test_ingredient_crud.py` | create, read, update, delete and search over HTTP; re-sending existing aliases and storage rows on `PATCH` |
| `tests/api/test_category_crud.py`, `test_label_crud.py` | the same round trip for categories and labels; a category's `description` through create, the tree (a child's too), `PATCH` and clearing, blank stored as null |
| `tests/api/test_label_scope.py` | every label in one library: `scope` required and known, names unique per scope, `?scope=`, a move allowed while unused and the in-use 409, and each owner (ingredient create, update and attach; dish; note) refusing another library's label, each with its mirror |
| `tests/test_label_scope_migration.py` | `l1abels` on a scratch database: used labels scoped by their one library, unused ones deleted, uniqueness per scope, the refusal on a label two libraries carry (changing nothing), and the downgrade with its own refusal |
| `tests/api/test_ingredient_storage.py` | storage state and range, heating, links, rating, the new list filters (the category filter over a subtree, its sibling mirror, and the list agreeing with the tree's subtree totals), the delete counts and the 409 that names the moved one, `/api/vocabularies/fixed` |
| `tests/api/test_vocabularies.py` | the nine vocabularies, parametrised over one factory, the in-use 409 for each (a course or region a dish is filed in), and authors in name order |
| `tests/api/test_author_details.py` | an author's links and 備註: the blank-url CHECK and CASCADE to links (with two links really present), the round trip in order, a blank 備註 as null, `https://` given to a link without a scheme, the 422 for a blank, `javascript:` or other non-web url with nothing written and the mirror that saves, a refused `PATCH` keeping the stored links, links replaced wholesale, left alone, cleared by `[]` and the null refused, the delete taking the links, and the other eight vocabularies refusing `notes` and `links` with the author accepting the same body |
| `tests/api/test_images.py` | upload, re-encode, deduplication, ingredient, dish and recipe galleries (kitchen-note galleries are in `test_kitchen_notes.py`), a dish's cover falling back to its first recipe's, an image's owners, deletion, serving |
| `tests/api/test_recipe_model.py` | every named dish and recipe constraint, each refusal with its mirror; a recipe's display name falling back to its dish's; CASCADE and RESTRICT on delete, and a recipe's delete leaving its dish |
| `tests/api/test_dish_crud.py` | the dish round trip, kind, names, unknown ids, its recipes and "used in", the two delete refusals with their mirrors, the stale alias count, 404s |
| `tests/api/test_dish_library.py` | the dish list's summary, search and "any of" filters, and the recipe list's filters that read through the dish (dish, kind, course, region, label) and its search over the dish's names |
| `tests/api/test_recipe_crud.py` | the recipe round trip, its dish (`dish_id`, `new_dish`, reuse by name, moving), 其他版本, `PATCH` list semantics, status, the default status and the 422 with none, the moved fields refused, sources and their platforms, `reheating_notes` (加熱) round-tripping and cleared as `storage_notes` is, delete leaving the dish, stale counts |
| `tests/api/test_recipe_lines.py` | line targets (ingredient, dish, new ingredient, new dish), the claimed-type refusal, the own-dish rule and the cycle guard through dishes, stub and dish creation and reuse |
| `tests/api/test_recipe_line_alternatives.py` | a line's alternatives: the round trip in order with amount and note, in a group, new names resolved with the lines' (one stub for a name typed on both), the unknown-id 422 writing nothing, exactly one target, redundant alternatives dropped, a re-save replacing them; the own-dish rule, the cycle guard and a dish move through an alternative; "used in" for an ingredient (a variety's included) and a dish with `alternative_only`, the recipe filter; both delete refusals with mirrors, the RESTRICT itself, the CASCADE with the recipe; the ingredient merge moving and dropping them with the preview's counts and the fingerprint; templates carrying them, dropping a deleted one, `from-recipe`, a body stored before them, and a merge rewriting them |
| `tests/test_line_alternatives_migration.py` | `a2lternatives` on a scratch database: the downgrade drops the table with an alternative in it and keeps the line, and the chain upgrades again |
| `tests/api/test_recipe_step_kinds.py` | a step's kind: the `step` default, the round trip through create, read and `PATCH` in and out of groups, the 422 for an unknown or null kind, the `step_kinds` fixed list |
| `tests/api/test_recipe_groups.py` | lines and steps in groups: order and positions, a name stored as its 設定 value, the empty group, duplicate and malformed groups, the `PATCH` pair rule, stubs, cycles and a dish's "used in" through grouped lines, the delete counts, the in-use 409, SET NULL from a group to its rows |
| `tests/api/test_recipe_library.py` | the list's summary (its dish), search over the dish's names and aliases (wildcards literal) and the recipe's own filters (`author_id` among them), and the query count |
| `tests/api/test_kitchen_notes.py` | every named kitchen-note constraint with its mirror, CASCADE on delete, the round trip, title, kind, link and label refusals, newest-first order, `q` over title and body (wildcards literal), the "any of" filters, the query count, the gallery and the image 409 naming a note |
| `tests/api/test_ingredient_used_in.py` | "used in" over descendants, the list filter agreeing with it, the delete refusal, the query count |
| `tests/api/test_homemade_version.py` | an ingredient's 自製版: the round trip and `PATCH` set / change / clear, any dish kind, one dish named by several ingredients as the dish's `bought_as`, the 422 for an id naming no dish (writing nothing), SET NULL through the API and in raw SQL, the cascade's `bought_as`, and the merge keeping the target's or taking the source's, with its preview word and fingerprint |
| `tests/api/test_category_clash.py` | a name is a category or an ingredient, never both: the 409 and its `category_clash` preview (English name and case included; aliases and `name_alt` not), the conversion's every outcome, the ingredient keeping its own category and description, the ancestor kept top-level, conversion on update and no check on an update leaving the names, a top-level category's target and its 422s, a parent's other target refused, the sibling-name block (422, nothing changed), a child sharing the category's name moving up, the stale fingerprint (409, nothing changed), the fallback's 422, two clashing categories' 409, a category created or renamed under an ingredient's name refused (409) and a drag not, the recipe stub's 422 |
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
(the 地區 tab after 類別), `routes.test.jsx` (the dish
routes and the `/edit/dishes/:id/edit` redirect), `lib/nav.test.js` (料理
first), `lib/typeahead.test.js`, `lib/recipeLines.test.js` and
`lib/imageOwners.test.js`.

Labels' libraries are covered in: `pages/edit/settings.test.jsx` (the three
sections in order, an add sending its section's scope, 移到 off for a label in
use and on for an unused one, and a refused move said in the row),
`pages/library/libraries.test.jsx` (each sidebar asking for its own scope,
the recipe library for `dish`, against a server answering only `dish`) and
`components/forms/forms.test.jsx` (the dish form reading `?scope=dish`).

Line alternatives are covered in: `lib/recipeLines.test.js` (read back as
targets in order, a body without them reading as none, the payload's four
targets, a blank one dropped, and the unpicked one refused naming its line
and its number), `components/forms/forms.test.jsx` (「＋替代」 under a line:
an existing dish, a 新增 stub, a note and an amount, one removed, the exact
payload; and the unpicked refusal sending nothing),
`pages/detail/details.test.jsx` (a line's alternatives after it with their
links, amounts and notes, a line without them unchanged; 替代 in an
ingredient's and a sauce's 用在), `lib/mergePreview.test.js` (the moved and
dropped counts) and the payload expectations of every recipe and template
form test, which now carry `alternatives: []`.

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

Authors' links and 備註 are covered in: `pages/edit/settings.test.jsx`
(the row's 編輯 opening the stored links and 備註, a link added and the
remark changed sent as one `PATCH` in order, a link removed and a blank
remark sent as `[]` and null), `pages/library/libraries.test.jsx` (the
panel above the recipe library filtered to one author - its heading,
links by label or by address, each `target="_blank"` with
`rel="noopener noreferrer"`, the 備註 with its line break - and its
mirror: no panel for an author with neither, nor for two authors, once the
authors have loaded) and `lib/authors.test.js` (the draft and the body).

The category clash is covered in: `components/forms/forms.test.jsx` (the
ingredient form's 409 opening 「轉成食材」 with each outcome in words, 轉成食材
resending the same body with `convert_category`, 取消 leaving the form unsaved
with one request sent, a top-level category's target select defaulting to the
fallback and never offering the category or its subtree, the sibling block
turning the button off, a stale preview replaced and confirmed with the fresh
fingerprint) and `pages/edit/settings.test.jsx` (a category rename refused
for an ingredient's name, said in the row with the typing kept).

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
