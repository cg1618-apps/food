# Module 1 — Ingredients

Working scaffolding. This file is deleted when the work lands; what survives
moves into `docs/data-model.md`, `docs/api.md`, `docs/testing.md` and
`docs/notes/decisions.md` in the same commit that deletes it.

Module 1 of the eight in `docs/notes/decisions.md`. The owner has scoped work to
modules 1 and 2 only until both are far enough along.

## What ships

The ingredient library: the rows, their names and aliases, a category tree, the
notes that make it a reference rather than a list, and the read and write API
and pages over all of it. Plus the app-wide foundations that have nowhere
earlier to live — the write-prefix constant, the error handling, the API client,
logging — because this is the first module with any routes at all.

Not in scope: anything a recipe needs. Stub creation, merge, and "what uses
this" are module 2's, and are named here only where module 1 must not make them
harder.

## Decisions taken

Settled with the owner during design. The reasoning that outlives this file goes
to `docs/notes/decisions.md`.

- **A parent ingredient is an ordinary ingredient.** `parent_id` is a nullable
  self-reference, one level enforced. 醬油 → {生抽, 老抽}. The parent is itself
  stockable, cookable and citable on a recipe line; it is not an abstract
  grouping node. Most rows have a null parent.
- **Plain integer primary key.** Media's `system_id` UUID + `public_id` sequence
  with a deferrable unique constraint exists to let its Google Sheets restore
  permute ids inside one transaction. food has no such channel. One id, and it
  is the one in the URL.
- **Category is a required tree.** Arbitrary depth, cycle-guarded on write. An
  ingredient may point at any node, not only a leaf.
- **`needs_detail` is an explicit boolean, not derived.** Derived from "has no
  notes", salt is permanently unfinished and can never be marked done.
- **No `is_base`.** Considered and removed. "Base" keeps one meaning in this
  app: a general recipe, in module 2.
- **Aliases are a child table, not an array column.** Media has no
  `postgresql.ARRAY` anywhere and records replacing list-in-a-column with a real
  table twice as a regret. `docs/notes/decisions.md` says `aliases[]`; that line
  is corrected when this lands.
- **Three name slots plus aliases.** `name_cn` leads display, then `name_en`,
  then `name_alt`. No per-row display-override column.
- **`name_alt` is a formal name** in another script or romanisation, shown on
  the detail page. **An alias is anything you might type** — unlimited, indexed
  for lookup, never displayed.
- **Preservation is a child table**, one row per way of keeping the thing, with
  an optional typical duration in days. The range ("3–5 天") lives in that row's
  notes; the integer is what a future "what is about to go off" view needs.
- **Labels are free cross-cutting tags**, many per ingredient, in their own
  table so a rename happens once.
- **Sourcing is free text.** A store table is cheap to add later because nothing
  references it — unlike granularity, which is why that one was decided now.

## Schema

```python
class Ingredient(Base):
    __tablename__ = "ingredient"

    id = Column(Integer, primary_key=True)

    name_cn  = Column(String, nullable=True)
    name_en  = Column(String, nullable=True)
    name_alt = Column(String, nullable=True)

    category_id = Column(Integer, ForeignKey("ingredient_category.id",
                                             ondelete="RESTRICT"), nullable=False)
    parent_id   = Column(Integer, ForeignKey("ingredient.id",
                                             ondelete="RESTRICT"), nullable=True)

    description        = Column(Text, nullable=True)   # what it is
    selection_notes    = Column(Text, nullable=True)   # how to pick a good one
    sourcing_notes     = Column(Text, nullable=True)   # where to get it
    preservation_notes = Column(Text, nullable=True)   # advice tied to no method

    needs_detail = Column(Boolean, nullable=False, server_default=text("false"))

    created_at = Column(DateTime, default=get_taipei_now)
    updated_at = Column(DateTime, default=get_taipei_now, onupdate=get_taipei_now)

    __table_args__ = (
        CheckConstraint("num_nonnulls(name_cn, name_en, name_alt) >= 1",
                        name="ck_ingredient_has_a_name"),
        Index("uq_ingredient_name_cn", func.lower(name_cn), unique=True,
              postgresql_nulls_not_distinct=True),
        Index("uq_ingredient_name_en", func.lower(name_en), unique=True,
              postgresql_nulls_not_distinct=True),
    )
```

`name_alt` carries no unique index: it is a catch-all, not a key.

