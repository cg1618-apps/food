# Plan 2 — recipes

Working scaffolding: deleted when branch 2 merges. Spec:
`docs/superpowers/specs/2026-10-02-recipes-and-ingredients-v2-design.md`
("Recipes", "Behaviour", "API"). Branch `feat/recipes`, cut from `dev` at
`a6200d0`.

## Rulings made before execution

- **An id inside a request body that names no row is 422, everywhere.** Owner
  decision, 2026-10-02, superseding the spec's and module 1's hand-over's
  "404". The URL resolved; the payload was wrong. `check_parent`, labels and
  heating methods already answer 422; the gallery `PUT`'s unknown `image_id`
  changes from 404 to 422 in Task 3, which also deletes the open item and
  records the decision in `docs/notes/decisions.md`. A missing row named by
  the **URL** stays 404.
- **Docs land with their behaviour**, task by task: each task updates the
  `docs/` pages its change makes untrue, in the same commit.
- **Every list with a per-recipe unique position is cleared and flushed before
  it is reassigned** (lines, steps, gallery). The unit of work INSERTs before it
  DELETEs, so a wholesale replace that reuses position 0 collides with its own
  unique key — module 1 shipped that defect for aliases (`dfcfad1`), and
  `ingredients.set_images` carries the fix to copy.

## Conventions every task follows

Read before writing; copy, do not reinvent: `app/models/ingredient.py` (model
docstrings, `passive_deletes="all"` across RESTRICT), `app/services/ingredients.py`
(service shape, `_loaded`, `_apply_*`, `_as_entries`), `app/routers/ingredient.py`
(`read_router`/`write_router`, explicit `_response`, delete with echoed counts),
`app/errors.py` (`AppError`, `StaleCountError`, `CONSTRAINT_MESSAGES`),
`tests/api/conftest.py` (fixtures). Inputs `extra="forbid"`. Every refusal test
has its permitted mirror, with its set made non-empty (platform `CLAUDE.md`,
"Rule"). Backend tests run under the machine-wide lock:

```bash
LOCK=/c/Users/$USERNAME/AppData/Local/Temp/anime_site_pytest.lock
until mkdir "$LOCK" 2>/dev/null; do sleep 10; done
venv/Scripts/python.exe -m pytest -q; rc=$?
rmdir "$LOCK"; exit $rc
```

plus `venv/Scripts/ruff.exe check .`. Commits: conventional prefix, `git commit
-- <exact paths>`, **no trailers of any kind** (no Co-Authored-By, nothing
naming a tool). Do not push.

## Task 1 — schema

**Constants** (`app/constants.py`), dicts of value → display label, appended to
`FIXED_VOCABULARIES` as `recipe_kinds`, `recipe_statuses`, `source_platforms`:

- `RECIPE_KINDS = {"dish": "料理", "base": "基底"}`
- `RECIPE_STATUSES = {"want_to_try": "想試", "can_cook": "可煮", "regular": "常煮"}`
- `SOURCE_PLATFORMS = {"youtube": "YouTube", "shorts": "Shorts", "website": "網站", "book": "書", "other": "其他"}`

**Models**, `app/models/recipe.py` (one family, one file), exported from
`app/models/__init__.py`:

