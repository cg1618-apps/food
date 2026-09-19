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

## Conventions

- **`201` on create, `204` on delete**, uniformly.
- **List endpoints return a bare array**, not `{items, total}`. No pagination:
  these are small catalogues, and list order is fixed per router rather than a
  query parameter.
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
 "expected": 3, "actual": 4}
```

so the dialog can correct itself in place. Telling the user to reload is what a
prose-only body forces.

**FastAPI's automatic validation error is the exception**: its `detail` is an
*array* of `{loc, msg, type}`. That is a real shape the client must handle —
treating it as a string renders `[object Object]`, which is exactly what a
malformed body produces.

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
| `GET /api/ingredients/{id}/cascade` | what a delete would remove |
| `POST /api/edit/ingredients` | |
| `PATCH /api/edit/ingredients/{id}` | |
| `DELETE /api/edit/ingredients/{id}` | requires the confirmation counts |
| `POST /api/edit/ingredients/{id}/labels/{label_id}` | attach |
| `DELETE /api/edit/ingredients/{id}/labels/{label_id}` | detach |

**`GET /api/ingredients` is also module 2's typeahead.** The library search box
and recipe-line completion ask the same question, and two implementations would
answer differently within a month. Query parameters: `q`, `category_id`,
`label_id`, `parent_id`, `needs_detail`.

`q` matches any of the three name slots or any alias, case-insensitively, as a
substring. The alias arm is a subquery rather than a join, so an ingredient
matching two of its own aliases comes back once.

**`DELETE` takes `aliases` and `preservation` as required query parameters** —
the counts the confirmation dialog showed. If either has moved, the answer is
409 carrying `expected` and `actual`. It is an optimistic check, not a lock:
nothing is held between the count and the delete, and what it guards is a tab
left open rather than a second person.

Children are not in the counts. They are `RESTRICT`, so an ingredient with
children cannot be deleted at all — a refusal, not a number.

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
| `GET /api/labels` | with `ingredient_count` |
| `POST /api/edit/labels` | |
| `PATCH /api/edit/labels/{id}` | |
| `DELETE /api/edit/labels/{id}` | |

**Deleting a label detaches it from every ingredient carrying it**, and that is
intended — removing a tag from the vocabulary means removing it from the things
tagged. No confirmation count: no ingredient is touched, and re-tagging is
typing the label again.

## Health

`GET /health` — 200 only when the database is reachable *and* its Alembic
revision matches the one the running code expects. Declared in the platform's
`apps.yml`; the deploy pipeline reads it from there.