`postgresql_nulls_not_distinct=True` is load-bearing and looks like decoration.
Without it Postgres treats every NULL as distinct, twenty rows with a null
`name_cn` are twenty distinct values, and the constraint never fires. Media
shipped that three times and needed a migration to collapse the duplicates it
had already allowed.

```python
class IngredientCategory(Base):
    __tablename__ = "ingredient_category"

    id          = Column(Integer, primary_key=True)
    parent_id   = Column(Integer, ForeignKey("ingredient_category.id",
                                             ondelete="RESTRICT"), nullable=True)
    name_cn     = Column(String, nullable=True)
    name_en     = Column(String, nullable=True)
    sort_order  = Column(Integer, nullable=False, server_default=text("0"))
    is_fallback = Column(Boolean, nullable=False, server_default=text("false"))

    __table_args__ = (
        UniqueConstraint("parent_id", "name_cn", name="uq_category_sibling_cn",
                         postgresql_nulls_not_distinct=True),
        Index("uq_category_one_fallback", is_fallback,
              unique=True, postgresql_where=is_fallback),
    )


class IngredientAlias(Base):
    __tablename__ = "ingredient_alias"

    id            = Column(Integer, primary_key=True)
    ingredient_id = Column(Integer, ForeignKey("ingredient.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    value         = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("ingredient_id", "value", name="uq_ingredient_alias"),
        Index("ix_ingredient_alias_lookup", func.lower(value)),
    )


class IngredientPreservation(Base):
    __tablename__ = "ingredient_preservation"

    id            = Column(Integer, primary_key=True)
    ingredient_id = Column(Integer, ForeignKey("ingredient.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    method        = Column(String, nullable=False)   # PRESERVATION_METHODS
    duration_days = Column(Integer, nullable=True)
    notes         = Column(Text, nullable=True)
    sort_order    = Column(Integer, nullable=False, server_default=text("0"))


class Label(Base):
    __tablename__ = "label"

    id      = Column(Integer, primary_key=True)
    name_cn = Column(String, nullable=True)
    name_en = Column(String, nullable=True)


class IngredientLabel(Base):
    __tablename__ = "ingredient_label"

    ingredient_id = Column(Integer, ForeignKey("ingredient.id", ondelete="CASCADE"),
                           primary_key=True)
    label_id      = Column(Integer, ForeignKey("label.id", ondelete="CASCADE"),
                           primary_key=True)
```

`CASCADE` on aliases, preservation rows and label links; `RESTRICT` on both
parent references and on `category_id`. That asymmetry is deliberate and is the
kind that reads as uniform: an alias has no life without its ingredient, but a
category with ingredients in it, or an ingredient with children, refuses to be
deleted rather than taking them with it.

`method` is a `String` validated against a Python constant, never a Postgres
`ENUM`. Media has no `sa.Enum` in any revision, and altering a PG enum is a
migration for what should be a one-line edit.

### Category, required, without interrupting

A required category collides head-on with module 2's stub creation: the point of
a stub is that naming an unknown ingredient mid-recipe does not stop you, and a
`NOT NULL` category stops you with a taxonomy question.

The fallback row is the resolution. Exactly one category may set `is_fallback`,
enforced by a partial unique index rather than by everyone remembering. Stubs
land there. Filing them properly joins `needs_detail` as the tidy-up pass, and
"uncategorised" is a query rather than a null check.

Only the fallback row is seeded. The real taxonomy is the owner's to build;
inventing one produces forty rows to delete.

### Category is never inherited

A child ingredient's category is its own column. The form may pre-fill from the
parent; the stored value is the row's own. Inheriting it would mean re-parenting
an ingredient silently re-files it.

## Routes

```
GET    /api/ingredients            list, search, filters
GET    /api/ingredients/{id}
GET    /api/ingredient-categories  the whole tree
GET    /api/labels
POST   /api/edit/ingredients
PATCH  /api/edit/ingredients/{id}
DELETE /api/edit/ingredients/{id}
  ... and the same under /api/edit for categories and labels
```

Reads are public; every mutation sits under `/api/edit`, which Cloudflare Access
gates. There is no auth code in this app and there will be none.

**The prefix has exactly one definition** — `WRITE_PREFIX` in `app/routing.py`.
Every write router derives its prefix from it, the route-enumeration test
asserts against it, and `deploy/gated-paths` is generated from it, one path per
line, LF, **mode 100644** (it is data; nothing execs it, and none of the
executable-bit machinery that guards `deploy/migrations` applies). The platform
reads that file from the commit, and `apps.yml` will carry `gated_paths` checked
against it in both directions.

