# API

Read it when you need to know what a route answers, or what an error means.

## The read/write split is the security boundary

**Everything under `/api/edit` is behind Cloudflare Access. Everything else is
public.** There is no authentication code in this application and there is not
meant to be: one user, no accounts, nothing to log into.

Because Access is all-or-nothing per path, that split has to live in the URL.
A mutation added outside the prefix is publicly writable the moment it deploys,
and nothing in the platform repository would catch it — `bin/check-exposure`
probes the hostname root, which keeps answering correctly while an unprotected
write endpoint sits below it.

`WRITE_PREFIX` in `app/routing.py` is the single definition. Routers derive
their prefixes from it, `deploy/gated-paths` is generated from it, and
`tests/api/test_route_prefixes.py` asserts nothing escapes it.

**Access also gates `/edit`, the edit pages.** That protects no data — the
pages are the same public bundle as every other — but it puts the login in
front of the page someone opens rather than behind their first save. So
`GATED_PATHS`, and therefore `deploy/gated-paths` and `apps.yml`, list both
`/api/edit` and `/edit`.

## Conventions

- **`201` on create, `204` on delete**, uniformly.
- **List endpoints return a bare array**, not `{items, total}`. No pagination:
  these are small catalogues, and list order is fixed per router rather than a
  query parameter. The one exception is `GET /api/images`, which grows with
  every upload and takes `limit` and `offset`.
- **Sorting is by display name, done in Python**, because the display name is
  the first non-empty of three columns and no single `ORDER BY` expresses it.
- **`PATCH` applies only what was sent.** Absent and explicitly null are
  different: `{}` changes nothing, `{"description": null}` clears the note.
- **Unknown fields are refused, not ignored.** `extra="forbid"`, so a payload
  naming `id` or `created_at` is a 422 rather than a silent no-op.

## Errors

Every error body is `{"detail": "<a sentence>"}`. There is no error-code field:
one user, no translations, and the status already classifies the failure.
**Nothing branches on the prose**, so any message can be reworded freely.

**Where a caller must act on an error, the body carries data beside the
detail.** A stale delete answers:

```json
{"detail": "This now removes 4 aliases, not 3. Check and confirm again.",
 "field": "aliases", "expected": 3, "actual": 4}
```

`field` names which count moved, in the delete's query-parameter names. Several
counts can share a value, so a dialog matching `expected` against its own
numbers would correct the wrong one. The dialog corrects itself in place.
Telling the user to reload is what a prose-only body forces.

**FastAPI's automatic validation error is the exception**: its `detail` is an
*array* of `{loc, msg, type}`. That is a real shape the client must handle —
treating it as a string renders `[object Object]`, which is exactly what a
malformed body produces.

### An id in the body that names nothing is 422

**A missing row named by the URL is 404; an id inside the request body that
names no row is 422**, everywhere — a parent, a label, a cooking method, a
course, a recipe's dish, a line's ingredient or dish, a gallery's
`image_id`. The URL resolved; it is the payload that is wrong. The detail
names the id.

### Which status a constraint violation answers

Classified by SQLSTATE, not by constraint name, and decided once with every
constraint in the schema in view.

| SQLSTATE | Meaning | Status |
| --- | --- | --- |
| `23514` | check violation | 422 |
| `23502` | not-null violation | 422 |
| `23505` | unique violation | 409 |
| `23503` | foreign key, on a write | 422 |
| `23503` | foreign key, on a `DELETE` | 409 |
| anything else | the database refused a change | 409 |

`23503` splitting by method is the part that is easy to get wrong: the same
error means "your payload names a row that does not exist" going in, and
"something still references this row" on the way out.

The schema layer mirrors each constraint, so the ordinary path answers before
the database is reached. **The handler is a backstop**, and
`tests/api/test_constraint_statuses.py` drives every row of that table through
HTTP — the layer where the promise lives and where media's equivalent
discipline was never tested.

## Ingredients

| Route | |
| --- | --- |
| `GET /api/ingredients` | list, search and filter |
| `GET /api/ingredients/{id}` | the full row |
| `GET /api/ingredients/{id}/cascade` | what a delete would remove, and what blocks it |
| `GET /api/ingredients/{id}/merge-preview?into={target}` | what a merge would do |
| `POST /api/edit/ingredients` | |
| `PATCH /api/edit/ingredients/{id}` | |
| `DELETE /api/edit/ingredients/{id}` | requires the confirmation counts |
| `POST /api/edit/ingredients/{id}/merge` | merge into another, then delete |
| `PUT /api/edit/ingredients/{id}/images` | replace the gallery, in order |
| `POST /api/edit/ingredients/{id}/labels/{label_id}` | attach |
| `DELETE /api/edit/ingredients/{id}/labels/{label_id}` | detach |

**`GET /api/ingredients` is also module 2's typeahead.** The library search box
and recipe-line completion ask the same question, and two implementations would
answer differently within a month. Query parameters: `q`, `category_id`,
`label_id`, `parent_id`, `needs_detail`, `rating` (one grade), and `has_parent`
(`true` for varieties, `false` for top-level ingredients).