| Table | Columns and constraints |
| --- | --- |
| `recipe` | `id`; `name_cn`, `name_en`, `name_alt` (String, null); `kind` String NOT NULL server default `'dish'`; `course_id` → `recipe_course` RESTRICT, null, indexed; `variant_of_id` → `recipe` **SET NULL**, null, indexed; `status` String NOT NULL server default `'want_to_try'`; `servings`, `time` String null; `description`, `storage_notes`, `notes` Text null; `created_at`, `updated_at` as `Ingredient`. `ck_recipe_has_a_name` (num_nonnulls of the three ≥ 1); `ck_recipe_not_its_own_version` (`variant_of_id IS NULL OR variant_of_id <> id`). Names are **not** unique. `NameFallbackMixin`. |
| `recipe_alias` | as `ingredient_alias`: `uq_recipe_alias (recipe_id, value)`, `ix_recipe_alias_lookup lower(value)`, recipe CASCADE |
| `recipe_serves_as` | `recipe_id` CASCADE, `course_id` → `recipe_course` CASCADE, composite PK |
| `recipe_label` | `recipe_id` CASCADE, `label_id` CASCADE, composite PK |
| `recipe_method` | `recipe_id` CASCADE, `method_id` → `cooking_method` **RESTRICT**, composite PK |
| `recipe_equipment` | `recipe_id` CASCADE, `equipment_id` → `equipment` **RESTRICT**, composite PK |
| `recipe_source` | `id`, `recipe_id` CASCADE indexed, `platform` String NOT NULL, `creator`, `url`, `title` String null, `sort_order` default 0. `ck_recipe_source_has_content` (num_nonnulls(creator, url, title) ≥ 1) |
| `recipe_line` | `id`, `recipe_id` CASCADE indexed, `position` Integer NOT NULL, `section` String null, `ingredient_id` → `ingredient` **RESTRICT** null indexed, `sub_recipe_id` → `recipe` **RESTRICT** null indexed, `amount`, `note` String null, `is_optional` Boolean NOT NULL default false. `uq_recipe_line_position (recipe_id, position)`; `ck_recipe_line_one_target` (`num_nonnulls(ingredient_id, sub_recipe_id) = 1`); `ck_recipe_line_not_itself` (`sub_recipe_id IS NULL OR sub_recipe_id <> recipe_id`) |
| `recipe_step` | `id`, `recipe_id` CASCADE indexed, `position` NOT NULL, `section` String null, `body` Text NOT NULL. `uq_recipe_step_position` |

`recipe_image` goes in `app/models/image.py` beside `IngredientImage`, same
shape (`uq_recipe_image_position`, `uq_recipe_image_once`), and is appended to
`OWNER_TABLES` in `app/services/images.py` as `(RecipeImage, "recipe", Recipe)`.

Relationships on `Recipe`: `course`, `variant_of` / `variants`
(`passive_deletes=True` so the database applies SET NULL), `aliases`, `sources`,
`lines`, `steps`, `images` (cascade delete-orphan, ordered), `labels`,
`methods`, `equipment`, `serves_as` (secondary). `RecipeLine.ingredient` and
`RecipeLine.sub_recipe` with `passive_deletes="all"`. `Label` gains `recipes`
only if needed — do not add a back-relationship nothing reads.

**Migration** `alembic/versions/r1recipes_recipes.py`, revision `r1recipes`,
down `m1images`, docstring in the house style; downgrade drops the tables
(lossy: say so). Update the head pins in `tests/test_health.py` and
`tests/test_migrations_build_the_schema.py`.

**Errors:** one `CONSTRAINT_MESSAGES` sentence per new named constraint.

**Vocabulary usage** (`app/services/vocabularies.py`): course → count of
`recipe.course_id` (serves-as links CASCADE and are not a reason to refuse);
cooking method → heating rows **plus** `recipe_method` rows; equipment →
`recipe_equipment` rows. Remove `_nothing_yet` if nothing uses it.

**Tests:** `tests/api/test_recipe_model.py` in the style of
`test_ingredient_model.py` — each named constraint refuses and its mirror
commits; SET NULL on a version's parent; CASCADE of children on recipe delete;
RESTRICT of an ingredient and of a sub-recipe named by a line. A vocabulary
test that a cooking method used only by a recipe, and equipment used by a
recipe, refuse delete with `usage_count` (the in-use fixture is the
load-bearing one; mirror: unused deletes).

**Docs:** `docs/data-model.md` gains the recipe tables; `docs/api.md`'s fixed
vocabularies paragraph gains the three new lists.

## Task 2 — recipe CRUD

`app/schemas/recipe.py`, `app/services/recipes.py`, `app/routers/recipe.py`,
registered in `app/main.py` (read and write together).

**Input** `RecipeCreate` / `RecipeUpdate` (the `IngredientUpdate` pattern:
all-optional, `exclude_unset`). Fields: name slots (blank → None), `kind`,
`course_id`, `variant_of_id`, `status`, `servings`, `time`, `description`,
`storage_notes`, `notes`, and the lists `aliases`, `sources`, `lines`, `steps`,
`serves_as_ids`, `label_ids`, `method_ids`, `equipment_ids`. Each list sent
replaces the stored one; absent is untouched. Enum fields validated against the
constants (422).