Search is `ILIKE` across `name_cn`, `name_en`, `name_alt` and the alias lookup
index. A few hundred rows: no trigram, no tsvector, no GIN. The same endpoint is
module 2's typeahead, so it returns the display name, the id and `needs_detail`
from the start.

Small catalogue, so the list returns the whole table as a bare array and sorts
by display name in Python — no envelope, no pagination. A per-row display
fallback cannot be expressed as a single `ORDER BY`.

`201` on create, `204` on delete, applied uniformly. Media's codes are drift —
sibling routers disagree and its DELETE has four different success shapes — and
there is no rule behind them to inherit.

## Errors

Body is `{"detail": "<a sentence>"}`. No error-code taxonomy: one user, no i18n,
and the status already classifies. Nothing ever branches on the prose, so any
message can be reworded without breaking a caller.

**Where a caller needs to act on an error, the error carries data beside the
detail** — not a code. A custom exception plus one handler serialises `detail`
plus extras, so this is a pattern from the first use rather than a hand-built
`JSONResponse` someone escapes the idiom for. `HTTPException` cannot carry the
extra fields; that limitation is what defeated media's one attempt, and the
field it needed was then dropped by its client wrapper anyway.

### Constraint → status, decided once

Every constraint in this module is in front of us now, which is the only moment
this mapping can be decided coherently. A handler mapping everything to a flat
409 is wrong: "that name is taken" and "something still references this" are
different sentences and different situations.

Classified by SQLSTATE, not by constraint name:

| SQLSTATE | Meaning | Status | Because |
| --- | --- | --- | --- |
| `23514` check_violation | `ck_ingredient_has_a_name` | 422 | the payload is malformed |
| `23502` not_null_violation | a missing required column | 422 | the payload is malformed |
| `23505` unique_violation | the name, alias, sibling-category and fallback indexes | 409 | the payload is fine; the world conflicts |
| `23503` foreign_key_violation, on write | `category_id` or `parent_id` names no row | 422 | the payload is malformed |
| `23503` foreign_key_violation, on `DELETE` | something references the row | 409 | the request is fine; the state refuses |

The one `IntegrityError` class splits by cause, and `23503` is the split that
would have been missed — the same error code means a bad reference going in and
a live reference on the way out.

**The handler is a backstop, not the mechanism.** Pydantic mirrors each
constraint so the ordinary path answers 422 before the database is touched. The
backstop exists because media documented exactly that discipline, had no global
handler, and drifted into unhandled 500s for years while ~60 tests asserted
`IntegrityError` at the ORM level and none asserted an HTTP status. So: a test
per row of that table, driven through the HTTP client.

## Frontend

Media's conventions, per the platform's house-style section: react-router,
TanStack Query, Tailwind v4 with the same semantic colour tokens, Context for
what little client state there is, colocated vitest files, `api/client.js` as
the only file that calls `fetch`, `api/endpoints.js` as the single source of URL
truth.

Two fixes to media's client, which has both defects live:

- **`detail` may be an array.** FastAPI's automatic validation error puts
  `[{loc, msg, type}]` there, and `new Error(array)` renders `[object Object]` —
  precisely the case a malformed body produces. Join the `msg` values.
- **Attach the status** to the thrown error. Media throws a bare `Error`
  carrying a string, so callers that need a status re-implement `fetch`, and two
  documented contracts are dead as a result.

### Pages

Naming follows media's tree — `pages/library/`, `pages/detail/`, the forms
alongside.

| Page | Route | Gate |
| --- | --- | --- |
| Ingredient library | `/library/ingredient` | public |
| Ingredient detail | `/ingredient/:id` | public |
| Add an ingredient | `/edit/ingredient/new` | Access |
| Modify an ingredient | `/edit/ingredient/:id` | Access |
| Categories and labels | `/edit/vocabularies` | Access |

Media's detail route is `/<type>/:publicId/:slug?`. The cosmetic slug and the
second id went with the integer-primary-key decision, so ours is `/ingredient/:id`.

**The detail page is the reason this app exists** and is the one read surface
worth designing rather than generating. It is what gets opened on a phone in a
shop, signed out: the selection notes, the preservation methods with their
durations, where to get the thing. Everything else here is a list or sits behind
Access.