A list row is a summary: names, `category_id`, `parent_id`, `needs_detail`,
`rating`, `cover` (the first gallery image's `thumb_url` and `focus`, or null)
`fridge`, the `{min, max}` of the unused, refrigerated preservation row or
null when there is none, and `used_in_count`.

**"Used in" is distinct recipes with a line naming the ingredient or any
ingredient below it**, at any depth of `parent_id`. A recipe naming both 生抽
and 老抽 counts once on 醬油. Depth through sub-dishes is zero: a recipe using a
sauce whose recipe uses the ingredient is not counted. `used_in_count` on a summary,
`used_in` on the full row and the recipe list's `ingredient_id` filter all read
one query, so they cannot disagree; the list computes every row's count in a
fixed number of queries.

**The full row** adds `aliases`, `preservation`, `heating`, `links`, `labels`,
`images` and `used_in` (recipes as `{id, display_name, dish}`, `dish` being
`{id, display_name, kind}`, sorted by display name). Its `parent` and `children` are summaries, `used_in_count` included,
plus `sourcing_notes` - the page lists varieties with where each is bought;
a list row does not carry it. A preservation entry is `state` (`unused`, `opened`, `cooked`;
default `unused`), `method`, `duration_min_days`, `duration_max_days` and
`notes`. A heating entry is `method` (`{id, display_name}`), `temperature_c`,
`temperature_f` (computed, never sent), `duration`, `preheat`, `flip` and
`notes`; a link is `url` and `title`. An image is `image_id`, `url`,
`thumb_url`, `width`, `height` and `focus`. Heating rows and links come back
with a `sort_order`, but it is not sent: their order is the order of the list,
and a request naming `sort_order` on either is a 422.

**`POST` and `PATCH` take `rating`, `preservation`, `heating` (each entry names
a `method_id`) and `links`.** On `PATCH`, each list that is sent replaces the
stored one and each that is absent is left alone. Aliases and preservation are
*reconciled* rather than rewritten, so re-sending a row the ingredient already
has changes nothing instead of colliding with its own unique key.

Refused with 422: a `rating` outside S to D, an unknown `state` or `method`, a
duration that is not positive, a minimum above the maximum, the same
`(state, method)` twice, a link that is not `http` or `https`, and a heating
entry naming no cooking method. A preservation row with only a maximum is valid.

`q` matches any of the three name slots or any alias, case-insensitively, as a
substring. It is literal text: `%`, `_` and `\` match themselves, not any
character (`app/services/search.py`). The alias arm is a subquery rather than a join, so an ingredient
matching two of its own aliases comes back once.

**`DELETE` takes `aliases`, `preservation`, `heating` and `links` as required
query parameters** — the counts the confirmation dialog showed. If any has
moved, the answer is 409 carrying `field`, `expected` and `actual`. It is an
optimistic check, not a lock: nothing is held between the count and the delete,
and what it guards is a tab left open rather than a second person.

Children are not in the counts. They are `RESTRICT`, so an ingredient with
children cannot be deleted at all — a refusal, not a number. Gallery rows are
not in the counts either: the pictures survive, so nothing is removed that the
user would miss.

**An ingredient a recipe line names is refused with 409 first**, before the
database is asked, with `used_in: [{id, display_name}]` on the body — the
recipes naming it **directly**. A line naming one of its children does not
block it; the child does that on its own. Merging is the way out of a
duplicate that recipes use.

**`GET .../cascade` answers `{aliases, preservation, heating, links, labels,
children, recipes}`.** The first four are echoed back to the delete;
`children` and `recipes` (distinct recipes with a line naming it directly)
block the delete rather than being removed by it.

**Merge.** `POST /api/edit/ingredients/{id}/merge` with
`{"into": target, "fingerprint": "<from the preview>"}` moves everything the source has onto the target, deletes the source, and
answers the target's full row. `GET /api/ingredients/{id}/merge-preview?into=`
answers what it would do, computed by the same function, without writing:

```json
{
  "source": {"...": "summary"},
  "target": {"...": "summary"},
  "moves": {"lines": 2, "children": 1, "links": 1, "labels": 1,
            "images": 1, "heating": 1, "preservation": 1},
  "new_aliases": ["蔥花", "青蔥"],
  "dropped_preservation": [{"state": "unused", "method": "冷藏"}],
  "prose": {"description": "dropped", "selection_notes": "moved"},
  "fingerprint": "3f1c…"
}
```

`fingerprint` is a SHA-256 over every row the merge would move or drop — the
rows themselves, not their counts — and the merge requires it back. The merge
recomputes the plan; if anything it would move or drop has been added,
removed or edited since the preview was read, it answers **409** and changes
nothing:

```json
{"detail": "This merge has changed since the preview. Check it and confirm again.",
 "preview": {"...": "the fresh preview, with its own fingerprint"}}
```

so the dialog can redraw from `preview` and confirm with its fingerprint. A
body with no `fingerprint` is 422.

The target wins every collision:

- recipe lines naming the source, its children, links and heating rows all
  move; links and heating are numbered after the target's own;
- labels are the union — `moves.labels` counts those the target lacked;
- images are appended after the target's gallery, skipping any the target
  already carries;
- the source's name slots and aliases become target **aliases**, never names,
  unless the target already answers to them (a name slot or an alias,
  ignoring case). `new_aliases` is sorted;
- a preservation row moves, numbered after the target's own, unless the
  target has a note for that `(state, method)`, in which case it is dropped
  and listed;
- each prose field the source has (`description`, `selection_notes`,
  `sourcing_notes`, `preservation_notes`) moves when the target's is empty and
  is dropped otherwise; `prose` lists only fields the source has;
- names, category, parent, rating and `needs_detail` are the target's and are
  not touched;
- the source's 常用食材 entry moves to the target in the same place, unless
  the target is listed already, when it is dropped. It is not in the preview
  or the fingerprint: it moves no content;
- every recipe template line naming the source names the target. Not in the
  preview or the fingerprint either: a template is a starting point, not
  content the merge moves.

Refused with 422: into itself, into one of its own descendants, and an `into`
that names nothing. A missing source — the id in the URL — is 404. The body
refuses unknown fields. These are checked before the fingerprint, so a merge
that could never run is a 422 or 404, not a 409.

**`PUT /api/edit/ingredients/{id}/images`** takes a list of
`{"image_id": 12, "focus": "50% 30%"}` and makes it the gallery, in that order;
index 0 is the cover. `[]` clears it. An unknown `image_id` is 422 naming the
id (see "An id in the body that names nothing is 422"), the same image twice
is 422, and a `focus` that is not `"X% Y%"` with each between 0 and
100 is 422. Putting the same list twice in a row succeeds. The answer is the
full ingredient.

## Dishes

A dish (料理) is a dish or a sauce in general - 照燒雞腿排, 照燒醬 - and its
recipes are the specific ways of making it. One table holds both kinds:
`kind` is `dish` (料理) or `sauce` (醬料).

| Route | |
| --- | --- |
| `GET /api/dishes` | list, search and filter |
| `GET /api/dishes/{id}` | the full dish, its recipes and what uses it |
| `GET /api/dishes/{id}/cascade` | what a delete would remove, and what blocks it |
| `POST /api/edit/dishes` | |
| `PATCH /api/edit/dishes/{id}` | |
| `DELETE /api/edit/dishes/{id}` | requires the alias count |
| `PUT /api/edit/dishes/{id}/images` | replace the gallery, in order |

**`GET /api/dishes`** is the library: a bare array of summaries sorted by
display name. A summary is the name slots and `display_name`, `kind`,
`course` and `region` (`{id, display_name}` or null), `labels`
(`{id, display_name}` list), `recipe_count` and `cover`. **`cover` is the
dish's own first picture, else the first cover among its recipes**, in recipe
id order, else null - a dish shows something before it has pictures of its
own.

Query parameters: `q` - any name slot or any alias, case-insensitively, as a
substring, with `%`, `_` and `\` matched literally; `kind`, `course_id`,
`region_id`, `label_id` - each may repeat, meaning **any of** its values,
and different parameters narrow each other.

**The full dish** is the name slots and `display_name`, `kind`, `course`,
`region`, `description`, `aliases` (sorted strings), `serves_as` and `labels`
(`{id, display_name}` lists), `images` (as an ingredient's), `created_at`,
`updated_at`, and:

- `recipes` - the dish's recipes, as the recipe library lists them (the
  recipe summary below), by display name;
- `used_in` - recipes with a line naming this dish **directly**, as
  `{id, display_name, dish}`. What a sauce is used in.

**`POST` takes `name_cn`, `name_en`, `name_alt`, `kind` (default `dish`),
`course_id`, `region_id`, `description`, `aliases`, `serves_as_ids` and
`label_ids`; `PATCH` takes any subset**, each list sent replacing the stored
one and each absent left alone. Names are not unique - two dishes may share
one. Refused with 422: no name left on the merged row, a `kind` outside its
list (null included), the same alias twice, and an id that names nothing
(`course_id`, `region_id`, either id list), the detail naming it. Unknown
fields are refused.

**`GET .../cascade` answers `{aliases, recipes, used_in}`.** `aliases` is what
the delete removes and is echoed back; `recipes` (the dish's own) and
`used_in` (recipes whose lines name it) block the delete.

**`DELETE` takes `aliases` as a required query parameter.** A dish with
recipes, or one a recipe's line names, is refused with 409 first, before the
database is asked:

```json
{"detail": "This dish still has recipes, or recipes use it, so it cannot be removed.",
 "recipes": [{"id": 5, "display_name": "阿基師版"}],
 "used_in": [{"id": 8, "display_name": "照燒雞腿飯"}]}
```

A moved alias count is the 409 with `field`, `expected` and `actual`. Serves-as
and label links and gallery rows go with the dish uncounted; the pictures
stay.

**`PUT /api/edit/dishes/{id}/images`** replaces the gallery exactly as an
ingredient's does, and answers the full dish.

## Recipes

| Route | |
| --- | --- |
| `GET /api/recipes` | list, search and filter |
| `GET /api/recipes/{id}` | the full recipe |
| `GET /api/recipes/{id}/cascade` | what a delete would remove |
| `POST /api/edit/recipes` | |
| `PATCH /api/edit/recipes/{id}` | also the in-place status change |
| `DELETE /api/edit/recipes/{id}` | requires the confirmation counts |
| `PUT /api/edit/recipes/{id}/images` | replace the gallery, in order |

A recipe is one way of making a dish. **Its display name is its own `name`
when it has one, else its dish's display name.** What is true of the dish
whoever cooks it - names, kind, course, region, labels, serves-as, the
description - is the dish's, read through the dish and written on it.

How other rows point at these on the wire:

- `DishRef` - `{id, display_name, kind}`;
- `RecipeRef` - `{id, display_name, dish}`, `dish` a `DishRef`. An
  ingredient's and a dish's `used_in` and a recipe's `other_recipes` are
  lists of these.

**`GET /api/recipes`** is the library: every recipe of every dish, a bare
array of summaries sorted by display name. A summary is `id`, `display_name`,
`name` (its own, or null), `dish` (a `DishRef`), `status`
(`{id, display_name}`), `course` (the dish's, `{id, display_name}` or null),
`methods` (`{id, display_name}` list), `authors` (`{id, display_name}`, the
distinct authors of its sources, in source order, skipping sources with
none), `time`, `written_up` and `cover` (the recipe's own first gallery
image's `thumb_url` and `focus`, or null).

Query parameters:

- `q` - the recipe's own `name`, or any of its dish's name slots or aliases,
  case-insensitively, as a substring, with `%`, `_` and `\` matched
  literally. Each arm is a subquery, so a recipe matching twice comes back
  once;
- `dish_id`, `kind`, `course_id`, `region_id`, `label_id`, `status_id`,
  `method_id`, `equipment_id`, `author_id`, `ingredient_id` - each may repeat,
  and a repeated parameter means **any of** its values
  (`?status_id=2&status_id=3`). Different parameters narrow each other.
  `kind`, `course_id`, `region_id` and `label_id` are the dish's and filter
  through it; `course_id` is the course a dish is filed under, not one it
  serves as; `author_id` matches recipes with a source by that author;
  `ingredient_id` matches recipes using that ingredient as "used in" defines
  it - a line naming it or anything below it, depth zero through sub-dishes;
- `written_up` - `true` for recipes with at least one line or step, `false`
  for the rest.

**`PUT /api/edit/recipes/{id}/images`** replaces the recipe's own gallery
exactly as an ingredient's does, and answers the full recipe.

**The full recipe** is `id`, `display_name`, `name`, `status`, `servings`,
`time`, `storage_notes`, `notes`, `created_at`, `updated_at`, and:

- `dish` - a `DishBrief`: the `DishRef` fields plus `course`, `region`,
  `labels` and `serves_as`, so the page can show what the dish says without
  a second read;
- `sources` - `{id, platform, author, url, title, sort_order}`, `platform`
  being `{id, display_name}` and `author` `{id, display_name}` or null;
- `lines` - the lines in no group, `{id, position, ingredient, sub_dish,
  amount, note, is_optional}`, where exactly one of `ingredient`
  (`{id, display_name, needs_detail}`) and `sub_dish` (a `DishRef`) is set;
- `line_groups` - the recipe's 材料分組, in order, each `{id, position, group,
  name, display_name, lines}`: `group` is the 設定 value (`{id,
  display_name}`) or null, `name` the one-off name or null - exactly one is
  set - `display_name` is whichever it is, and `lines` the group's lines, as
  above. An empty group is listed with `lines: []`;
- `steps` - the steps in no group, `{id, position, kind, body}`: `kind` is
  `step` (an ordinary step), `optional` (one that may be skipped) or `note`
  (a note among the steps);
- `step_groups` - the 步驟分組, `{id, position, group, name, display_name,
  steps}`, as `line_groups`;
- `methods`, `equipment` - `{id, display_name}` lists;
- `images` - as an ingredient's;
- `other_recipes` - 其他版本: the dish's other recipes, as `RecipeRef`s, by
  display name;
- `written_up` - true when it has at least one line or step, grouped or not.
  Derived, never sent.

A line's or step's `position` runs through the whole recipe in the order the
page shows it - the ungrouped rows, then group by group. A group's `position`
is its place among the groups. A step's number is not stored: the page counts
only `step`-kind steps, through every group, so an optional step or a note
takes a place in the order and no number.

**`POST` takes the whole recipe; `PATCH` takes any subset.** The fields are
`dish_id` or `new_dish`, `name`, `status_id`, `servings`, `time`,
`storage_notes`, `notes`, and the lists `sources`, `lines`, `line_groups`,
`steps`, `step_groups`, `method_ids` and `equipment_ids`. The fields that live
on the dish - name slots, `kind`, `course_id`, `serves_as_ids`, `label_ids`,
`aliases`, `description` - and the removed `variant_of_id` are unknown fields
here, and a request naming one is a 422.

**A recipe belongs to exactly one dish.** `POST` sends `dish_id` or
`new_dish` (`{name_cn, name_en, kind}`, at least one name, `kind` `dish` or
`sauce`, default `dish`), never both and never neither. `new_dish` reuses a
dish whose name slot or alias equals a typed name, ignoring case - kind and
all - and otherwise creates one. On `PATCH`, `dish_id` or `new_dish` moves the
recipe to that dish and neither leaves it where it is; an explicit null
`dish_id` is a 422.

When `status_id` is left out on create, the recipe gets the first status in
sort order (the oldest among equals); with no status at all to give, the create
is a 422 saying so. On `PATCH` each list sent replaces the stored list and each
one absent is left alone. Sources, lines, steps and groups take their order
from the list - a request naming `sort_order` or `position` is a 422 - and
re-sending the same lines, steps and groups succeeds.

**Lines and steps are each a pair, replaced together.** `lines` is the
ungrouped lines and `line_groups` the groups with theirs; `steps` and
`step_groups` likewise. A `PATCH` sends both halves of a pair or neither -
one without the other, or either as null, is a 422 - because replacing one
half alone would have to guess what becomes of the rows in the other. A `PATCH` carrying only `status_id` is the status
change; nothing else is needed for it.

A source is `{platform_id, author_id, new_author, url, title}`: `platform_id`
required, at most one of `author_id` and `new_author`, and at least one of an
author, `url` and `title`; `url` must be `http` or `https`. `new_author`
(`{name_cn, name_en}`, at least one) is a name typed into the source that the
save resolves: an author whose `name_cn` or `name_en` equals a typed name,
ignoring case, is reused, and otherwise one is created (with `sort_order` 0,
as every author). Names resolved earlier in the same save count, so one new
name on two sources is one author. A step is `{body, kind}` with a non-blank
`body`; `kind` is one of `step`, `optional` or `note` and defaults to `step`
when left out - any other value, null included, is a 422.

A group is `{line_group_id, name, lines}` (or `{step_group_id, name, steps}`):
exactly one of the 設定 value's id and a one-off `name`, and its rows, which
may be none - an empty group is kept. A `name` equal to a value's `name_cn`
or `name_en`, trimmed and ignoring case, is stored as that value. A recipe may
not hold the same group twice: the same value, a value and its name, or one
one-off name in two cases.

**A line names exactly one of `ingredient_id`, `sub_dish_id`,
`new_ingredient` or `new_dish`**, plus `amount`, `note` and `is_optional`,
wherever it sits - ungrouped or in a group. There is no type field, and a
payload sending one is a 422: the stored kind of line is whichever column is
set. A line names a **dish**, never one recipe of it.

`new_ingredient` (`{name_cn, name_en}`, at least one) reuses an ingredient
whose name slot or alias equals a typed name, ignoring case; otherwise it
creates a stub in the fallback category with `needs_detail` set. `new_dish`
(`{name_cn, name_en, kind}`) reuses a dish the same way and otherwise creates
one - **a `sauce` unless `kind` says otherwise**, where the recipe's own
`new_dish` defaults to `dish`. Names resolved earlier in the same save count,
the recipe's own dish first, so one new name typed into two lines is one row.
A near match is not reused - the typeahead (`GET /api/ingredients?q=`,
`GET /api/dishes?q=`) is where a near match is offered.

Refused with 422, and a refused save writes nothing - not a new dish, not an
author, not a stub an earlier line asked for:

- an explicit null for `status_id`, `dish_id` or a source's `platform_id`; a
  `new_dish` kind outside its list;
- a source sending both `author_id` and `new_author`;
- a group naming both a value and a name, or neither; the same group twice in
  one recipe; on `PATCH`, one half of a lines or steps pair without the other;
- creating a recipe without `status_id` when there is no status at all;
- **an id inside the body that names nothing** - `dish_id`, `status_id`, a
  source's `platform_id` or `author_id`, either id list, a group's
  `line_group_id` or `step_group_id`, `ingredient_id` or `sub_dish_id` in a
  line. The detail names the id. The URL's own recipe missing is 404;
- **a line naming the recipe's own dish** - by `sub_dish_id`, or by a
  `new_dish` that resolves to it (an existing dish of that name, or the same
  new name as the recipe's own `new_dish`);
- **a loop through dishes**: dish A uses dish B when a recipe of A has a line
  naming B, and a line may not name a dish from which the recipe's own dish is
  reachable, at any depth and through any recipe of each dish. The recipe's
  own stored lines are left out of the walk - they are being replaced;
- **moving a recipe to a dish its lines name**, or to one that would close a
  loop through the lines it keeps.

**`GET .../cascade` answers `{sources, lines, steps}`**, what the delete
removes; `lines` and `steps` count every row, grouped or not, and the groups
themselves go too uncounted.

**`DELETE` takes `sources`, `lines` and `steps` as required query
parameters**, and a moved count is the 409 with `field`, `expected` and
`actual` that an ingredient's is. **Nothing refuses deleting a recipe**: a
line names a dish, never a recipe, so no line depends on it. **The dish
stays**, even when this was its last recipe - deleting a dish is its own
decision. Method and equipment links and gallery rows go with the recipe
uncounted; the images themselves stay.

## Recipe templates

| Route | |
| --- | --- |
| `GET /api/recipe-templates` | every template, in order, with counts |
| `GET /api/recipe-templates/{id}` | the body, resolved, and `dropped` |
| `POST /api/edit/recipe-templates` | creates one, at the end; 201 |
| `POST /api/edit/recipe-templates/from-recipe/{recipe_id}` | creates one from that recipe; 201 |
| `PATCH /api/edit/recipe-templates/{id}` | |
| `DELETE /api/edit/recipe-templates/{id}` | 204; nothing refers to a template |
| `PUT /api/edit/recipe-templates/order` | saves the order of every template |

A template is a named skeleton a new recipe starts from: servings, time, the
lines and steps in their groups (steps with their kinds), methods and
equipment. No dish, name, status, sources, notes or pictures.

**The list** is light - `{id, name, sort_order, line_count, step_count}` - in
`sort_order`, ties by name. The counts are of the body as stored, grouped rows
included.

**`GET /api/recipe-templates/{id}`** answers the body in a recipe response's
shapes, so a form reads a template with the code that reads a recipe:

```json
{"id": 11, "name": "基本照燒", "sort_order": 0, "dropped": 1,
 "body": {"servings": "2 人份", "time": null,
          "lines": [{"ingredient": {"id": 1, "display_name": "薑", "needs_detail": false},
                     "sub_dish": null, "amount": "1 片", "note": null, "is_optional": false}],
          "line_groups": [{"group": {"id": 5, "display_name": "主料"}, "name": null,
                           "display_name": "主料", "lines": []}],
          "steps": [{"kind": "step", "body": "煎皮"}],
          "step_groups": [{"group": null, "name": "收尾", "display_name": "收尾",
                           "steps": [{"kind": "note", "body": "別燒焦"}]}],
          "methods": [{"id": 3, "display_name": "煎"}], "equipment": []},
 "created_at": "…", "updated_at": "…"}
```

Lines and steps carry no `id` or `position`: they are not rows. `POST` and
`PATCH` answer this same shape.

**What the body names can be deleted from under it** - nothing in the
database ties a template to an ingredient, a dish, a method, a piece of
equipment or a group value. Reading a template leaves out each reference that
no longer exists and counts it in `dropped`: a line whose ingredient or dish
is gone, a method or a piece of equipment that is gone, and a group whose
材料分組 / 步驟分組 value is gone - whose rows then join the end of the
ungrouped ones, as removing a group in the form does. The stored body is left
alone; the next save writes what the form then holds.

**The `POST` body is `{"name": …, "body": {…}}`**, and `PATCH` sends either
or both. `body` takes the recipe payload's structural fields -
`servings`, `time`, `lines` with `line_groups`, `steps` with `step_groups`,
`method_ids`, `equipment_ids` - each optional, validated by the recipe's own
input models, and replaces the whole body when sent. Refused with 422, each
changing nothing:

- a blank name, or a name another template has, whatever its case;
- a line naming `new_ingredient` or `new_dish` - **a template never creates
  rows**; pick an existing ingredient or dish;
- an id naming nothing - an ingredient, a dish, a method, a piece of
  equipment, a group value;
- a line naming none or several targets, a group naming both or neither of a
  value and a name, or the same group twice;
- a field a template does not carry (`dish_id`, `sources`, `notes` …), and
  `null` for `name` or `body` on a `PATCH`.

A one-off group name that is a 設定 value's name is stored as that value, as
on a recipe.

**`POST /api/edit/recipe-templates/from-recipe/{recipe_id}`** takes `{"name":
…}` and makes a template of that recipe's structure - its lines and steps in
their groups, the steps' kinds, its methods, equipment, servings and time.
A missing recipe is 404; a taken name is 422.

**The order `PUT` body is `{"ids": [11, 12, …]}`** and must hold exactly the
current templates, each once, as TBD's does; the answer is the list.

## Kitchen notes

| Route | |
| --- | --- |
| `GET /api/kitchen-notes` | list, search and filter |
| `GET /api/kitchen-notes/{id}` | the full note |
| `POST /api/edit/kitchen-notes` | |
| `PATCH /api/edit/kitchen-notes/{id}` | |
| `DELETE /api/edit/kitchen-notes/{id}` | no confirmation counts |
| `PUT /api/edit/kitchen-notes/{id}/images` | replace the gallery, in order |

**`GET /api/kitchen-notes`** is a bare array of summaries, **newest first** —
unlike the ingredient, dish and recipe libraries, which sort by name: a note is
found by when it was saved as often as by what it is called. A summary is
`id`, `title`, `kind`, `url`, `labels` (`{id, display_name}` list) and `cover`.

Query parameters:

- `q` — the title or the body, case-insensitively, as a substring, with `%`,
  `_` and `\` matched literally;
- `kind`, `label_id` — each may repeat, meaning **any of** its values; the two
  narrow each other. A note carrying two of the labels comes back once.

**The full note** is `id`, `title`, `kind` (`compilation`, `technique`,
`reference`), `url`, `body`, `labels`, `images` (as an ingredient's),
`created_at` and `updated_at`.

**`POST` takes `title`, `kind`, `url`, `body` and `label_ids`; `PATCH` takes
any subset.** `kind` defaults to `reference`. `label_ids` replaces the labels
when sent and is left alone when absent. A blank `body` or `url` is stored as
null. Refused with 422, and a refused save writes nothing:

- a missing title, or one that is blank once trimmed — on `PATCH` an explicit
  null as well;
- a `kind` outside its list, including an explicit null;
- a `url` that is not `http` or `https`;
- an id in `label_ids` that names nothing; the detail names the id;
- any other field.

**`DELETE` takes no counts and answers 204.** Nothing a note owns is something
the user would miss: its label links and gallery rows go with it, and the
pictures stay in the library.

**`PUT .../images`** replaces the gallery exactly as an ingredient's does, and
answers the full note.

## Vocabularies

Nine managed vocabularies share one shape, so one description covers them:

| Route | |
| --- | --- |
| `GET /api/recipe-courses` | 類別, filing a dish |
| `GET /api/regions` | 地區, where a dish comes from |
| `GET /api/recipe-statuses` | |
| `GET /api/source-platforms` | |
| `GET /api/cooking-methods` | |
| `GET /api/equipment` | |
| `GET /api/authors` | |
| `GET /api/line-groups` | 材料分組 |
| `GET /api/step-groups` | 步驟分組 |
| `POST /api/edit/<same>` | |
| `PATCH /api/edit/<same>/{id}` | |
| `DELETE /api/edit/<same>/{id}` | |

Each value is `id`, `display_name`, `name_cn`, `name_en`, `sort_order` and
`usage_count`, listed by `sort_order` then name. A value needs at least one name
and names are unique case-insensitively per slot. Authors are never
hand-ordered: the recipe form creates them with `sort_order` 0 and 設定 sends
none, so their list is in name order.

**Deleting a value that is in use is a 409 carrying `usage_count`**, answered
before the database is asked; the `RESTRICT` foreign key is the backstop. The
count is the number of `RESTRICT` references: for a course, the dishes filed
in it (a dish that only serves as that course does not count, and its link
goes with the course); for a region, the dishes from it; for a status, the recipes in it; for a source platform,
the sources naming it, so one recipe with two sources from one book counts
twice; for an author, likewise the sources naming them; for a cooking method,
ingredient heating rows plus recipes using it; for equipment, recipes using
it; for a 材料分組 or 步驟分組 value, the recipe groups naming it — one per
recipe, since a recipe holds a group once. A recipe group with a one-off name
counts for no value. Renaming a value renames every recipe group using it.

**`GET /api/vocabularies/fixed`** serves every closed list the interface
renders, as `{value, label}` pairs under `preservation_methods`,
`preservation_states`, `ratings`, `dish_kinds` (料理, 醬料), `kitchen_note_kinds` and
`step_kinds` (步驟, 可省略, 備註),
so no component keeps its own copy. These lists are constants in the code and
are not editable through the API; recipe statuses and source platforms are not
among them — they are managed vocabularies, above.

## Images

| Route | |
| --- | --- |
| `GET /api/images` | the library, newest first |
| `GET /api/images/{id}` | one image and the rows that attach it |
| `POST /api/edit/images` | upload, multipart field `file` |
| `DELETE /api/edit/images/{id}` | |
| `GET /images/{key}` | the file itself |

An image is `id`, `url`, `thumb_url`, `width`, `height`, `byte_size`,
`original_filename`, `uploaded_at` and `attachment_count`; the single-image read
adds `owners`, a list of `{type, id, display_name}` where `type` is
`ingredient`, `dish`, `recipe` or `kitchen_note` (whose `display_name` is its
title).

**`GET /api/images` takes `unused`, `limit` (default 60, at most 200) and
`offset`.** `unused=true` returns only images nothing attaches, `false` only
those something does. The filter runs in SQL before the page is cut, so a page
is never short.

**An upload is re-encoded, never stored as sent.** The filename extension and
`Content-Type` are ignored. Pillow verifies the bytes; the image then has its
EXIF rotation applied, is converted to RGB (transparency flattened onto white),
scaled to at most 2000 px on its long edge and written as JPEG at quality 88,
with a 400 px thumbnail beside it. The re-encode is the security control: it
strips EXIF, GPS included, and anything riding in the file. The rotation is
applied first because the re-encode discards the tag, and a portrait phone
photograph would otherwise land sideways.

The key is the SHA-256 of the normalised bytes, so **uploading the same picture
twice answers 200 with the existing row** where a new one answers 201, and no
second row is made. The files are written again either way, which is how a lost
file comes back.

| Status | Cause |
| --- | --- |
| 413 | over `MAX_IMAGE_UPLOAD_MB` (default 10) |
| 422 | not an image Pillow can read |
| 422 | over 50 megapixels once decoded — a decompression bomb |

**The size cap bounds what is processed, not what is received.** The multipart
body is spooled before the handler runs, so a larger body has already arrived
when the 413 is answered. What bounds who can send one is Cloudflare Access on
`/api/edit`.

**Deleting an attached image is a 409** whose body carries `owners`, and its
files stay. Deleting an unattached one is 204 and removes both files; a file
already missing is not an error.

**`/images/<key>` is public**, like every read. Keys are content hashes, so a
URL never changes meaning and may be cached indefinitely. A key that does not
exist is a 404, not the application shell: the bundle's catch-all refuses
`/images` for the same reason it refuses `/api` and `/health`.

## 常用食材

| Route | |
| --- | --- |
| `GET /api/common-ingredients` | the list, in order |
| `PUT /api/edit/common-ingredients` | replaces the whole list |

The list is the ingredients the recipe form offers as chips:

```json
[{"ingredient": {"id": 3, "display_name": "蒜", "needs_detail": false}, "sort_order": 0},
 {"ingredient": {"id": 8, "display_name": "薑", "needs_detail": true}, "sort_order": 1}]
```

`ingredient` is the shape a recipe line embeds (`IngredientRef`).

**The `PUT` body is `{"ingredient_ids": [3, 8]}`** and the list becomes
exactly that, numbered 0, 1, 2 … in the order sent; `[]` empties it. Adding,
removing and reordering are each this one call. The answer is the list, as
the `GET` gives it. An id that names no ingredient is 422 naming the id, the
same id twice is 422, and an unknown field in the body is 422; each changes
nothing.

Deleting an ingredient takes it off the list (`CASCADE`); merging one moves
its entry to the target (see Ingredients).

## TBD

| Route | |
| --- | --- |
| `GET /api/tbd` | every entry, in order |
| `POST /api/edit/tbd` | creates one entry, at the end; 201 |
| `PATCH /api/edit/tbd/{id}` | |
| `DELETE /api/edit/tbd/{id}` | 204; the entry's links go with it |
| `PUT /api/edit/tbd/order` | saves the order of every entry |

A standalone page of loose notes: an entry is an optional name and any number
of links, related to nothing else in the app. There is no detail route - the
page is read whole.

```json
[{"id": 4, "name": "想試的店", "sort_order": 0,
  "links": [{"id": 9, "url": "https://example.com/shop", "label": "甲店"},
            {"id": 10, "url": "https://icook.tw/recipes/12", "label": null}]},
 {"id": 2, "name": null, "sort_order": 1,
  "links": [{"id": 7, "url": "https://youtu.be/x", "label": null}]}]
```

Entries come in `sort_order`, ties by `id`; links in the order they were sent.

**The `POST` and `PATCH` bodies are `{"name": …, "links": [{"url": …,
"label": …}]}`**, both optional and nothing else accepted. A `PATCH` applies
only what it sends, and `links`, when sent, replaces every link the entry had
(`[]` removes them; `null` is a 422). The answer is the entry, as the `GET`
gives it.

**An entry needs a name or at least one link** - a 422 in the usual shape,
checked against the entry as it would be saved, so `{"links": []}` is fine on
an entry with a name and refused on one without. A blank name or label is
stored as null.

**A link is stored as a web address.** What is typed is trimmed; with no
scheme it is given `https://` (`example.com/x` is stored as
`https://example.com/x`, `localhost:8000` as `https://localhost:8000`). A
blank url, a scheme other than `http` or `https` (`javascript:`, `ftp:`), or
no host is a 422.

