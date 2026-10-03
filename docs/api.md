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
course, a version's original, a line's ingredient or sub-recipe, a gallery's
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
and 老抽 counts once on 醬油. Depth through sub-recipes is zero: a dish using a
base that uses the ingredient is not counted. `used_in_count` on a summary,
`used_in` on the full row and the recipe list's `ingredient_id` filter all read
one query, so they cannot disagree; the list computes every row's count in a
fixed number of queries.

**The full row** adds `aliases`, `preservation`, `heating`, `links`, `labels`,
`images` and `used_in` (`{id, display_name, kind}` recipes, sorted by display
name). Its `parent` and `children` are summaries, `used_in_count` included,
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
  not touched.

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

## Recipes

| Route | |
| --- | --- |
| `GET /api/recipes` | list, search and filter |
| `GET /api/recipes/{id}` | the full recipe |
| `GET /api/recipes/{id}/cascade` | what a delete would remove, and what blocks it |
| `POST /api/edit/recipes` | |
| `PATCH /api/edit/recipes/{id}` | also the in-place status change |
| `DELETE /api/edit/recipes/{id}` | requires the confirmation counts |
| `PUT /api/edit/recipes/{id}/images` | replace the gallery, in order |

**`GET /api/recipes`** is the library: a bare array of summaries sorted by
display name. A summary is the name slots and `display_name`, `kind`,
`status` (`{id, display_name}`), `course` (`{id, display_name}` or null), `methods`
(`{id, display_name}` list), `authors` (`{id, display_name}`, the distinct
authors of its sources, in source order, skipping sources with none), `time`,
`written_up` and `cover`
(the first gallery image's `thumb_url` and `focus`, or null).

Query parameters:

- `q` — any name slot or any alias, case-insensitively, as a substring, with
  `%`, `_` and `\` matched literally as on the ingredient list. The alias arm is a subquery, so a recipe matching two of its aliases comes back
  once;
- `course_id`, `status_id`, `kind`, `label_id`, `method_id`, `equipment_id`,
  `author_id`, `ingredient_id` — each may repeat, and a repeated parameter means
  **any of** its values (`?status_id=2&status_id=3`). Different
  parameters narrow each other. `course_id` is the course a recipe is filed
  under, not one it serves as; `author_id` matches recipes with a source by
  that author;
  `ingredient_id` matches recipes using that ingredient as "used in" defines
  it — a line naming it or anything below it, depth zero through sub-recipes;
- `written_up` — `true` for recipes with at least one line or step, `false`
  for the rest.

**`PUT /api/edit/recipes/{id}/images`** replaces the gallery exactly as an
ingredient's does, and answers the full recipe.

**The full recipe** is the name slots and `display_name`, `kind` (`dish` or
`base`), `status` (`{id, display_name}`), `course`
(`{id, display_name}` or null), `servings`, `time`, `description`,
`storage_notes`, `notes`, and:

- `aliases` — sorted strings;
- `sources` — `{id, platform, author, url, title, sort_order}`, `platform`
  being `{id, display_name}` and `author` `{id, display_name}` or null;
- `lines` — `{id, position, section, ingredient, sub_recipe, amount, note,
  is_optional}`, where exactly one of `ingredient`
  (`{id, display_name, needs_detail}`) and `sub_recipe`
  (`{id, display_name, kind}`) is set;
- `steps` — `{id, position, section, body}`;
- `serves_as`, `labels`, `methods`, `equipment` — `{id, display_name}` lists;
- `images` — as an ingredient's;
- `variant_of` — the original this is a version of, `{id, display_name,
  kind}` or null;
- `versions` — the other recipes in its version family: an original's
  versions, or a version's siblings (its original is `variant_of`);
- `used_in` — recipes with a line naming this one **directly**. A dish using a
  base that uses this base is not listed;
- `written_up` — true when it has at least one line or step. Derived, never
  sent.

**`POST` takes the whole recipe; `PATCH` takes any subset.** A recipe is
filed under a course by `course_id` and a status by `status_id`. Defaults on
create are `kind: dish` and, when `status_id` is left out, the first status in
sort order (the oldest among equals); with no status at all to give, the create
is a 422 saying so. The lists are `aliases`, `sources`,
`lines`, `steps`, `serves_as_ids`, `label_ids`, `method_ids` and
`equipment_ids`: on `PATCH` each one sent replaces the stored list and each one
absent is left alone. Sources, lines and steps take their order from the list —
a request naming `sort_order` or `position` is a 422 — and re-sending the same
lines and steps succeeds. A `PATCH` carrying only `status_id` is the status
change; nothing else is needed for it.

A source is `{platform_id, author_id, new_author, url, title}`: `platform_id`
required, at most one of `author_id` and `new_author`, and at least one of an
author, `url` and `title`; `url` must be `http` or `https`. `new_author`
(`{name_cn, name_en}`, at least one) is a name typed into the source that the
save resolves: an author whose `name_cn` or `name_en` equals a typed name,
ignoring case, is reused, and otherwise one is created (with `sort_order` 0,
as every author). Names resolved earlier in the same save count, so one new
name on two sources is one author. A step is `{section, body}` with a
non-blank `body`.

**A line names exactly one of `ingredient_id`, `sub_recipe_id` or
`new_ingredient`** (`{name_cn, name_en}`, at least one), plus `section`,
`amount`, `note` and `is_optional`. There is no type field, and a payload
sending one is a 422: the stored kind of line is whichever column is set.

`new_ingredient` reuses an ingredient whose name slot or alias equals a typed
name, ignoring case; otherwise it creates a stub in the fallback category with
`needs_detail` set. Names resolved earlier in the same save count, so one new
name typed into two lines is one stub. A near match is not reused — the
typeahead (`GET /api/ingredients?q=`) is where a near match is offered.

Refused with 422, and a refused save writes nothing — not even a stub an
earlier line asked for:

- a `kind` outside its list, and an explicit null for `kind`, `status_id` or a
  source's `platform_id`;
- a source sending both `author_id` and `new_author`;
- creating a recipe without `status_id` when there is no status at all;
- no name left on the merged row;
- **an id inside the body that names nothing** — `course_id`, `status_id`,
  `variant_of_id`, a source's `platform_id` or `author_id`, any of the four id lists, `ingredient_id` or `sub_recipe_id` in a line. The
  detail names the id. The URL's own recipe missing is 404;
- a line whose recipe is reachable from its `sub_recipe_id` through sub-recipe
  lines, at any depth — itself included;
- **the version rule**: `variant_of_id` naming the recipe itself, naming a
  recipe that is itself a version, or set on a recipe that has versions of its
  own. Versions are one level deep.

**`GET .../cascade` answers `{aliases, sources, lines, steps, used_in}`.** The
first four are what the delete removes and are echoed back; `used_in` is a
count of the recipes naming this one, and blocks the delete rather than being
removed by it.

**`DELETE` takes `aliases`, `sources`, `lines` and `steps` as required query
parameters**, and a moved count is the 409 with `field`, `expected` and
`actual` that an ingredient's is. A recipe another recipe's line names is
refused with 409 first, before the database is asked, with
`used_in: [{id, display_name}]` on the body. Its versions survive with
`variant_of` null. Label, method, equipment and serves-as links and gallery
rows go with it uncounted; the images themselves stay.

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
unlike the ingredient and recipe libraries, which sort by name: a note is
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

Six managed vocabularies share one shape, so one description covers them:

| Route | |
| --- | --- |
| `GET /api/recipe-courses` | |
| `GET /api/recipe-statuses` | |
| `GET /api/source-platforms` | |
| `GET /api/cooking-methods` | |
| `GET /api/equipment` | |
| `GET /api/authors` | |
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
count is the number of `RESTRICT` references: for a course, the recipes filed
in it (a recipe that only serves as that course does not count, and its link
goes with the course); for a status, the recipes in it; for a source platform,
the sources naming it, so one recipe with two sources from one book counts
twice; for an author, likewise the sources naming them; for a cooking method,
ingredient heating rows plus recipes using it; for equipment, recipes using
it.

**`GET /api/vocabularies/fixed`** serves every closed list the interface
renders, as `{value, label}` pairs under `preservation_methods`,
`preservation_states`, `ratings`, `recipe_kinds` and `kitchen_note_kinds`,
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
`ingredient`, `recipe` or `kitchen_note` (whose `display_name` is its title).

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
`recipe_count` and `note_count` (kitchen notes), and `usage_count`, their sum —
the name the other vocabularies use for the same question. A library's label
filter shows its own owner's count; the settings page shows the total.

Labels have no `sort_order`: they are listed by name, case-insensitively.

**Deleting a label detaches it from every ingredient, recipe and note carrying
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