**The category tree editor cannot be deferred.** Only the fallback row is
seeded, so without it the first ingredient has exactly one category to choose
and no way to make another. It carries the cycle guard and surfaces the
`RESTRICT` refusals as sentences — "this category still holds 12 ingredients" —
rather than as a failed request. Labels are a second section on that same page
rather than a page of their own: same shape, far less of it.

**The app shell ships here too**, and is invisible until it is missing. The
frontend today is `App.jsx` with a health check: no router, no layout, no
navigation. Module 1 introduces all three, and every later module inherits their
shape.

Two things that are deliberately not pages:

- **The `needs_detail` backlog and the uncategorised pile are filters on the
  library**, not pages. They do need a visible entry point — a count on the
  library page — or the backlog is invisible and stubs accumulate forever.
- **Delete is a dialog.** It shows how many aliases, preservation rows and label
  links go with the row, echoes that count back as a required parameter, and on
  a 409 updates itself in place with the new numbers and re-offers the button.
  Telling the user to reload is what a prose-only error body forces, and is the
  reason the error carries `expected` and `actual` beside the detail.

## Tests

Backend tests take the machine-wide pytest lock. A scratch PostgreSQL, per-test
outer transaction with `join_transaction_mode="create_savepoint"`, full-sentence
test names.

The ones that are load-bearing and look like decoration:

- **`test_every_write_route_sits_under_the_write_prefix`** — enumerates
  `app.routes`, asserts every non-GET route is under `WRITE_PREFIX`.
- **`test_a_write_route_outside_the_prefix_is_caught`** — the mirror. Registers
  a deliberately misplaced write route on a throwaway app and asserts the check
  fails. Without it the first test passes on an empty route table, which is what
  it would do today and would keep doing through the change that breaks it.
- **`test_duplicate_names_are_refused_when_the_other_name_is_null`** — the
  `nulls_not_distinct` guard. Passes trivially if both rows carry every name.
- **`test_a_second_fallback_category_is_refused`**.
- **One test per row of the constraint table**, through the HTTP client.
- **`test_deploy_gated_paths_matches_the_constant`**, and a CI assertion that it
  is `100644` and LF via `git ls-tree HEAD` — beside the existing `100755`
  assertion on `deploy/migrations`, same mechanism, different expected value.

## Docs landing in the same commit

`docs/data-model.md`, `docs/api.md`, `docs/testing.md`, and the corrections to
`docs/notes/decisions.md` (the `aliases[]` line, and the divergences below).

## Divergences from media, to record with reasons

Integer PK; read/write split by path prefix where media splits by comment banner
and an auth dependency; three name slots plus an alias table where media has
four fixed slots; CN-led display with no override column; `XUpdate` +
`exclude_unset` + `extra="forbid"` where media takes a raw dict.

The PATCH one is the only one with real tension, since the house-style section
says copy media's conventions by default. Media's raw-dict helper is
load-bearing there for reasons that do not exist here — association proxies onto
a parent row, and 17 heterogeneous endpoints — and `extra="forbid"` additionally
rejects server-owned columns loudly where theirs drops them silently.
"Conventional beats clever" is the tiebreak.

## Recorded dormant, for when it applies

- **Row-hiding filters belong in SQL, not in Python after the page was cut.**
  food has nothing to hide today. The moment it has a discontinued ingredient or
  an archived recipe, a Python filter after `limit`/`offset` silently shortens
  pages and starts the next one in the wrong place.
- **"Hidden = missing"** — 404 rather than 403, so the status cannot be used to
  enumerate which ids name real rows. No referent today; goes in with the first
  hiding flag.
- **Whatever parameter drives filtering gets no default.** Media's own docs say
  so and its entity routers gave one anyway, producing write responses whose
  counts disagree with the GET of the same object.

## Handed to module 2

- The discriminator on a recipe line resolves **three ways** — ingredient,
  recipe, or neither — and "neither" is a 404. The stored type comes from the
  row, never from the payload; media shipped that corruption three times, and
  there the authz layer was incidentally catching it. Here nothing would.
- **"What uses this ingredient" counts distinct recipes, not lines**, and must
  state its recursion depth. 生抽 in one line and 老抽 in another is one recipe
  using 醬油. A one-level join and a recursive CTE look equally correct in
  review.
- Merge, and stub creation defaulting to the fallback category.
- Whether a bought-and-makeable thing — caramel — is one row or two. Module 1
  adds no link column and assumes nothing.