**The order `PUT` body is `{"ids": [4, 2, …]}`** and must hold exactly the
current entries, each once; the entries are numbered 0, 1, 2 … in that order
and the answer is the page. A missing, unknown or repeated id is a 422 and
changes nothing - it means the page is out of date, and guessing would drop or
invent a place.

## Categories

| Route | |
| --- | --- |
| `GET /api/ingredient-categories` | the whole tree, nested |
| `POST /api/edit/ingredient-categories` | |
| `PATCH /api/edit/ingredient-categories/{id}` | |
| `DELETE /api/edit/ingredient-categories/{id}` | |

The tree comes back in one response with `ingredient_count` per node, assembled
in Python from two queries. A few dozen rows.

**`is_fallback` cannot be set through the API.** There is exactly one fallback
category, the migration seeds it, and moving it would re-file every stub ever
created. The field is absent from the update schema, so the attempt is never
offered; the partial unique index refuses a second one regardless.

**Deleting the fallback category is refused outright**, because it is reachable
even when empty and every later stub needs somewhere to land.

Category deletes take no confirmation count: both relationships are `RESTRICT`,
so nothing cascades and the answer is a refusal rather than a number.

## Labels

| Route | |
| --- | --- |
| `GET /api/labels` | every label, by name, with its counts |
| `POST /api/edit/labels` | |
| `PATCH /api/edit/labels/{id}` | |
| `DELETE /api/edit/labels/{id}` | |