- `SourceIn`: `platform`, `creator`, `url` (http/https via `_check_url`),
  `title`; at least one of the three (422). No `sort_order` — list order.
- `LineIn`: `section`, `ingredient_id`, `sub_recipe_id`, `new_ingredient`
  (`{name_cn?, name_en?}`, at least one), `amount`, `note`, `is_optional`.
  Exactly one of the three targets (422). No type field: `extra="forbid"` makes
  a payload claiming a type a 422, and the stored type is whichever column is
  set.
- `StepIn`: `section`, `body` (non-blank, 422).

**Line resolution**, one transaction:

- unknown `ingredient_id` / `sub_recipe_id` → 422 naming the id;
- `new_ingredient` → if any typed name equals (casefold) an existing
  ingredient's `name_cn`, `name_en`, `name_alt` or alias, **use that row**;
  else create a stub: fallback category (`is_fallback`), `needs_detail=True`,
  the typed names. A name typed twice in one save makes one stub (resolve
  against stubs made earlier in the same request as well);
- cycle guard: refuse (422) a sub-recipe line `B` on recipe `A` when `B == A`
  or `A` is reachable from `B` through sub-recipe lines. Walk with a bounded
  loop or a recursive CTE; `MAX_DEPTH` as in `app/services/hierarchy.py`.

**Version rule** (`variant_of_id`), on create and update, 422 each: names no
recipe; names itself; names a recipe that is itself a version; is set on a
recipe that has versions of its own.

**Responses.** `RecipeRef {id, display_name, kind}`. Line response: `id`,
`position`, `section`, `ingredient` (`{id, display_name, needs_detail}` or
null), `sub_recipe` (`RecipeRef` or null), `amount`, `note`, `is_optional`.
Full `RecipeResponse`: every column, `course` (`VocabRef`), `aliases` (sorted
strings), `sources`, `lines`, `steps`, `serves_as`, `labels`, `methods`,
`equipment` (`VocabRef` lists), `images` (`AttachedImage`), `variant_of`
(`RecipeRef`), `versions` (the other recipes in this version family: for a
parent its variants, for a variant its parent's other variants — the parent
itself is `variant_of`), `used_in` (`RecipeRef` list of recipes with a line
naming this one directly; depth zero), `written_up` (has a line or a step;
derived, never stored). Built explicitly as `ingredient._response` is.

