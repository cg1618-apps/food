# Plan 3 — kitchen notes

Working scaffolding: deleted when branch 3 merges. Spec:
`docs/superpowers/specs/2026-10-02-recipes-and-ingredients-v2-design.md`
("Kitchen notes", "API"). Branch `feat/kitchen-notes`, cut from `dev` after
branch 2 merged.

## Conventions

As plan 2's: read and copy `app/models/recipe.py`, `app/services/recipes.py`,
`app/routers/recipe.py`, `app/schemas/recipe.py` and the gallery helpers in
`app/services/images.py`. Inputs `extra="forbid"`; an id in the body that
names nothing is 422, a missing row named by the URL is 404. Every refusal
test has its permitted mirror with its set non-empty. Tests run under the
machine-wide lock; `ruff check .` clean; docs land with behaviour; commits by
exact path with no trailers.

## Task 1 — the whole module (one task: it is small)

**Constant** `KITCHEN_NOTE_KINDS = {"compilation": "合輯", "technique": "技巧",
"reference": "參考"}`, appended to `FIXED_VOCABULARIES` as `kitchen_note_kinds`.

**Models**, `app/models/kitchen_note.py`:

- `kitchen_note` — `id`; `title` String NOT NULL with `ck_kitchen_note_has_a_title`
  (`btrim(title) <> ''`); `kind` String NOT NULL server default `'reference'`;
  `url` String null (http/https, validated in the schema); `body` Text null;
  `created_at`, `updated_at`. No name slots: a note is a bookmark, not a
  catalogue entity (spec). Titles are not unique.
- `kitchen_note_label` — `kitchen_note_id` CASCADE, `label_id` CASCADE,
  composite PK.
- `kitchen_note_image` in `app/models/image.py`, the gallery shape
  (`uq_kitchen_note_image_position`, `uq_kitchen_note_image_once`), appended
  to `OWNER_TABLES` as `(KitchenNoteImage, "kitchen_note", KitchenNote)`.
  `owners()` reads `display_name`: give `KitchenNote` a `display_name`
  property returning `title`.

**Migration** `k1notes`, down `r1recipes`; head pins updated; downgrade drops
the tables (lossy, say so in the docstring and in `docs/deployment.md`).

**API** (`app/schemas/kitchen_note.py`, `app/services/kitchen_notes.py`,
`app/routers/kitchen_note.py`, registered in `app/main.py`):

- `GET /api/kitchen-notes` — bare array of summaries (`id`, `title`, `kind`,
  `url`, `labels`, `cover`), newest first. Filters `q` (title and body,
  ILIKE), `kind` and `label_id`, the last two repeatable "any of".
- `GET /api/kitchen-notes/{id}` — every column, `labels`, `images`.
- `POST /api/edit/kitchen-notes` (201), `PATCH /api/edit/kitchen-notes/{id}`
  (`label_ids` replaces when sent), `DELETE /api/edit/kitchen-notes/{id}` (204;
  no echoed counts — nothing a note owns is something the user would miss,
  and the gallery pictures survive, so there is no cascade to confirm; record
  that in decisions), `PUT /api/edit/kitchen-notes/{id}/images` via the shared
  `set_images`.
- `GET /api/images/{id}` owners include kitchen notes (one test).

**Tests** `tests/api/test_kitchen_notes.py`: round trip; blank title 422
(mirror: a title); bad kind 422; `javascript:` URL 422 (mirror: https);
unknown label id 422; "any of" filters with two values and three rows; `q`
matching body; gallery attach, then image delete refused 409 naming the note,
then detach and delete; a model test for each named constraint.

**Docs:** `docs/data-model.md`, `docs/api.md`, `docs/notes/decisions.md`,
`docs/testing.md`, `CLAUDE.md` status.

## Task 2 — finish

Full suite, the running-app check over HTTP, PR into `dev`, merge, delete
this plan.