**A label counts every owner that carries it**: `ingredient_count`,
`dish_count` and `note_count` (kitchen notes), and `usage_count`, their sum —
the name the other vocabularies use for the same question. A library's label
filter shows its owner's count - the dish and recipe libraries both show
`dish_count`, since a recipe's labels are its dish's; the settings page shows
the total.

Labels have no `sort_order`: they are listed by name, case-insensitively.

**Deleting a label detaches it from every ingredient, dish and note carrying
it**, and that is intended — removing a tag from the vocabulary means removing
it from the things tagged. No confirmation count: no owner is touched, and
re-tagging is typing the label again.

## Session

`GET /api/edit/session` — the probe the edit pages use to reach the Access
login. It checks nothing itself: Access answers before the app does, so a
request that arrives has already been let through.

- No query: **204**. A signed-out browser never gets this far — Access answers
  with a redirect to its login, which the frontend reads as "signed out".
- `?next=/edit/...`: **303** to that path. The frontend sends the browser here
  as a top-level navigation when it is signed out; Access takes it through the
  login and back to this URL, and this sends it on to the edit page it left.
- A `next` that is not `/edit` or a path under it — another host, a
  protocol-relative `//`, a backslash, a control character, a public page — is
  **400**. An open redirect on a signed-in path would be a phishing link
  carrying this hostname.

## Health

`GET /health` — 200 only when the database is reachable *and* its Alembic
revision matches the one the running code expects. Declared in the platform's
`apps.yml`; the deploy pipeline reads it from there.