**Routes:** `GET /api/recipes/{id}`; `POST /api/edit/recipes` (201);
`PATCH /api/edit/recipes/{id}` (a status-only PATCH is the in-place status
change and needs nothing special); `GET /api/recipes/{id}/cascade` →
`{aliases, sources, lines, steps}` plus `used_in` (count of recipes naming it);
`DELETE /api/edit/recipes/{id}` with those four counts as required query
params → `StaleCountError` on drift; refused 409 **before** the database is
asked when another recipe's line names it, with `used_in: [{id,
display_name}]` on the body. Versions of a deleted recipe survive with
`variant_of_id` null.

**Tests** (`tests/api/test_recipe_crud.py`, `tests/api/test_recipe_lines.py`):
the full round trip; PATCH leaves absent lists alone and replaces sent ones —
including re-sending the same lines and steps unchanged (the position
collision); every 422 above with its mirror; the load-bearing cases from the
spec: a line naming a missing ingredient is 422; a payload claiming a type is
refused and cannot change the stored one; a self-reference and a two-recipe
cycle are refused (mirror: a chain A→B is fine); a stub typed twice in one save
is one row; a typed name matching an existing alias reuses that row; deleting a
recipe used as a sub-recipe is 409 naming it (mirror: unused deletes);
deleting a version's parent leaves the version.

**Docs:** `docs/api.md` gains a Recipes section; `docs/notes/decisions.md`
gains the decisions (versions one level deep and why SET NULL; written-up
derived; stubs reuse an exact-name match; used-in depth zero through
sub-recipes).

## Task 3 — recipe library and galleries

- `GET /api/recipes` — bare array of `RecipeSummary` (`id`, `display_name`,
  name slots, `kind`, `status`, `course` (`VocabRef`), `methods`, `creators`
  (distinct, source order), `time`, `written_up`, `cover`), sorted by display
  name in Python. Filters: `q` (name slots + aliases, the ingredient search's
  subquery shape so a double alias match returns one row), `course_id`,
  `status`, `kind`, `label_id`, `method_id`, `equipment_id`, `creator`
  (exact), `ingredient_id` (Task 4 fills it; accept it now and filter by
  direct lines, Task 4 swaps in the descendant query), `written_up`.
  Multi-valued filters are `list[...] = Query(None)` and mean "any of"; the
  test for "any of" needs two values and three rows. No N+1: `selectinload`
  everything the summary reads.
- `GET /api/recipe-creators` — sorted distinct non-null creators, a bare array
  of strings. Its own small read router.
- `PUT /api/edit/recipes/{id}/images` — as the ingredient gallery, via a shared
  helper rather than a copy (third repetition rule: move `set_images` into
  `app/services/images.py` taking the owner, the relationship name and the
  attachment class, and point the ingredient route at it).
- **The 422 convention** (Rulings): `resolve_attachments`' unknown id → 422;
  update `tests/api/test_images.py` and `docs/api.md`; delete the open item
  "An unknown id inside a request body is 404 in one place and 422 in
  another"; add the decision to `docs/notes/decisions.md`, superseding the
  "neither is a 404" line in "What module 1 hands module 2" (edit that bullet
  — grep the claim, not the file).
- `GET /api/images/{id}` owners now include recipes — one test.

**Docs:** `docs/api.md` (list filters, creators, gallery, 422 rule).

## Task 4 — the ingredient side

- **Used in.** `app/services/recipes.py::recipes_using_ingredient(db, ids)`:
  distinct recipes with a line naming the ingredient **or any descendant**
  (recursive CTE over `ingredient.parent_id`); depth through sub-recipes is
  zero. `GET /api/recipes?ingredient_id=` uses exactly this query.
  `IngredientResponse` gains `used_in: [RecipeRef]`; `IngredientSummary`
  gains `used_in_count` computed for the whole list in a fixed number of
  queries (fetch `(recipe_id, ingredient_id)` pairs and the parent map once).
  Load-bearing test: a recipe using two children of one parent counts once on
  the parent; a recipe whose sub-recipe uses the ingredient does not count.
- **Ingredient delete** refused 409 before the database is asked when lines
  name it, with `used_in: [{id, display_name}]` (mirror: unused deletes).
  The cascade preview gains `recipes` (a blocking count, like `children`).
- **Merge.** `GET /api/ingredients/{id}/merge-preview?into={target}` and
  `POST /api/edit/ingredients/{id}/merge` `{"into": target}` → the target's
  `IngredientResponse`. One service function computes the plan; the preview
  returns it and the merge executes it, so the two cannot disagree (test it:
  preview, merge, compare). The plan: lines, children, links, labels (union),
  images (appended after the target's, skipping ones the target has) move;
  the source's name slots and aliases become target aliases unless the target
  already answers to them (name slots or aliases, casefold); preservation rows
  move unless the target has that `(state, method)` (dropped, listed); heating
  rows move; each prose field moves when the target's is empty and is dropped
  (listed) otherwise; the source is deleted. Refused 422: into itself, into
  one of its descendants, into an id that names nothing. Source missing → 404.
  Preview shape: `{source: IngredientSummary, target: IngredientSummary,
  moves: {lines, children, links, labels, images, heating, preservation},
  new_aliases: [str], dropped_preservation: [{state, method}],
  prose: {field: "moved" | "dropped"}}` (only fields the source has).

**Docs:** `docs/api.md` (used-in, merge, delete refusal), `docs/notes/decisions.md`
(merge rules: target wins).

## Task 5 — finish

`docs/testing.md` (new suites, load-bearing fixtures), `CLAUDE.md` status
(recipes API built), the running-app check over HTTP against `:8001`
(create a recipe with a stub line and a sub-recipe, edit, status change,
delete refusal, merge two ingredients), full suite, PR into `dev`, merge, then
delete this plan.
