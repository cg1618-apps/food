# Plan 5 — the one-time ingredient import

Working scaffolding: deleted when branch 5 merges, **together with the spec**
(this is the last branch it describes). Spec:
`docs/superpowers/specs/2026-10-02-recipes-and-ingredients-v2-design.md`,
"One-time ingredient import". Branch `feat/ingredient-import`, cut from `dev`
after branch 4 merged.

## Rulings made before execution

- **The CSV is drafted and owner-approved** (2026-10-02): 194 rows extracted
  from the owner's recipe Google Doc, with the owner's decisions applied —
  step-only ingredients included, 樹薯粉 and 澱粉 as their own rows, 鹼粉 and
  tomato sauce kept as aliases, 海帶 under 乾貨; the rest of the draft trusted
  without a row-by-row review. It is copied into the repository as given; do
  not re-curate it.
- **It lives at `alembic/import/ingredients.csv`, not `data/import/`** as the
  spec says: `.dockerignore` excludes `data/` (and `.gitignore` excludes
  `data/images/`), so a CSV under `data/` would never reach the image the
  migration runs in on the box. Record the deviation in decisions.md.
- Header `name_cn,name_en,aliases,parent,category`; aliases `|`-separated;
  `category` one of the seeded names or empty.

## Task 1 — the data migration

Revision `i3import`, down the current head (check `alembic heads` — it is
`k1notes` unless something landed since), file
`alembic/versions/i3import_ingredient_names.py`, docstring in the house style.

- Reads the CSV with the standard library, path relative to the migration
  file (`Path(__file__).resolve().parents[1] / "import" / "ingredients.csv"`).
- **Validates before writing** and raises on: a parent not in the file, a
  category that is not empty and not a seeded name, two rows sharing a
  `name_cn` or a `name_en` (casefold), an alias equal to a row name or
  repeated. A malformed file must stop the migration, not half-load.
- Inserts with SQL through `op.get_bind()` (no ORM models — a migration must
  not depend on today's models): every row `needs_detail = true`; category by
  name among the seeded categories, empty or not found → the fallback
  (`is_fallback`) category; aliases into `ingredient_alias`.
- **Idempotent and polite**: a row is skipped when its `name_cn` or `name_en`
  (casefold) already equals any ingredient's name slot or alias — so rows the
  owner typed by hand, or a second run, never collide with the unique name
  indexes. Parents are resolved after inserting, by name, against the file's
  rows **and** existing ingredients (a skipped row's existing twin can still be
  a parent); a parent link that would make a cycle or point at itself is
  skipped. Existing rows are never modified.
- **Downgrade is a deliberate no-op** — deleting rows the owner may since have
  edited is worse than leaving them — and the docstring says so.
- Head pins in `tests/test_health.py` and
  `tests/test_migrations_build_the_schema.py` move to `i3import`.

**Tests** (`tests/test_ingredient_import.py`, scratch database like
`tests/test_seed_migration.py`): the CSV itself passes validation (a unit test
calling the migration's validation function on the real file); upgrade loads
every row with `needs_detail`, aliases and parents; a pre-existing ingredient
whose name matches a CSV row is untouched and the CSV row is skipped (the
load-bearing fixture — without it idempotency is vacuous); categories resolve
and an empty category files in the fallback; running the load twice inserts
nothing the second time; downgrade leaves the rows. Validation refusals with
a tiny bad CSV each (missing parent, unknown category, duplicate name) and a
good mirror.

**Docs:** `docs/data-model.md` (where the starting ingredient list came
from), `docs/deployment.md` (`i3import` downgrade is a no-op, deliberately),
`docs/notes/decisions.md`, `docs/testing.md`, `CLAUDE.md` status.

## Task 2 — finish the spec

- Run the import against the local dev database and look at the result in the
  running app (library counts by category, a parent with children, a stub's
  待補 badge).
- **Retire the spec**: move anything still only in it into `docs/`
  (present-tense, as it ended up), then delete it and this plan in the same
  commit. Grep the spec for decisions not yet in `docs/notes/decisions.md`.
- PR into `dev`, CI, merge, tear down.
