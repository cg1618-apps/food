# Plan 1 — Ingredient storage and heating, vocabularies, images backend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land branch 1 of five: the ingredient schema changes the reference sheets need, the three managed vocabularies with seeds, the image library backend with ingredient galleries, and HTTP CRUD tests for everything module 1 already has.

**Architecture:** Three hand-written Alembic revisions on top of `i1ngredients` (`v1ocabulary` → `i2storage` → `m1images`), each with its models, schemas, service and router in the module-1 shape: one router file per resource exposing a public `router` and a gated `edit`, inputs `extra="forbid"`, errors `{"detail": ...}`. Images follow media's upload pipeline (Pillow verify, re-encode to JPEG, content-hash name) but attach through a real join table.

**Tech Stack:** FastAPI 0.115, SQLAlchemy 2.0, Alembic 1.14, PostgreSQL 17, Pydantic 2, Pillow, python-multipart, pytest; React 19 + Vite (two small compatibility edits only).

**Spec:** `docs/superpowers/specs/2026-10-02-recipes-and-ingredients-v2-design.md`. Read its "Data model", "Images", "API" and "Testing" sections before starting. Plans 2–5 (recipes, kitchen notes, UI, import) are written when this one has merged.

## Global Constraints

- Branch: `feat/ingredient-storage-heating-images`, cut from an up-to-date `dev`. Never commit to `dev` or `main`.
- Commit messages carry **no** AI trailers (`Co-Authored-By`, `Generated with`, links). Stage named files only, then `git commit -- <paths>`; never `git add -A`, never a directory pathspec.
- Every backend test run takes the machine-wide lock (all four apps share one PostgreSQL). From the repo root, in Git Bash:
  ```bash
  LOCK=/c/Users/$USERNAME/AppData/Local/Temp/anime_site_pytest.lock
  until mkdir "$LOCK" 2>/dev/null; do sleep 10; done
  venv/Scripts/python.exe -m pytest -q <ARGS>; rc=$?; rmdir "$LOCK"; exit $rc
  ```
  If the lock is held, run the command in the background rather than looping in the foreground. A lock directory older than 25 minutes is stale: remove it and say so.
- Lint before each commit: `venv/Scripts/ruff.exe check .`
- Migrations are hand-written, import **nothing** from `app.models`, and spell partial or expression indexes with `sa.text`. Revision ids: `v1ocabulary`, `i2storage`, `m1images`, each revising the one before (`v1ocabulary` revises `i1ngredients`).
- Each new head must be pinned in exactly three places: `tests/test_health.py` (two asserts), and `tests/test_migrations_build_the_schema.py` (`stamped ==` and the `heads` assert).
- Closed vocabularies are `String` columns validated against `app/constants.py`; no Postgres enums.
- Every relationship across a `RESTRICT` foreign key sets `passive_deletes="all"`.
- Every new named constraint gets a sentence in `CONSTRAINT_MESSAGES` (`app/errors.py`).
- Every refusal test has a paired permitted-case test, and its set is made non-empty (platform `CLAUDE.md`, "Rule").
- Test names are full sentences, `test_<what is asserted>`.
- `IMAGE_DIR` is read from `app.config.settings` **at call time**, never bound at import time.
- Upload limit: `MAX_IMAGE_UPLOAD_MB` default 10 → 413. Re-encode: long edge ≤ 2000 px, JPEG quality 88, thumbnail long edge 400 px. Storage keys: `library/<sha256>.jpg`, `library/thumbs/<sha256>.jpg`. Served at `/images/<key>`.
- Focus is `"X% Y%"` with 0 ≤ X, Y ≤ 100, or null.
- Docs land in the same commit as the behaviour they describe.

## Review Focus

1. **A phone photo taken in portrait** carries its rotation in EXIF. Since the re-encode strips EXIF, the image must be rotated *first* (`ImageOps.exif_transpose`), or every portrait dish photo lands sideways. Test in Task 4.
2. **A decompression bomb**: a small PNG declaring 30000×30000 pixels must be a 422, not a worker eating gigabytes. Set `Image.MAX_IMAGE_PIXELS` and catch `DecompressionBombError`/`DecompressionBombWarning`. Test in Task 4.
3. **Seed migration on a database where the owner already typed 肉類 or 飯** must not fail on a unique index. Seeds use `ON CONFLICT DO NOTHING`. Test in Task 1 (migration test with a pre-existing row).
4. **A preservation row with only a maximum** ("up to 3 days") is valid; **min > max** is a 422, not a 500. Tests in Task 2.
5. **Uploading the same photo twice** returns the existing row with 200 and writes no second file; **deleting an image still attached** is a 409 naming the owner, and its file survives. Tests in Task 4.

---

## File structure

| File | Responsibility |
| --- | --- |
| `app/constants.py` (modify) | add `PRESERVATION_STATES`, `RATINGS`, `FIXED_VOCABULARIES` |
| `app/models/vocabulary.py` (create) | `RecipeCourse`, `CookingMethod`, `Equipment` via one mixin |
| `app/models/ingredient.py` (modify) | `rating`; preservation `state` and range; `IngredientHeating`, `IngredientLink` |
| `app/models/image.py` (create) | `Image`, `IngredientImage` |
| `app/models/__init__.py` (modify) | import every new model |
| `alembic/versions/v1ocabulary_managed_vocabularies.py` (create) | vocab tables + all seeds |
| `alembic/versions/i2storage_storage_heating_links.py` (create) | ingredient changes |
| `alembic/versions/m1images_image_library.py` (create) | image tables |
| `app/schemas/vocabulary.py` (create) | vocabulary in/out shapes, `VocabRef` |
| `app/schemas/ingredient.py` (modify) | preservation range and state, heating, links, rating, images |
| `app/schemas/image.py` (create) | image summary, attachment in/out, focus validation |
| `app/services/vocabularies.py` (create) | usage counters per vocabulary |
| `app/services/ingredients.py` (modify) | apply heating, links, images; new filters |
| `app/services/images.py` (create) | read upload, normalise, store, delete files |
| `app/routers/vocabulary.py` (create) | one factory → three router pairs, plus `/api/vocabularies/fixed` |
| `app/routers/image.py` (create) | upload, list, detail, delete |
| `app/routers/ingredient.py` (modify) | response fields, delete counts, `PUT .../images` |
| `app/main.py` (modify) | include routers, mount `/images`, catch-all guard |
| `app/config.py` (modify) | `image_dir`, `max_image_upload_mb` |
| `app/errors.py` (modify) | messages for new constraints |
| `requirements.txt` (modify) | `Pillow`, `python-multipart` |
| `docker-compose.prod.yml`, `.gitignore`, `.dockerignore` (modify) | bind mount; ignore `data/images/` |
| `frontend/vite.config.js` (modify) | proxy `/images` |
| `frontend/src/pages/edit/IngredientForm.jsx`, `frontend/src/pages/detail/Ingredient.jsx`, `frontend/src/pages/edit/DeleteIngredientDialog.jsx` (modify) | keep the existing UI working against the changed API until plan 4 replaces it |
| `tests/api/test_vocabularies.py`, `tests/api/test_ingredient_storage.py`, `tests/api/test_images.py`, `tests/api/test_ingredient_crud.py`, `tests/api/test_category_crud.py`, `tests/api/test_label_crud.py`, `tests/test_seed_migration.py` (create) | tests |
| `docs/data-model.md`, `docs/api.md`, `docs/testing.md`, `docs/notes/decisions.md`, `docs/deployment.md`, `docs/open-items.md` (create), `CLAUDE.md` (modify) | docs |

---

### Task 1: Managed vocabularies — courses, cooking methods, equipment — with seeds

**Files:**
- Create: `app/models/vocabulary.py`, `app/schemas/vocabulary.py`, `app/services/vocabularies.py`, `app/routers/vocabulary.py`, `alembic/versions/v1ocabulary_managed_vocabularies.py`, `tests/api/test_vocabularies.py`, `tests/test_seed_migration.py`
- Modify: `app/models/__init__.py`, `app/schemas/__init__.py`, `app/main.py`, `app/errors.py`, `tests/test_health.py`, `tests/test_migrations_build_the_schema.py`

**Interfaces:**
- Produces: models `RecipeCourse`, `CookingMethod`, `Equipment` (columns `id`, `name_cn`, `name_en`, `sort_order`; `display_name` from `NameFallbackMixin`).
- Produces: `app.schemas.VocabRef(id: int, display_name: str)`, `VocabularyCreate`, `VocabularyUpdate`, `VocabularyResponse(id, display_name, name_cn, name_en, sort_order, usage_count)`.
- Produces: `app.services.vocabularies.USAGE: dict[type, Callable[[Session], dict[int, int]]]`. Plan 2 adds recipe counts to it.
- Produces: routes `GET /api/{recipe-courses|cooking-methods|equipment}`, `POST /api/edit/<same>`, `PATCH/DELETE /api/edit/<same>/{id}`.

- [ ] **Step 1: Cut the branch**

```bash
git reflog -5 && git worktree list && git status --short
git checkout dev && git pull origin dev && git checkout -b feat/ingredient-storage-heating-images
```

If the reflog shows `HEAD` moves you did not make, or `git status` shows files you do not recognise, stop and take a worktree instead (platform `CLAUDE.md`, "Git Branches").

- [ ] **Step 2: Write the failing API tests**

`tests/api/test_vocabularies.py`:

```python
"""The three managed vocabularies share one router factory, so one parametrised
suite covers all three. The fixtures that make refusals bite are the in-use
rows: a vocabulary value nothing uses deletes freely, and that is the mirror."""

import pytest

RESOURCES = ["recipe-courses", "cooking-methods", "equipment"]


@pytest.mark.parametrize("resource", RESOURCES)
def test_a_vocabulary_value_can_be_created_listed_renamed_and_deleted(client, resource):
    created = client.post(f"/api/edit/{resource}", json={"name_cn": "測試", "sort_order": 5})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["display_name"] == "測試"
    assert body["usage_count"] == 0

    listed = client.get(f"/api/{resource}").json()
    assert [row["name_cn"] for row in listed] == ["測試"]

    renamed = client.patch(
        f"/api/edit/{resource}/{body['id']}", json={"name_cn": "改名", "name_en": "renamed"}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["display_name"] == "改名"

    deleted = client.delete(f"/api/edit/{resource}/{body['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/{resource}").json() == []


@pytest.mark.parametrize("resource", RESOURCES)
def test_a_vocabulary_value_needs_a_name(client, resource):
    assert client.post(f"/api/edit/{resource}", json={"name_cn": "  "}).status_code == 422


@pytest.mark.parametrize("resource", RESOURCES)
def test_two_values_may_not_share_an_english_name_case_insensitively(client, resource):
    assert client.post(f"/api/edit/{resource}", json={"name_en": "Pan"}).status_code == 201
    assert client.post(f"/api/edit/{resource}", json={"name_en": "pan"}).status_code == 409


@pytest.mark.parametrize("resource", RESOURCES)
def test_any_number_of_values_may_leave_the_english_name_empty(client, resource):
    assert client.post(f"/api/edit/{resource}", json={"name_cn": "甲"}).status_code == 201
    assert client.post(f"/api/edit/{resource}", json={"name_cn": "乙"}).status_code == 201


@pytest.mark.parametrize("resource", RESOURCES)
def test_renaming_away_every_name_is_refused(client, resource):
    row = client.post(f"/api/edit/{resource}", json={"name_cn": "甲"}).json()
    response = client.patch(f"/api/edit/{resource}/{row['id']}", json={"name_cn": None})
    assert response.status_code == 422


@pytest.mark.parametrize("resource", RESOURCES)
def test_an_unknown_id_is_404(client, resource):
    assert client.patch(f"/api/edit/{resource}/999999", json={"name_cn": "x"}).status_code == 404
    assert client.delete(f"/api/edit/{resource}/999999").status_code == 404


def test_values_list_in_sort_order_then_name(client):
    client.post("/api/edit/equipment", json={"name_cn": "乙", "sort_order": 1})
    client.post("/api/edit/equipment", json={"name_cn": "甲", "sort_order": 2})
    client.post("/api/edit/equipment", json={"name_cn": "丙", "sort_order": 1})
    names = [row["name_cn"] for row in client.get("/api/equipment").json()]
    assert names == ["丙", "乙", "甲"]
```

(`"丙" < "乙"` by casefold code point; the assertion pins sort-then-name, whatever the code points are. If it fails only on the tie order, the tie must be broken by `display_name.casefold()` — fix the code, not the test.)

- [ ] **Step 3: Run them and watch them fail**

Run (with the lock): `venv/Scripts/python.exe -m pytest -q tests/api/test_vocabularies.py`
Expected: FAIL — 404s, because the routes do not exist.

- [ ] **Step 4: The models**

`app/models/vocabulary.py`:

```python
"""Small managed vocabularies: recipe courses, cooking methods, equipment.

Three tables with one shape, declared once through a mixin. They are tables
rather than lists in `app/constants.py` because the owner edits them - renaming
煮 to 水煮 must be one row, not a deploy. The closed lists in constants are the
ones the app's own logic branches on (storage state, recipe status); these are
the ones it only displays and filters by.

`declared_attr` builds each table's constraints from its own name and its own
copied columns: `cls.name_cn` inside it is the subclass's column, not the
mixin's, which is what lets one definition produce three correctly-bound
expression indexes.
"""

from sqlalchemy import CheckConstraint, Column, Index, Integer, String, func, text
from sqlalchemy.orm import declared_attr

from app.database import Base
from app.models.base import NameFallbackMixin


class VocabularyMixin(NameFallbackMixin):
    id = Column(Integer, primary_key=True)
    name_cn = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default=text("0"))

    @declared_attr.directive
    def __table_args__(cls):
        table = cls.__tablename__
        return (
            CheckConstraint(
                "num_nonnulls(name_cn, name_en) >= 1", name=f"ck_{table}_has_a_name"
            ),
            # Default NULLS DISTINCT, deliberately - the long note in
            # app/models/ingredient.py applies unchanged.
            Index(f"uq_{table}_name_cn", func.lower(cls.name_cn), unique=True),
            Index(f"uq_{table}_name_en", func.lower(cls.name_en), unique=True),
        )


class RecipeCourse(Base, VocabularyMixin):
    """主食, 配菜, 湯 … - where a dish sits in a meal."""

    __tablename__ = "recipe_course"


class CookingMethod(Base, VocabularyMixin):
    """煮, 煎, 氣炸 … - shared by recipes and the ingredient heating guide."""

    __tablename__ = "cooking_method"


class Equipment(Base, VocabularyMixin):
    """鍋子, 平底鍋, 氣炸鍋 …"""

    __tablename__ = "equipment"
```

Add to `app/models/__init__.py` (import and `__all__`): `CookingMethod`, `Equipment`, `RecipeCourse` from `app.models.vocabulary`.

- [ ] **Step 5: The schemas**

`app/schemas/vocabulary.py`:

```python
"""Shapes shared by the three managed vocabularies."""

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class VocabRef(BaseModel):
    """How another row points at a vocabulary value on the wire."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str = ""


class VocabularyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None
    sort_order: int = 0

    @field_validator("name_cn", "name_en", mode="before")
    @classmethod
    def normalise_names(cls, value):
        return _blank_to_none(value)

    @model_validator(mode="after")
    def at_least_one_name(self):
        if not any((self.name_cn, self.name_en)):
            raise ValueError("A value needs at least one name")
        return self


class VocabularyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None
    sort_order: int | None = None

    @field_validator("name_cn", "name_en", mode="before")
    @classmethod
    def normalise_names(cls, value):
        return _blank_to_none(value)


class VocabularyResponse(BaseModel):
    id: int
    display_name: str = ""
    name_cn: str | None = None
    name_en: str | None = None
    sort_order: int
    usage_count: int
```

Re-export all four from `app/schemas/__init__.py` (import and `__all__`).

- [ ] **Step 6: Usage counters**

`app/services/vocabularies.py`:

```python
"""How many rows use each vocabulary value - for the settings page and for the
409 a delete answers while a value is in use.

One function per vocabulary, registered in USAGE. Plan 2 adds the recipe link
tables to these counters; a vocabulary with no counter yet reports zero rather
than being special-cased by its router.
"""

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.models import CookingMethod, Equipment, RecipeCourse


def _nothing_yet(db: Session) -> dict[int, int]:
    return {}


USAGE: dict[type, Callable[[Session], dict[int, int]]] = {
    RecipeCourse: _nothing_yet,
    CookingMethod: _nothing_yet,
    Equipment: _nothing_yet,
}


def usage(db: Session, model) -> dict[int, int]:
    return USAGE[model](db)
```

Task 2 replaces `CookingMethod`'s counter with a count of heating rows.

- [ ] **Step 7: The router factory**

`app/routers/vocabulary.py`:

```python
"""One factory, three vocabularies. Reads are public; writes sit behind Access.

A delete of a value still in use is refused here with a 409 that carries the
count, before the database is asked. The RESTRICT foreign keys are the
backstop, and through the IntegrityError handler they would only be able to
say "something still refers to this".
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.errors import AppError
from app.models import CookingMethod, Equipment, RecipeCourse
from app.routing import read_router, write_router
from app.services import vocabularies


def _response(row, counts: dict[int, int]) -> schemas.VocabularyResponse:
    return schemas.VocabularyResponse(
        id=row.id,
        display_name=row.display_name,
        name_cn=row.name_cn,
        name_en=row.name_en,
        sort_order=row.sort_order,
        usage_count=counts.get(row.id, 0),
    )


def build(model, resource: str, tag: str, noun: str) -> tuple[APIRouter, APIRouter]:
    router = read_router(resource, tag)
    edit = write_router(resource, tag)

    def _get(db: Session, row_id: int):
        row = db.query(model).filter(model.id == row_id).one_or_none()
        if row is None:
            raise AppError(404, f"No such {noun}.")
        return row

    @router.get("", response_model=list[schemas.VocabularyResponse])
    def list_values(db: Session = Depends(get_db)):
        counts = vocabularies.usage(db, model)
        rows = db.query(model).all()
        rows.sort(key=lambda r: (r.sort_order, r.display_name.casefold()))
        return [_response(row, counts) for row in rows]

    @edit.post("", response_model=schemas.VocabularyResponse, status_code=201)
    def create_value(payload: schemas.VocabularyCreate, db: Session = Depends(get_db)):
        row = model(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return _response(row, {})

    @edit.patch("/{row_id}", response_model=schemas.VocabularyResponse)
    def update_value(
        row_id: int, payload: schemas.VocabularyUpdate, db: Session = Depends(get_db)
    ):
        row = _get(db, row_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        if not any((row.name_cn, row.name_en)):
            raise AppError(422, f"A {noun} needs at least one name.")
        db.commit()
        db.refresh(row)
        return _response(row, vocabularies.usage(db, model))

    @edit.delete("/{row_id}", status_code=204)
    def delete_value(row_id: int, db: Session = Depends(get_db)):
        row = _get(db, row_id)
        in_use = vocabularies.usage(db, model).get(row.id, 0)
        if in_use:
            raise AppError(
                409,
                f"{row.display_name} is still used in {in_use} place(s); "
                "change those first.",
                usage_count=in_use,
            )
        db.delete(row)
        db.commit()
        return Response(status_code=204)

    return router, edit


course_router, course_edit = build(RecipeCourse, "recipe-courses", "Recipe courses", "course")
method_router, method_edit = build(
    CookingMethod, "cooking-methods", "Cooking methods", "cooking method"
)
equipment_router, equipment_edit = build(Equipment, "equipment", "Equipment", "piece of equipment")

ROUTERS = [
    course_router,
    course_edit,
    method_router,
    method_edit,
    equipment_router,
    equipment_edit,
]
```

In `app/main.py`, import `vocabulary` from `app.routers` and, after the label routers:

```python
    for vocabulary_router in vocabulary.ROUTERS:
        app.include_router(vocabulary_router)
```

In `app/errors.py`, add to `CONSTRAINT_MESSAGES`, for each table `t` in `recipe_course`, `cooking_method` and `equipment`:

```python
    "ck_recipe_course_has_a_name": "A course needs at least one name.",
    "uq_recipe_course_name_cn": "Another course already has that Chinese name.",
    "uq_recipe_course_name_en": "Another course already has that English name.",
    "ck_cooking_method_has_a_name": "A cooking method needs at least one name.",
    "uq_cooking_method_name_cn": "Another cooking method already has that Chinese name.",
    "uq_cooking_method_name_en": "Another cooking method already has that English name.",
    "ck_equipment_has_a_name": "A piece of equipment needs at least one name.",
    "uq_equipment_name_cn": "Another piece of equipment already has that Chinese name.",
    "uq_equipment_name_en": "Another piece of equipment already has that English name.",
```

- [ ] **Step 8: Run the API tests**

Run (with the lock): `venv/Scripts/python.exe -m pytest -q tests/api/test_vocabularies.py tests/api/test_route_prefixes.py`
Expected: PASS.

- [ ] **Step 9: Write the failing migration and seed tests**

`tests/test_seed_migration.py`:

```python
"""The vocabulary migration seeds rows, and seeding must survive a database
where the owner already typed one of them by hand. The pre-existing row is the
fixture that makes this bite: on an empty database every INSERT succeeds and
the ON CONFLICT clause is never consulted."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.config import settings

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = "food_seed_test"


def _url(database: str) -> str:
    return settings.sqlalchemy_database_url.rsplit("/", 1)[0] + f"/{database}"


def _alembic(*args: str) -> None:
    env = dict(os.environ, DATABASE_URL=_url(SCRATCH))
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def scratch():
    admin = create_engine(_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {SCRATCH}"))
    engine = create_engine(_url(SCRATCH))
    yield engine
    engine.dispose()
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH} WITH (FORCE)"))
    admin.dispose()


def test_the_seeds_land_on_an_empty_database(scratch):
    _alembic("upgrade", "v1ocabulary")
    with scratch.connect() as conn:
        courses = conn.execute(text("SELECT name_cn FROM recipe_course")).scalars().all()
        methods = conn.execute(text("SELECT count(*) FROM cooking_method")).scalar()
        categories = conn.execute(
            text("SELECT name_cn FROM ingredient_category WHERE NOT is_fallback")
        ).scalars().all()
        labels = conn.execute(text("SELECT name_cn FROM label")).scalars().all()
    assert "主食" in courses and len(courses) == 7
    assert methods == 12
    assert "肉類" in categories
    assert "飯" in labels


def test_seeding_skips_a_value_the_owner_already_created(scratch):
    _alembic("upgrade", "i1ngredients")
    with scratch.begin() as conn:
        conn.execute(text("INSERT INTO label (name_cn) VALUES ('飯')"))
        conn.execute(
            text("INSERT INTO ingredient_category (name_cn, sort_order) VALUES ('肉類', 3)")
        )
    _alembic("upgrade", "v1ocabulary")
    with scratch.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM label WHERE name_cn = '飯'")).scalar() == 1
        assert (
            conn.execute(
                text("SELECT sort_order FROM ingredient_category WHERE name_cn = '肉類'")
            ).scalar()
            == 3
        )


def test_downgrade_keeps_a_seeded_category_that_is_in_use(scratch):
    _alembic("upgrade", "v1ocabulary")
    with scratch.begin() as conn:
        meat = conn.execute(
            text("SELECT id FROM ingredient_category WHERE name_cn = '肉類'")
        ).scalar()
        conn.execute(
            text("INSERT INTO ingredient (name_cn, category_id) VALUES ('雞腿', :c)"), {"c": meat}
        )
    _alembic("downgrade", "i1ngredients")
    with scratch.connect() as conn:
        names = conn.execute(text("SELECT name_cn FROM ingredient_category")).scalars().all()
    assert "肉類" in names
    assert "海鮮" not in names
```

Update the head pins: in `tests/test_health.py` both `== "i1ngredients"` become `== "v1ocabulary"`; in `tests/test_migrations_build_the_schema.py` `stamped == "i1ngredients"` and `"i1ngredients" in lines[0]` become `"v1ocabulary"`.

- [ ] **Step 10: Run them and watch them fail**

Run (with the lock): `venv/Scripts/python.exe -m pytest -q tests/test_seed_migration.py tests/test_migrations_build_the_schema.py tests/test_health.py`
Expected: FAIL — `Can't locate revision identified by 'v1ocabulary'`.

- [ ] **Step 11: The migration**

`alembic/versions/v1ocabulary_managed_vocabularies.py`:

```python
"""managed vocabularies, and the starter data every select needs

Revision ID: v1ocabulary
Revises: i1ngredients
Create Date: 2026-10-02

Three small tables - recipe_course, cooking_method, equipment - and the rows
that make a fresh install usable: those three seeded from the owner's
reference sheets, plus a starter ingredient-category tree and starter labels.

Seeded here rather than by a script so production receives the same starting
vocabulary on deploy with nobody touching the box. Every seeded row is ordinary
editable data.

`ON CONFLICT DO NOTHING` on every seed: a database where the owner already
typed 肉類 or 飯 by hand must not fail on a unique index, and must keep the
owner's row as it is.

Downgrade deletes only seeded rows nothing references, then drops the tables.
It identifies seeded rows by name, so an unreferenced row the owner happened
to create with a seeded name goes too; that is accepted, because the
alternative is a marker column every row carries forever for a downgrade
nobody expects to run.
"""

import sqlalchemy as sa

from alembic import op

revision = "v1ocabulary"
down_revision = "i1ngredients"
branch_labels = None
depends_on = None

COURSES = ["主食", "配菜", "湯", "小吃點心", "甜點", "飲料", "醬料"]
METHODS = ["煮", "壓力鍋煮", "煎", "炒", "炸", "氣炸", "烤", "蒸", "川燙", "涼拌", "微波", "混合"]
EQUIPMENT = [
    "鍋子", "壓力鍋", "平底鍋", "氣炸鍋", "烤箱", "油鍋", "果汁機", "電鍋", "微波爐", "保鮮盒", "碗",
]
CATEGORIES = [
    "肉類", "海鮮", "蔬菜", "菇類", "水果", "蛋豆製品", "主食穀物", "調味料", "乳製品", "乾貨",
]
LABELS = ["飯", "麵", "肉", "麵包", "馬鈴薯", "地瓜", "沙拉", "鍋"]

TABLES = ["recipe_course", "cooking_method", "equipment"]


def _create(table: str) -> None:
    op.create_table(
        table,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name_cn", sa.String(), nullable=True),
        sa.Column("name_en", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("num_nonnulls(name_cn, name_en) >= 1", name=f"ck_{table}_has_a_name"),
    )
    op.create_index(f"uq_{table}_name_cn", table, [sa.text("lower(name_cn)")], unique=True)
    op.create_index(f"uq_{table}_name_en", table, [sa.text("lower(name_en)")], unique=True)


def _seed(table: str, names: list[str]) -> None:
    for position, name in enumerate(names):
        op.execute(
            sa.text(
                f"INSERT INTO {table} (name_cn, sort_order) "
                "VALUES (:name, :sort) ON CONFLICT DO NOTHING"
            ).bindparams(name=name, sort=(position + 1) * 10)
        )


def upgrade() -> None:
    for table in TABLES:
        _create(table)
    _seed("recipe_course", COURSES)
    _seed("cooking_method", METHODS)
    _seed("equipment", EQUIPMENT)
    _seed("ingredient_category", CATEGORIES)
    for name in LABELS:
        op.execute(
            sa.text("INSERT INTO label (name_cn) VALUES (:name) ON CONFLICT DO NOTHING").bindparams(
                name=name
            )
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM label WHERE name_cn = ANY(:names) "
            "AND NOT EXISTS (SELECT 1 FROM ingredient_label l WHERE l.label_id = label.id)"
        ).bindparams(names=LABELS)
    )
    op.execute(
        sa.text(
            "DELETE FROM ingredient_category c WHERE c.name_cn = ANY(:names) "
            "AND c.parent_id IS NULL AND NOT c.is_fallback "
            "AND NOT EXISTS (SELECT 1 FROM ingredient i WHERE i.category_id = c.id) "
            "AND NOT EXISTS (SELECT 1 FROM ingredient_category k WHERE k.parent_id = c.id)"
        ).bindparams(names=CATEGORIES)
    )
    for table in reversed(TABLES):
        op.drop_index(f"uq_{table}_name_en", table)
        op.drop_index(f"uq_{table}_name_cn", table)
        op.drop_table(table)
```

- [ ] **Step 12: Run the migration, seed, schema-match and full suites**

Run (with the lock): `venv/Scripts/python.exe -m pytest -q`
Expected: all PASS. `test_the_migrated_schema_matches_the_models` is the one that proves the mixin's indexes and the migration agree; if it reports a difference, fix whichever side is wrong rather than loosening the comparison.

- [ ] **Step 13: Lint and commit**

```bash
venv/Scripts/ruff.exe check .
git add app/models/vocabulary.py app/models/__init__.py app/schemas/vocabulary.py app/schemas/__init__.py app/services/vocabularies.py app/routers/vocabulary.py app/main.py app/errors.py alembic/versions/v1ocabulary_managed_vocabularies.py tests/api/test_vocabularies.py tests/test_seed_migration.py tests/test_health.py tests/test_migrations_build_the_schema.py
git commit -m "feat: courses, cooking methods and equipment as managed vocabularies, seeded" -- app/models/vocabulary.py app/models/__init__.py app/schemas/vocabulary.py app/schemas/__init__.py app/services/vocabularies.py app/routers/vocabulary.py app/main.py app/errors.py alembic/versions/v1ocabulary_managed_vocabularies.py tests/api/test_vocabularies.py tests/test_seed_migration.py tests/test_health.py tests/test_migrations_build_the_schema.py
```

(Docs for this task land in Task 6, which documents the whole branch at once — the docs pages describe the schema as a whole, and three partial rewrites of `data-model.md` would each be wrong until the last.)

---

### Task 2: Ingredient storage state and range, heating guide, links, rating

**Files:**
- Create: `alembic/versions/i2storage_storage_heating_links.py`, `tests/api/test_ingredient_storage.py`
- Modify: `app/constants.py`, `app/models/ingredient.py`, `app/models/__init__.py`, `app/schemas/ingredient.py`, `app/schemas/__init__.py`, `app/services/ingredients.py`, `app/services/vocabularies.py`, `app/routers/ingredient.py`, `app/routers/vocabulary.py`, `app/main.py`, `app/errors.py`, `tests/test_health.py`, `tests/test_migrations_build_the_schema.py`, `tests/api/test_ingredient_model.py` (only if it references `duration_days`), `tests/api/test_constraint_statuses.py` (only where it references `duration_days` or `uq_ingredient_preservation_method`), `frontend/src/pages/edit/IngredientForm.jsx`, `frontend/src/pages/detail/Ingredient.jsx`, `frontend/src/pages/edit/DeleteIngredientDialog.jsx`

**Interfaces:**
- Consumes: `CookingMethod`, `VocabRef`, `vocabularies.USAGE` (Task 1).
- Produces: `PRESERVATION_STATES: dict[str, str]` (`unused`→未使用, `opened`→已開封, `cooked`→熟食), `RATINGS = ["S","A","B","C","D"]`, and `FIXED_VOCABULARIES: dict[str, list[dict]]`. Plan 2 appends recipe kinds, statuses and source platforms to it.
- Produces: models `IngredientHeating`, `IngredientLink`; `Ingredient.rating`, `Ingredient.heating`, `Ingredient.links`; preservation `state`, `duration_min_days`, `duration_max_days`.
- Produces: schemas `PreservationIn` (with the new fields), `HeatingIn`, `HeatingResponse` (adds `id`, `method: VocabRef`, `temperature_f`), `LinkIn`, `LinkResponse`; `IngredientSummary` gains `rating` and `fridge` (`{"min": int|None, "max": int|None}` or `None`).
- Produces: `GET /api/vocabularies/fixed`; `GET /api/ingredients?rating=&has_parent=`; `DELETE /api/edit/ingredients/{id}?aliases=&preservation=&heating=&links=`, all four required.

- [ ] **Step 1: Write the failing tests**

`tests/api/test_ingredient_storage.py`:

```python
"""Storage with a state and a range, the heating guide, links and rating.

The refusal tests each carry the data that lets them bite: a duplicate
(state, method) needs two rows, an in-use cooking method needs a heating row
pointing at it. Each refusal is paired with the case that must still pass."""

import pytest

from app.models import CookingMethod


@pytest.fixture
def air_fryer(db):
    row = CookingMethod(name_cn="氣炸", sort_order=10)
    db.add(row)
    db.flush()
    return row


def _create(client, category_id, **fields):
    payload = {"name_cn": "香腸", "category_id": category_id, **fields}
    response = client.post("/api/edit/ingredients", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_a_preservation_row_carries_a_state_and_a_range(client, fallback_category):
    body = _create(
        client,
        fallback_category.id,
        preservation=[
            {"state": "unused", "method": "冷藏", "duration_min_days": 3, "duration_max_days": 5},
            {"state": "opened", "method": "冷藏", "duration_max_days": 2, "notes": "密封"},
        ],
    )
    rows = {(r["state"], r["method"]): r for r in body["preservation"]}
    assert rows[("unused", "冷藏")]["duration_min_days"] == 3
    assert rows[("opened", "冷藏")]["duration_min_days"] is None
    assert rows[("opened", "冷藏")]["duration_max_days"] == 2


def test_state_defaults_to_unused(client, fallback_category):
    body = _create(client, fallback_category.id, preservation=[{"method": "冷凍"}])
    assert body["preservation"][0]["state"] == "unused"


def test_the_same_method_twice_in_one_state_is_refused(client, fallback_category):
    response = client.post(
        "/api/edit/ingredients",
        json={
            "name_cn": "豆腐",
            "category_id": fallback_category.id,
            "preservation": [{"method": "冷藏"}, {"method": "冷藏"}],
        },
    )
    assert response.status_code == 422


def test_the_same_method_in_two_states_is_allowed(client, fallback_category):
    body = _create(
        client,
        fallback_category.id,
        preservation=[{"method": "冷藏"}, {"state": "cooked", "method": "冷藏"}],
    )
    assert len(body["preservation"]) == 2


def test_a_minimum_above_the_maximum_is_refused(client, fallback_category):
    response = client.post(
        "/api/edit/ingredients",
        json={
            "name_cn": "豆腐",
            "category_id": fallback_category.id,
            "preservation": [{"method": "冷藏", "duration_min_days": 5, "duration_max_days": 3}],
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("field", ["duration_min_days", "duration_max_days"])
def test_a_duration_must_be_positive(client, fallback_category, field):
    response = client.post(
        "/api/edit/ingredients",
        json={
            "name_cn": "豆腐",
            "category_id": fallback_category.id,
            "preservation": [{"method": "冷藏", field: 0}],
        },
    )
    assert response.status_code == 422


def test_an_unknown_state_is_refused(client, fallback_category):
    response = client.post(
        "/api/edit/ingredients",
        json={
            "name_cn": "豆腐",
            "category_id": fallback_category.id,
            "preservation": [{"state": "frozen-ish", "method": "冷藏"}],
        },
    )
    assert response.status_code == 422


def test_a_heating_row_names_a_method_and_shows_fahrenheit(client, fallback_category, air_fryer):
    body = _create(
        client,
        fallback_category.id,
        heating=[
            {
                "method_id": air_fryer.id,
                "temperature_c": 180,
                "duration": "7 分",
                "preheat": True,
                "flip": True,
            }
        ],
    )
    row = body["heating"][0]
    assert row["method"] == {"id": air_fryer.id, "display_name": "氣炸"}
    assert row["temperature_f"] == 356
    assert row["preheat"] is True and row["flip"] is True


def test_a_heating_row_naming_no_method_is_refused(client, fallback_category):
    response = client.post(
        "/api/edit/ingredients",
        json={"name_cn": "香腸", "category_id": fallback_category.id, "heating": [{"method_id": 999999}]},
    )
    assert response.status_code == 422


def test_the_same_method_may_appear_in_two_heating_rows(client, fallback_category, air_fryer):
    body = _create(
        client,
        fallback_category.id,
        heating=[
            {"method_id": air_fryer.id, "temperature_c": 180},
            {"method_id": air_fryer.id, "temperature_c": 200},
        ],
    )
    assert len(body["heating"]) == 2


def test_a_cooking_method_in_use_by_a_heating_row_cannot_be_deleted(
    client, fallback_category, air_fryer
):
    _create(client, fallback_category.id, heating=[{"method_id": air_fryer.id}])
    response = client.delete(f"/api/edit/cooking-methods/{air_fryer.id}")
    assert response.status_code == 409
    assert response.json()["usage_count"] == 1
    listed = {row["id"]: row for row in client.get("/api/cooking-methods").json()}
    assert listed[air_fryer.id]["usage_count"] == 1


def test_a_link_must_be_http_or_https(client, fallback_category):
    for url in ["javascript:alert(1)", "ftp://x.example/a", "not a url"]:
        response = client.post(
            "/api/edit/ingredients",
            json={"name_cn": "檸檬", "category_id": fallback_category.id, "links": [{"url": url}]},
        )
        assert response.status_code == 422, url


def test_links_keep_their_order(client, fallback_category):
    body = _create(
        client,
        fallback_category.id,
        links=[
            {"url": "https://b.example/", "title": "B"},
            {"url": "https://a.example/", "title": "A"},
        ],
    )
    assert [link["title"] for link in body["links"]] == ["B", "A"]


def test_a_rating_is_one_of_the_fixed_grades(client, fallback_category):
    assert _create(client, fallback_category.id, rating="S")["rating"] == "S"
    response = client.post(
        "/api/edit/ingredients",
        json={"name_cn": "芒果", "category_id": fallback_category.id, "rating": "A+"},
    )
    assert response.status_code == 422


def test_the_library_filters_by_rating_and_by_having_a_parent(client, fallback_category):
    mango = _create(client, fallback_category.id, name_cn="芒果")
    _create(client, fallback_category.id, name_cn="愛文芒果", parent_id=mango["id"], rating="S")
    _create(client, fallback_category.id, name_cn="金煌芒果", parent_id=mango["id"], rating="A")

    graded = client.get("/api/ingredients", params={"rating": "S"}).json()
    assert [row["name_cn"] for row in graded] == ["愛文芒果"]

    varieties = client.get("/api/ingredients", params={"has_parent": "true"}).json()
    assert {row["name_cn"] for row in varieties} == {"愛文芒果", "金煌芒果"}

    roots = client.get("/api/ingredients", params={"has_parent": "false"}).json()
    assert [row["name_cn"] for row in roots] == ["芒果"]


def test_the_summary_carries_the_unused_fridge_range(client, fallback_category):
    _create(
        client,
        fallback_category.id,
        preservation=[
            {"state": "opened", "method": "冷藏", "duration_max_days": 1},
            {"state": "unused", "method": "冷藏", "duration_min_days": 5, "duration_max_days": 7},
        ],
    )
    row = client.get("/api/ingredients").json()[0]
    assert row["fridge"] == {"min": 5, "max": 7}


def test_delete_echoes_every_cascaded_count(client, fallback_category, air_fryer):
    body = _create(
        client,
        fallback_category.id,
        heating=[{"method_id": air_fryer.id}],
        links=[{"url": "https://a.example/"}],
    )
    stale = client.delete(
        f"/api/edit/ingredients/{body['id']}",
        params={"aliases": 0, "preservation": 0, "heating": 0, "links": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["actual"] == 1

    ok = client.delete(
        f"/api/edit/ingredients/{body['id']}",
        params={"aliases": 0, "preservation": 0, "heating": 1, "links": 1},
    )
    assert ok.status_code == 204


def test_the_fixed_vocabularies_are_served_with_labels(client):
    body = client.get("/api/vocabularies/fixed").json()
    assert {"value": "unused", "label": "未使用"} in body["preservation_states"]
    assert {"value": "冷藏", "label": "冷藏"} in body["preservation_methods"]
    assert [entry["value"] for entry in body["ratings"]] == ["S", "A", "B", "C", "D"]
```

Update the head pins from `v1ocabulary` to `i2storage` in the same three places as before.

- [ ] **Step 2: Run them and watch them fail**

Run (with the lock): `venv/Scripts/python.exe -m pytest -q tests/api/test_ingredient_storage.py`
Expected: FAIL — unknown fields (`state`, `heating`, `links`, `rating`) answer 422 through `extra="forbid"`.

- [ ] **Step 3: Constants**

Append to `app/constants.py`:

```python
PRESERVATION_STATES = {
    "unused": "未使用",  # bought and not yet opened or cut
    "opened": "已開封",  # opened, cut or partly used
    "cooked": "熟食",  # cooked - the reference sheet's 熟肉 rows
}

# How good one variety is: the Fruit sheet's grades.
RATINGS = ["S", "A", "B", "C", "D"]

# Every closed list the frontend renders, with its display label, served by
# GET /api/vocabularies/fixed so no list is copied into a component. Plan 2
# appends recipe kinds, statuses and source platforms.
FIXED_VOCABULARIES = {
    "preservation_methods": [{"value": m, "label": m} for m in PRESERVATION_METHODS],
    "preservation_states": [{"value": k, "label": v} for k, v in PRESERVATION_STATES.items()],
    "ratings": [{"value": r, "label": r} for r in RATINGS],
}
```

- [ ] **Step 4: Models**

In `app/models/ingredient.py`:

1. On `Ingredient`, after `needs_detail`:

```python
    # How good this one is, S to D - the Fruit sheet's grades. Used mostly on
    # varieties (愛文芒果 under 芒果). Validated against RATINGS.
    rating = Column(String, nullable=True)
```

and, beside `preservation`:

```python
    heating = relationship(
        "IngredientHeating",
        back_populates="ingredient",
        cascade="all, delete-orphan",
        order_by="IngredientHeating.sort_order",
    )
    links = relationship(
        "IngredientLink",
        back_populates="ingredient",
        cascade="all, delete-orphan",
        order_by="IngredientLink.sort_order",
    )
```

2. Replace the `IngredientPreservation` class body's docstring, `duration_days` and `__table_args__` with:

```python
class IngredientPreservation(Base):
    """One row per state and WAY of keeping the thing.

    未使用 冷藏 3-5 天; 已開封 冷藏 1-2 天; 熟食 冷凍 2-3 月. The state axis comes
    from the reference sheet's Unused / Opened columns and its 熟肉 rows.

    The duration is a RANGE, both ends optional: the sheet states a range in
    almost every row, and module 1's single typical number would have meant
    inventing one. "infinite" and "see the date" are notes, with both ends
    null.
    """

    __tablename__ = "ingredient_preservation"

    id = Column(Integer, primary_key=True)
    ingredient_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Validated against PRESERVATION_STATES / PRESERVATION_METHODS in the
    # schema layer - see app/constants.py.
    state = Column(String, nullable=False, server_default=text("'unused'"))
    method = Column(String, nullable=False)
    duration_min_days = Column(Integer, nullable=True)
    duration_max_days = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default=text("0"))

    ingredient = relationship("Ingredient", back_populates="preservation")

    __table_args__ = (
        UniqueConstraint(
            "ingredient_id", "state", "method", name="uq_ingredient_preservation_state_method"
        ),
        CheckConstraint(
            "(duration_min_days IS NULL OR duration_min_days > 0) "
            "AND (duration_max_days IS NULL OR duration_max_days > 0)",
            name="ck_ingredient_preservation_duration_positive",
        ),
        CheckConstraint(
            "duration_min_days IS NULL OR duration_max_days IS NULL "
            "OR duration_min_days <= duration_max_days",
            name="ck_ingredient_preservation_duration_order",
        ),
    )
```

3. Append:

```python
class IngredientHeating(Base):
    """How to heat or cook one thing quickly - the reference's 加熱 sheet.

    Not unique on method: 香腸 may be air-fried two ways. Temperature is
    stored in Celsius only; Fahrenheit is computed for display, because two
    stored temperatures can disagree and one cannot.
    """

    __tablename__ = "ingredient_heating"

    id = Column(Integer, primary_key=True)
    ingredient_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False, index=True
    )
    method_id = Column(
        Integer, ForeignKey("cooking_method.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    temperature_c = Column(Integer, nullable=True)
    duration = Column(String, nullable=True)
    preheat = Column(Boolean, nullable=False, server_default=text("false"))
    flip = Column(Boolean, nullable=False, server_default=text("false"))
    notes = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default=text("0"))

    ingredient = relationship("Ingredient", back_populates="heating")
    method = relationship("CookingMethod", passive_deletes="all")

    __table_args__ = (
        CheckConstraint(
            "temperature_c IS NULL OR temperature_c > 0",
            name="ck_ingredient_heating_temperature_positive",
        ),
    )


class IngredientLink(Base):
    """A reference link: where the selection or storage advice came from."""

    __tablename__ = "ingredient_link"

    id = Column(Integer, primary_key=True)
    ingredient_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url = Column(String, nullable=False)
    title = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default=text("0"))

    ingredient = relationship("Ingredient", back_populates="links")
```

Export `IngredientHeating` and `IngredientLink` from `app/models/__init__.py`.

- [ ] **Step 5: The migration**

`alembic/versions/i2storage_storage_heating_links.py`:

```python
"""storage state and range, the heating guide, links, rating

Revision ID: i2storage
Revises: v1ocabulary
Create Date: 2026-10-02

The ingredient changes the reference sheets need. Existing preservation rows
become state 'unused', and their single duration is copied to both ends of the
new range - the closest statement of what was recorded.

Downgrade reverses that lossily: rows for any state but 'unused' are deleted,
because the old unique key (ingredient, method) cannot hold two states, and
the range collapses to its maximum (or its minimum when there is no maximum).
"""

import sqlalchemy as sa

from alembic import op

revision = "i2storage"
down_revision = "v1ocabulary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ingredient", sa.Column("rating", sa.String(), nullable=True))

    op.add_column(
        "ingredient_preservation",
        sa.Column("state", sa.String(), nullable=False, server_default=sa.text("'unused'")),
    )
    op.alter_column(
        "ingredient_preservation", "duration_days", new_column_name="duration_min_days"
    )
    op.add_column(
        "ingredient_preservation", sa.Column("duration_max_days", sa.Integer(), nullable=True)
    )
    op.execute("UPDATE ingredient_preservation SET duration_max_days = duration_min_days")
    op.drop_constraint(
        "ck_ingredient_preservation_duration_positive", "ingredient_preservation", type_="check"
    )
    op.create_check_constraint(
        "ck_ingredient_preservation_duration_positive",
        "ingredient_preservation",
        "(duration_min_days IS NULL OR duration_min_days > 0) "
        "AND (duration_max_days IS NULL OR duration_max_days > 0)",
    )
    op.create_check_constraint(
        "ck_ingredient_preservation_duration_order",
        "ingredient_preservation",
        "duration_min_days IS NULL OR duration_max_days IS NULL "
        "OR duration_min_days <= duration_max_days",
    )
    op.drop_constraint(
        "uq_ingredient_preservation_method", "ingredient_preservation", type_="unique"
    )
    op.create_unique_constraint(
        "uq_ingredient_preservation_state_method",
        "ingredient_preservation",
        ["ingredient_id", "state", "method"],
    )

    op.create_table(
        "ingredient_heating",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("method_id", sa.Integer(), nullable=False),
        sa.Column("temperature_c", sa.Integer(), nullable=True),
        sa.Column("duration", sa.String(), nullable=True),
        sa.Column("preheat", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("flip", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["method_id"], ["cooking_method.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "temperature_c IS NULL OR temperature_c > 0",
            name="ck_ingredient_heating_temperature_positive",
        ),
    )
    op.create_index("ix_ingredient_heating_ingredient_id", "ingredient_heating", ["ingredient_id"])
    op.create_index("ix_ingredient_heating_method_id", "ingredient_heating", ["method_id"])

    op.create_table(
        "ingredient_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ingredient_link_ingredient_id", "ingredient_link", ["ingredient_id"])


def downgrade() -> None:
    op.drop_index("ix_ingredient_link_ingredient_id", "ingredient_link")
    op.drop_table("ingredient_link")
    op.drop_index("ix_ingredient_heating_method_id", "ingredient_heating")
    op.drop_index("ix_ingredient_heating_ingredient_id", "ingredient_heating")
    op.drop_table("ingredient_heating")

    op.execute("DELETE FROM ingredient_preservation WHERE state <> 'unused'")
    op.drop_constraint(
        "uq_ingredient_preservation_state_method", "ingredient_preservation", type_="unique"
    )
    op.create_unique_constraint(
        "uq_ingredient_preservation_method", "ingredient_preservation", ["ingredient_id", "method"]
    )
    op.drop_constraint(
        "ck_ingredient_preservation_duration_order", "ingredient_preservation", type_="check"
    )
    op.drop_constraint(
        "ck_ingredient_preservation_duration_positive", "ingredient_preservation", type_="check"
    )
    op.execute(
        "UPDATE ingredient_preservation "
        "SET duration_min_days = coalesce(duration_max_days, duration_min_days)"
    )
    op.drop_column("ingredient_preservation", "duration_max_days")
    op.alter_column(
        "ingredient_preservation", "duration_min_days", new_column_name="duration_days"
    )
    op.create_check_constraint(
        "ck_ingredient_preservation_duration_positive",
        "ingredient_preservation",
        "duration_days IS NULL OR duration_days > 0",
    )
    op.drop_column("ingredient_preservation", "state")
    op.drop_column("ingredient", "rating")
```

Before writing this, read `alembic/versions/i1ngredients_the_ingredient_library.py` and confirm the existing constraint names are exactly `ck_ingredient_preservation_duration_positive` and `uq_ingredient_preservation_method` and that the index is `ix_ingredient_preservation_ingredient_id`. A wrong name here fails only on the box.

- [ ] **Step 6: Schemas**

In `app/schemas/ingredient.py`:

1. Imports: `from app.constants import PRESERVATION_METHODS, PRESERVATION_STATES, RATINGS` and `from app.schemas.vocabulary import VocabRef`.

2. Replace `_one_note_per_method` with:

```python
def _one_note_per_state_and_method(values: list["PreservationIn"]) -> list["PreservationIn"]:
    """Mirrors uq_ingredient_preservation_state_method."""
    keys = [(v.state, v.method) for v in values]
    if len(set(keys)) != len(keys):
        raise ValueError("The same storage method is listed twice for one state")
    return values


def _check_url(value: str) -> str:
    """http and https only. A javascript: URL rendered as a link is an XSS."""
    from urllib.parse import urlparse

    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("A link must be an http or https URL")
    return value
```

and update the two validators named `one_method_each` to call it.

3. Replace `PreservationIn`:

```python
class PreservationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str = "unused"
    method: str
    duration_min_days: int | None = None
    duration_max_days: int | None = None
    notes: str | None = None
    sort_order: int = 0

    @field_validator("state")
    @classmethod
    def state_is_known(cls, value: str) -> str:
        if value not in PRESERVATION_STATES:
            raise ValueError(f"Unknown storage state: {value}")
        return value

    @field_validator("method")
    @classmethod
    def method_is_known(cls, value: str) -> str:
        if value not in PRESERVATION_METHODS:
            raise ValueError(f"Unknown preservation method: {value}")
        return value

    @field_validator("duration_min_days", "duration_max_days")
    @classmethod
    def duration_is_positive(cls, value: int | None) -> int | None:
        # Mirrors ck_ingredient_preservation_duration_positive.
        if value is not None and value <= 0:
            raise ValueError("A storage time must be a positive number of days")
        return value

    @model_validator(mode="after")
    def range_is_ordered(self):
        # Mirrors ck_ingredient_preservation_duration_order.
        if (
            self.duration_min_days is not None
            and self.duration_max_days is not None
            and self.duration_min_days > self.duration_max_days
        ):
            raise ValueError("The shortest time cannot be longer than the longest")
        return self
```

4. Add:

```python
class HeatingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_id: int
    temperature_c: int | None = None
    duration: str | None = None
    preheat: bool = False
    flip: bool = False
    notes: str | None = None
    sort_order: int = 0

    @field_validator("temperature_c")
    @classmethod
    def temperature_is_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("A temperature must be positive")
        return value


class HeatingResponse(BaseModel):
    id: int
    method: VocabRef
    temperature_c: int | None = None
    temperature_f: int | None = None
    duration: str | None = None
    preheat: bool
    flip: bool
    notes: str | None = None
    sort_order: int


class LinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    title: str | None = None
    sort_order: int = 0

    @field_validator("url")
    @classmethod
    def url_is_http(cls, value: str) -> str:
        return _check_url(value)


class LinkResponse(LinkIn):
    model_config = ConfigDict(from_attributes=True)

    id: int


class StorageRange(BaseModel):
    min: int | None = None
    max: int | None = None


def _check_rating(value: str | None) -> str | None:
    if value is not None and value not in RATINGS:
        raise ValueError(f"A rating is one of {', '.join(RATINGS)}")
    return value
```

5. `IngredientSummary` gains `rating: str | None = None` and `fridge: StorageRange | None = None`.

6. `IngredientBase` gains `rating: str | None = None`, `heating: list[HeatingIn] = []`, `links: list[LinkIn] = []`, with a validator calling `_check_rating`. `IngredientUpdate` gains `rating: str | None = None`, `heating: list[HeatingIn] | None = None`, `links: list[LinkIn] | None = None`, with the same rating validator.

7. `IngredientResponse` gains `rating: str | None = None`, `heating: list[HeatingResponse] = []`, `links: list[LinkResponse] = []`.

Export `HeatingIn`, `HeatingResponse`, `LinkIn`, `LinkResponse`, `StorageRange` from `app/schemas/__init__.py`.

- [ ] **Step 7: Service**

In `app/services/ingredients.py`:

1. Imports gain `CookingMethod`, `IngredientHeating`, `IngredientLink`. `_loaded` gains `selectinload(Ingredient.heating).selectinload(IngredientHeating.method)` and `selectinload(Ingredient.links)`.

2. `_apply_preservation` passes `state`, `duration_min_days`, `duration_max_days` instead of `duration_days`.

3. Add:

```python
def _apply_heating(db: Session, ingredient: Ingredient, entries) -> None:
    method_ids = {entry.method_id for entry in entries}
    found = {
        row.id for row in db.query(CookingMethod.id).filter(CookingMethod.id.in_(method_ids))
    }
    missing = method_ids - found
    if missing:
        raise AppError(422, f"No such cooking method: {sorted(missing)[0]}.")
    ingredient.heating = [
        IngredientHeating(
            method_id=e.method_id,
            temperature_c=e.temperature_c,
            duration=e.duration,
            preheat=e.preheat,
            flip=e.flip,
            notes=e.notes,
            sort_order=position,
        )
        for position, e in enumerate(entries)
    ]


def _apply_links(ingredient: Ingredient, entries) -> None:
    ingredient.links = [
        IngredientLink(url=e.url, title=e.title, sort_order=position)
        for position, e in enumerate(entries)
    ]
```

Heating and link `sort_order` come from list position, ignoring any sent value. The form's order is the order.

4. `create()` sets `rating=payload.rating`, and after `_apply_preservation` calls `_apply_heating(db, ingredient, payload.heating)` and `_apply_links(ingredient, payload.links)`.

5. `update()` pops `heating` and `links` as it pops `preservation`, and applies them when not `None`. `_as_entries` grows a model parameter, so the nested dicts come back as `HeatingIn` or `LinkIn`:

```python
def _as_entries(raw, model):
    return [model(**entry) if isinstance(entry, dict) else entry for entry in raw]
```

Call sites: `_as_entries(preservation, schemas.PreservationIn)`, `_as_entries(heating, schemas.HeatingIn)`, `_as_entries(links, schemas.LinkIn)`. Import `from app import schemas` inside the function as the current code does, to avoid the import cycle.

6. `search()` gains `rating: str | None = None` and `has_parent: bool | None = None`:

```python
    if rating is not None:
        query = query.filter(Ingredient.rating == rating)
    if has_parent is not None:
        query = query.filter(
            Ingredient.parent_id.isnot(None) if has_parent else Ingredient.parent_id.is_(None)
        )
```

7. `cascade_counts()` gains `"heating"` and `"links"` counts, queried like the others.

8. Add the fridge summary helper:

```python
def fridge_range(ingredient: Ingredient) -> dict | None:
    """The unused-and-refrigerated range, for the library's list view."""
    for row in ingredient.preservation:
        if row.state == "unused" and row.method == "冷藏":
            return {"min": row.duration_min_days, "max": row.duration_max_days}
    return None
```

In `app/services/vocabularies.py`, replace `CookingMethod`'s counter:

```python
def _cooking_method_usage(db: Session) -> dict[int, int]:
    from sqlalchemy import func

    from app.models import IngredientHeating

    rows = (
        db.query(IngredientHeating.method_id, func.count(IngredientHeating.id))
        .group_by(IngredientHeating.method_id)
        .all()
    )
    return dict(rows)
```

and register it in `USAGE`.

- [ ] **Step 8: Router**

In `app/routers/ingredient.py`:

1. `_response()` adds:

```python
        rating=row.rating,
        heating=[
            schemas.HeatingResponse(
                id=h.id,
                method=schemas.VocabRef(id=h.method.id, display_name=h.method.display_name),
                temperature_c=h.temperature_c,
                temperature_f=None if h.temperature_c is None else round(h.temperature_c * 9 / 5 + 32),
                duration=h.duration,
                preheat=h.preheat,
                flip=h.flip,
                notes=h.notes,
                sort_order=h.sort_order,
            )
            for h in row.heating
        ],
        links=[schemas.LinkResponse.model_validate(link) for link in row.links],
```

2. Add a summary builder and use it in `list_ingredients`. The plain `model_validate` cannot compute `fridge`:

```python
def _summary(row: Ingredient) -> schemas.IngredientSummary:
    summary = schemas.IngredientSummary.model_validate(row)
    summary.fridge = ingredients.fridge_range(row)
    return summary
```

`list_ingredients` gains `rating: str | None = None` and `has_parent: bool | None = None` and passes both to `search`.

3. `delete_ingredient` gains required `heating: int = Query(...)` and `links: int = Query(...)`, and checks them like the other two, with the nouns `"heating notes"` and `"links"`.

In `app/routers/vocabulary.py`, add the fixed-vocabulary route:

```python
from app.constants import FIXED_VOCABULARIES

fixed_router = read_router("vocabularies", "Vocabularies")


@fixed_router.get("/fixed")
def fixed_vocabularies():
    """Every closed list, with display labels, so no component copies one."""
    return FIXED_VOCABULARIES
```

Append `fixed_router` to `ROUTERS`.

In `app/errors.py` add:

```python
    "uq_ingredient_preservation_state_method": (
        "That ingredient already has a note for that state and storage method."
    ),
    "ck_ingredient_preservation_duration_order": (
        "The shortest storage time cannot be longer than the longest."
    ),
    "ck_ingredient_heating_temperature_positive": "A temperature has to be positive.",
```

Reword the existing `ck_ingredient_preservation_duration_positive` message to "A storage time has to be a positive number of days, or left empty." Delete the `uq_ingredient_preservation_method` entry, since that constraint no longer exists.

- [ ] **Step 9: Keep the existing UI working**

Plan 4 replaces these files. Until then, `dev` must not ship a broken form.

- `frontend/src/pages/edit/IngredientForm.jsx`:
  - Every `duration_days` becomes `duration_max_days`. That covers the state built on load, the payload on save, the input's `value` and its `onChange`.
  - Add `state: 'unused'` to each entry in the save payload.
- `frontend/src/pages/detail/Ingredient.jsx`, lines 90–91: show `entry.duration_min_days && entry.duration_max_days ? \`${entry.duration_min_days}–${entry.duration_max_days} days\` : entry.duration_max_days ? \`up to ${entry.duration_max_days} days\` : null`, keeping the existing `<span className="text-text-muted">`.
- `frontend/src/pages/edit/DeleteIngredientDialog.jsx`:
  - The delete params add `heating: live.heating, links: live.links`.
  - The 409 handler (lines 87–88) gains the same two `if (body.expected === live.heating)` and `live.links` arms.
  - The sentence at lines 65–67 stays as it is; plan 4 rewrites the dialog.

Run: `cd frontend && npm run lint && npm test && npm run build`
Expected: PASS, and the build writes `frontend_dist/`.

- [ ] **Step 10: Run the full suite**

Run (with the lock): `venv/Scripts/python.exe -m pytest -q`
Expected: all PASS. Any existing test that named `duration_days` or `uq_ingredient_preservation_method` fails here. Update it to the new names, and keep what it asserts: the same rule, renamed.

- [ ] **Step 11: Lint and commit**

```bash
venv/Scripts/ruff.exe check .
git status --short
```

Stage exactly the files this task changed. List them with `git status --short` and name each one. Then:

```bash
git commit -m "feat: storage state and range, heating guide, reference links and rating on ingredients" -- <the same paths>
```

---

### Task 3: Module 1 CRUD over HTTP

Module 1 shipped with constraint-status tests and no test that an ingredient, category or label can actually be added, read, edited and deleted through the API. The owner asked to know whether those three operations work.

**Files:**
- Create: `tests/api/test_ingredient_crud.py`, `tests/api/test_category_crud.py`, `tests/api/test_label_crud.py`
- Modify: only what a failing test proves broken (the `app/routers/*` or `app/services/*` file it names)

**Interfaces:**
- Consumes: the routes as they stand after Task 2.
- Produces: nothing new. Any fix lands in the file that owns the behaviour.

- [ ] **Step 1: Write the tests**

`tests/api/test_ingredient_crud.py`:

```python
"""An ingredient can be added, read, searched, edited and deleted over HTTP."""

from app.models import IngredientCategory, Label


def test_an_ingredient_round_trips_through_create_read_update_delete(client, fallback_category, db):
    meat = IngredientCategory(name_cn="肉類")
    spicy = Label(name_cn="辣")
    db.add_all([meat, spicy])
    db.flush()

    created = client.post(
        "/api/edit/ingredients",
        json={
            "name_cn": "雞腿",
            "name_en": "chicken leg",
            "category_id": meat.id,
            "description": "帶骨",
            "aliases": ["雞腿肉", "drumstick"],
            "label_ids": [spicy.id],
        },
    )
    assert created.status_code == 201, created.text
    ingredient_id = created.json()["id"]

    read = client.get(f"/api/ingredients/{ingredient_id}").json()
    assert read["category"]["display_name"] == "肉類"
    assert read["aliases"] == ["drumstick", "雞腿肉"]
    assert [label["display_name"] for label in read["labels"]] == ["辣"]

    updated = client.patch(
        f"/api/edit/ingredients/{ingredient_id}",
        json={"description": None, "aliases": ["雞腿肉"], "label_ids": []},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["description"] is None
    assert body["aliases"] == ["雞腿肉"]
    assert body["labels"] == []
    assert body["name_en"] == "chicken leg"  # untouched: not sent

    counts = client.get(f"/api/ingredients/{ingredient_id}/cascade").json()
    deleted = client.delete(
        f"/api/edit/ingredients/{ingredient_id}",
        params={k: counts[k] for k in ("aliases", "preservation", "heating", "links")},
    )
    assert deleted.status_code == 204
    assert client.get(f"/api/ingredients/{ingredient_id}").status_code == 404


def test_search_matches_any_name_slot_and_aliases_once(client, fallback_category):
    client.post(
        "/api/edit/ingredients",
        json={"name_cn": "青蔥", "category_id": fallback_category.id, "aliases": ["蔥", "蔥花"]},
    )
    client.post(
        "/api/edit/ingredients",
        json={"name_cn": "洋蔥", "name_en": "onion", "category_id": fallback_category.id},
    )
    by_alias = client.get("/api/ingredients", params={"q": "蔥花"}).json()
    assert [row["name_cn"] for row in by_alias] == ["青蔥"]

    by_both = client.get("/api/ingredients", params={"q": "蔥"}).json()
    assert sorted(row["name_cn"] for row in by_both) == ["洋蔥", "青蔥"]

    by_english = client.get("/api/ingredients", params={"q": "ONION"}).json()
    assert [row["name_cn"] for row in by_english] == ["洋蔥"]


def test_an_ingredient_with_children_cannot_be_deleted(client, fallback_category):
    parent = client.post(
        "/api/edit/ingredients", json={"name_cn": "醬油", "category_id": fallback_category.id}
    ).json()
    client.post(
        "/api/edit/ingredients",
        json={"name_cn": "生抽", "category_id": fallback_category.id, "parent_id": parent["id"]},
    )
    response = client.delete(
        f"/api/edit/ingredients/{parent['id']}",
        params={"aliases": 0, "preservation": 0, "heating": 0, "links": 0},
    )
    assert response.status_code == 409
    assert client.get(f"/api/ingredients/{parent['id']}").status_code == 200


def test_reparenting_into_a_descendant_is_refused(client, fallback_category):
    a = client.post("/api/edit/ingredients", json={"name_cn": "甲", "category_id": fallback_category.id}).json()
    b = client.post(
        "/api/edit/ingredients",
        json={"name_cn": "乙", "category_id": fallback_category.id, "parent_id": a["id"]},
    ).json()
    response = client.patch(f"/api/edit/ingredients/{a['id']}", json={"parent_id": b["id"]})
    assert response.status_code == 422


def test_an_unknown_ingredient_is_404_on_read_update_and_delete(client):
    assert client.get("/api/ingredients/999999").status_code == 404
    assert client.patch("/api/edit/ingredients/999999", json={"name_cn": "x"}).status_code == 404
    response = client.delete(
        "/api/edit/ingredients/999999",
        params={"aliases": 0, "preservation": 0, "heating": 0, "links": 0},
    )
    assert response.status_code == 404
```

`tests/api/test_category_crud.py`:

```python
"""Categories can be added, renamed, moved and deleted - and the fallback cannot."""


def test_a_category_round_trips_and_can_be_renamed_and_moved(client, fallback_category):
    root = client.post("/api/edit/ingredient-categories", json={"name_cn": "蔬菜"}).json()
    child = client.post(
        "/api/edit/ingredient-categories", json={"name_cn": "葉菜", "parent_id": root["id"]}
    )
    assert child.status_code == 201, child.text
    child = child.json()

    renamed = client.patch(
        f"/api/edit/ingredient-categories/{child['id']}", json={"name_cn": "葉菜類"}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["display_name"] == "葉菜類"

    moved = client.patch(f"/api/edit/ingredient-categories/{child['id']}", json={"parent_id": None})
    assert moved.json()["parent_id"] is None

    tree = client.get("/api/ingredient-categories").json()
    assert {node["name_cn"] for node in tree} >= {"蔬菜", "葉菜類", "未分類"}

    assert client.delete(f"/api/edit/ingredient-categories/{child['id']}").status_code == 204


def test_a_category_holding_an_ingredient_cannot_be_deleted(client, fallback_category):
    meat = client.post("/api/edit/ingredient-categories", json={"name_cn": "肉類"}).json()
    client.post("/api/edit/ingredients", json={"name_cn": "雞腿", "category_id": meat["id"]})
    assert client.delete(f"/api/edit/ingredient-categories/{meat['id']}").status_code == 409


def test_the_fallback_category_cannot_be_deleted(client, fallback_category):
    response = client.delete(f"/api/edit/ingredient-categories/{fallback_category.id}")
    assert response.status_code == 409
```

`tests/api/test_label_crud.py`:

```python
"""Labels can be added, renamed and deleted; deleting one detaches it."""


def test_a_label_round_trips_and_deleting_it_detaches_it(client, fallback_category):
    label = client.post("/api/edit/labels", json={"name_cn": "辣"}).json()
    ingredient = client.post(
        "/api/edit/ingredients",
        json={"name_cn": "辣椒", "category_id": fallback_category.id, "label_ids": [label["id"]]},
    ).json()

    renamed = client.patch(f"/api/edit/labels/{label['id']}", json={"name_en": "spicy"})
    assert renamed.json()["name_en"] == "spicy"
    assert renamed.json()["ingredient_count"] == 1

    assert client.delete(f"/api/edit/labels/{label['id']}").status_code == 204
    assert client.get(f"/api/ingredients/{ingredient['id']}").json()["labels"] == []
```

- [ ] **Step 2: Run them**

Run (with the lock): `venv/Scripts/python.exe -m pytest -q tests/api/test_ingredient_crud.py tests/api/test_category_crud.py tests/api/test_label_crud.py`

Expected: PASS. **Any failure here is a real module-1 defect.** Fix the code, not the test, using superpowers:systematic-debugging, and keep a note of each one for the PR body. If a test's expectation turns out to be wrong about the documented behaviour, check `docs/api.md` first; if the doc agrees with the test, it is the code that is wrong.

- [ ] **Step 3: Commit**

```bash
git add tests/api/test_ingredient_crud.py tests/api/test_category_crud.py tests/api/test_label_crud.py
git commit -m "test: ingredients, categories and labels round-trip through HTTP" -- tests/api/test_ingredient_crud.py tests/api/test_category_crud.py tests/api/test_label_crud.py
```

If a fix was needed, commit it separately first, with a `fix:` message naming the defect, and stage only its files.

---

### Task 4: The image library and ingredient galleries

**Files:**
- Create: `app/models/image.py`, `app/schemas/image.py`, `app/services/images.py`, `app/routers/image.py`, `alembic/versions/m1images_image_library.py`, `tests/api/test_images.py`
- Modify: `requirements.txt`, `app/config.py`, `app/models/__init__.py`, `app/models/ingredient.py`, `app/schemas/__init__.py`, `app/schemas/ingredient.py`, `app/services/ingredients.py`, `app/routers/ingredient.py`, `app/main.py`, `app/errors.py`, `tests/test_spa_routing.py`, `tests/test_health.py`, `tests/test_migrations_build_the_schema.py`, `frontend/vite.config.js`, `.gitignore`, `.dockerignore`

**Interfaces:**
- Consumes: `Ingredient` (Task 2's response builders).
- Produces: model `Image` (`id`, `checksum`, `storage_key`, `thumb_key`, `original_filename`, `byte_size`, `width`, `height`, `uploaded_at`) and `IngredientImage` (`id`, `ingredient_id`, `image_id`, `position`, `focus`). Plan 2's `RecipeImage` and plan 3's `KitchenNoteImage` copy `IngredientImage`'s shape.
- Produces: `app.services.images.store_upload(db, upload: UploadFile) -> tuple[Image, bool]` (the bool is "created"), `delete_image(db, image: Image) -> None`, `image_url(key: str) -> str`, `owners(db, image_id) -> list[dict]`, and `OWNER_TABLES: list[tuple[type, str, str]]`, which plans 2 and 3 append to.
- Produces: schemas `ImageSummary(id, url, thumb_url, width, height, byte_size, original_filename, uploaded_at, attachment_count)`, `AttachedImage(image_id, url, thumb_url, width, height, focus)`, `ImageAttachmentIn(image_id: int, focus: str | None)`, and `CoverRef(thumb_url, focus)`.
- Produces: `app.services.ingredients.set_images(db, ingredient, entries)`. Plans 2 and 3 implement the same function shape for their owners.
- Produces: routes `POST /api/edit/images` (multipart `file`), `GET /api/images?unused=&limit=&offset=`, `GET /api/images/{id}`, `DELETE /api/edit/images/{id}`, and `PUT /api/edit/ingredients/{id}/images`.

- [ ] **Step 1: Dependencies**

Append to `requirements.txt`:

```
Pillow==11.3.0
python-multipart==0.0.20
```

Run: `venv/Scripts/python.exe -m pip install -r requirements-dev.txt`

Then check that both versions exist on PyPI for Python 3.13 (`pip index versions Pillow`). If a pin does not resolve, take the newest 3.13-compatible release and say so in the commit message.

- [ ] **Step 2: Write the failing tests**

`tests/api/test_images.py`:

```python
"""Upload, deduplicate, attach, serve and delete images.

Every test points IMAGE_DIR at its own tmp_path (autouse), so nothing touches
the real data/images. The upload code reads the setting at call time; a test
that found a file in the real directory would mean that rule had broken.
"""

import io

import pytest
from PIL import Image as PILImage

from app import config


@pytest.fixture(autouse=True)
def image_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "image_dir", str(tmp_path))
    return tmp_path


def _png(size=(64, 48), colour=(200, 120, 40, 255), mode="RGBA") -> bytes:
    buffer = io.BytesIO()
    PILImage.new(mode, size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(client, data: bytes, name="dish.png"):
    return client.post("/api/edit/images", files={"file": (name, data, "image/png")})


def test_an_upload_is_reencoded_to_jpeg_and_stored_under_its_hash(client, image_dir):
    response = _upload(client, _png())
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["url"].startswith("/images/library/") and body["url"].endswith(".jpg")
    assert body["thumb_url"].startswith("/images/library/thumbs/")
    assert (body["width"], body["height"]) == (64, 48)
    stored = image_dir / body["url"].removeprefix("/images/")
    assert stored.is_file()
    assert PILImage.open(stored).format == "JPEG"


def test_the_same_picture_uploaded_twice_is_one_row(client, image_dir):
    first = _upload(client, _png()).json()
    second = _upload(client, _png(), name="again.png")
    assert second.status_code == 200
    assert second.json()["id"] == first["id"]
    assert len(list((image_dir / "library").glob("*.jpg"))) == 1


def test_a_file_that_is_not_an_image_is_refused(client, image_dir):
    response = _upload(client, b"<svg onload=alert(1)>", name="x.png")
    assert response.status_code == 422
    assert not (image_dir / "library").exists() or not list((image_dir / "library").glob("*.jpg"))


def test_an_upload_over_the_size_cap_is_refused(client, monkeypatch):
    monkeypatch.setattr(config.settings, "max_image_upload_mb", 1)
    noise = PILImage.effect_noise((1400, 1400), 100).convert("RGB")
    buffer = io.BytesIO()
    noise.save(buffer, format="BMP")
    assert len(buffer.getvalue()) > 1024 * 1024
    response = _upload(client, buffer.getvalue(), name="big.bmp")
    assert response.status_code == 413


def test_a_decompression_bomb_is_refused(client):
    buffer = io.BytesIO()
    # 144 megapixels: over twice the 50 MP ceiling, so Pillow raises rather than warns.
    PILImage.new("1", (12000, 12000)).save(buffer, format="PNG")
    response = _upload(client, buffer.getvalue(), name="bomb.png")
    assert response.status_code == 422


def test_the_long_edge_is_capped_and_the_thumbnail_is_small(client, image_dir):
    body = _upload(client, _png(size=(3000, 1500))).json()
    assert (body["width"], body["height"]) == (2000, 1000)
    thumb = PILImage.open(image_dir / body["thumb_url"].removeprefix("/images/"))
    assert max(thumb.size) == 400


def test_exif_rotation_is_applied_before_the_metadata_is_stripped(client, image_dir):
    """A phone's portrait photo is stored landscape plus an Orientation tag.

    The re-encode drops EXIF, so unless the rotation is applied first the
    stored image is sideways. Orientation 6 means "rotate 90 degrees clockwise
    to display": a 60x40 stored image displays as 40x60.
    """
    buffer = io.BytesIO()
    exif = PILImage.Exif()
    exif[0x0112] = 6
    PILImage.new("RGB", (60, 40), (10, 200, 10)).save(buffer, format="JPEG", exif=exif)
    body = _upload(client, buffer.getvalue(), name="phone.jpg").json()
    assert (body["width"], body["height"]) == (40, 60)
    stored = PILImage.open(image_dir / body["url"].removeprefix("/images/"))
    assert not stored.getexif()


def test_an_attached_image_shows_on_the_ingredient_and_is_its_cover(client, fallback_category):
    image = _upload(client, _png()).json()
    ingredient = client.post(
        "/api/edit/ingredients", json={"name_cn": "芒果", "category_id": fallback_category.id}
    ).json()
    response = client.put(
        f"/api/edit/ingredients/{ingredient['id']}/images",
        json=[{"image_id": image["id"], "focus": "50% 30%"}],
    )
    assert response.status_code == 200, response.text
    detail = client.get(f"/api/ingredients/{ingredient['id']}").json()
    assert detail["images"][0]["image_id"] == image["id"]
    assert detail["images"][0]["focus"] == "50% 30%"
    summary = client.get("/api/ingredients").json()[0]
    assert summary["cover"] == {"thumb_url": image["thumb_url"], "focus": "50% 30%"}


@pytest.mark.parametrize("focus", ["101% 0%", "50%", "a% b%", "50 50"])
def test_a_malformed_focus_is_refused(client, fallback_category, focus):
    image = _upload(client, _png()).json()
    ingredient = client.post(
        "/api/edit/ingredients", json={"name_cn": "芒果", "category_id": fallback_category.id}
    ).json()
    response = client.put(
        f"/api/edit/ingredients/{ingredient['id']}/images",
        json=[{"image_id": image["id"], "focus": focus}],
    )
    assert response.status_code == 422


def test_attaching_an_unknown_image_is_404_and_a_repeat_is_422(client, fallback_category):
    image = _upload(client, _png()).json()
    ingredient = client.post(
        "/api/edit/ingredients", json={"name_cn": "芒果", "category_id": fallback_category.id}
    ).json()
    url = f"/api/edit/ingredients/{ingredient['id']}/images"
    assert client.put(url, json=[{"image_id": 999999}]).status_code == 404
    assert (
        client.put(url, json=[{"image_id": image["id"]}, {"image_id": image["id"]}]).status_code
        == 422
    )


def test_an_attached_image_cannot_be_deleted_and_its_file_survives(
    client, fallback_category, image_dir
):
    image = _upload(client, _png()).json()
    ingredient = client.post(
        "/api/edit/ingredients", json={"name_cn": "芒果", "category_id": fallback_category.id}
    ).json()
    client.put(f"/api/edit/ingredients/{ingredient['id']}/images", json=[{"image_id": image["id"]}])

    response = client.delete(f"/api/edit/images/{image['id']}")
    assert response.status_code == 409
    assert response.json()["owners"] == [
        {"type": "ingredient", "id": ingredient["id"], "display_name": "芒果"}
    ]
    assert (image_dir / image["url"].removeprefix("/images/")).is_file()


def test_an_unattached_image_deletes_with_its_files(client, image_dir):
    image = _upload(client, _png()).json()
    assert client.delete(f"/api/edit/images/{image['id']}").status_code == 204
    assert not (image_dir / image["url"].removeprefix("/images/")).exists()
    assert not (image_dir / image["thumb_url"].removeprefix("/images/")).exists()


def test_deleting_an_ingredient_keeps_its_image_in_the_library(client, fallback_category):
    image = _upload(client, _png()).json()
    ingredient = client.post(
        "/api/edit/ingredients", json={"name_cn": "芒果", "category_id": fallback_category.id}
    ).json()
    client.put(f"/api/edit/ingredients/{ingredient['id']}/images", json=[{"image_id": image["id"]}])
    client.delete(
        f"/api/edit/ingredients/{ingredient['id']}",
        params={"aliases": 0, "preservation": 0, "heating": 0, "links": 0},
    )
    unused = client.get("/api/images", params={"unused": "true"}).json()
    assert [row["id"] for row in unused] == [image["id"]]


def test_the_unused_filter_hides_attached_images(client, fallback_category):
    used = _upload(client, _png(colour=(1, 2, 3, 255))).json()
    spare = _upload(client, _png(colour=(9, 8, 7, 255))).json()
    ingredient = client.post(
        "/api/edit/ingredients", json={"name_cn": "芒果", "category_id": fallback_category.id}
    ).json()
    client.put(f"/api/edit/ingredients/{ingredient['id']}/images", json=[{"image_id": used["id"]}])
    assert [r["id"] for r in client.get("/api/images", params={"unused": "true"}).json()] == [spare["id"]]
    everything = {r["id"]: r for r in client.get("/api/images").json()}
    assert everything[used["id"]]["attachment_count"] == 1


def test_a_stored_image_is_served_and_a_missing_one_is_404_not_the_spa(client):
    image = _upload(client, _png()).json()
    served = client.get(image["url"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"
    assert client.get("/images/library/does-not-exist.jpg").status_code == 404
```

Add to `tests/test_spa_routing.py` a test in that file's existing style. It builds the app against a tmp dist with an `index.html`, then asserts that `GET /images/nope.jpg` is a 404 and not `index.html`. Copy the setup the file's current `/api` guard test uses, and change only the path.

Update the head pins from `i2storage` to `m1images`.

- [ ] **Step 3: Run them and watch them fail**

Run (with the lock): `venv/Scripts/python.exe -m pytest -q tests/api/test_images.py tests/test_spa_routing.py`

Expected: FAIL. The tests error on `config.settings.image_dir`, and the routes answer 404.

- [ ] **Step 4: Settings**

In `app/config.py`, after `database_url`:

```python
    # Where uploaded images live. A setting, not a hardcoded relative path:
    # media hard-codes its directory and records that leaving the path
    # implicit produced a wrong spec. In the container this is
    # /app/data/images, bind-mounted from the box (docker-compose.prod.yml).
    image_dir: str = "data/images"
    max_image_upload_mb: int = 10
```

- [ ] **Step 5: Models**

`app/models/image.py`:

```python
"""The image library: one row per stored picture, and one gallery per owner.

Media's two-table library, with one deliberate difference: attachments are a
join table PER OWNER with real foreign keys, not one polymorphic table with an
owner_type and an owner_id nothing constrains. Media records that "nothing in
the database stops an attachment outliving its owner", and carries orphan gaps
because of it. food has three owner types; three small tables remove the class.

Owner side CASCADE (deleting a recipe removes its gallery, never the picture);
image side RESTRICT (an attached picture cannot be deleted - the API answers
409 naming the owners first).
"""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base, get_taipei_now


class Image(Base):
    __tablename__ = "image"

    id = Column(Integer, primary_key=True)
    # SHA-256 of the NORMALISED JPEG bytes. Identical pixels deduplicate;
    # "the same picture" in two formats does not, and is not meant to - media
    # learned that the hard way.
    checksum = Column(String, nullable=False)
    storage_key = Column(String, nullable=False)
    thumb_key = Column(String, nullable=False)
    original_filename = Column(String, nullable=True)
    byte_size = Column(BigInteger, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, default=get_taipei_now)

    __table_args__ = (UniqueConstraint("checksum", name="uq_image_checksum"),)


class IngredientImage(Base):
    """One picture in one ingredient's gallery. Position 0 is the cover."""

    __tablename__ = "ingredient_image"

    id = Column(Integer, primary_key=True)
    ingredient_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_id = Column(
        Integer, ForeignKey("image.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    # "X% Y%", 0-100 each, or NULL for centred. Where a cropped thumbnail
    # centres - per attachment, because one picture may be cropped
    # differently in two galleries.
    focus = Column(String, nullable=True)

    ingredient = relationship("Ingredient", back_populates="images")
    image = relationship("Image", passive_deletes="all")

    __table_args__ = (
        UniqueConstraint("ingredient_id", "position", name="uq_ingredient_image_position"),
        UniqueConstraint("ingredient_id", "image_id", name="uq_ingredient_image_once"),
    )
```

On `Ingredient` add:

```python
    images = relationship(
        "IngredientImage",
        back_populates="ingredient",
        cascade="all, delete-orphan",
        order_by="IngredientImage.position",
    )
```

Export `Image` and `IngredientImage` from `app/models/__init__.py`.

- [ ] **Step 6: The migration**

`alembic/versions/m1images_image_library.py`. The docstring is the same opening line, plus one paragraph on per-owner tables pointing at `app/models/image.py`.

- `image`: columns as the model, `sa.UniqueConstraint("checksum", name="uq_image_checksum")`.
- `ingredient_image`: columns as the model, plus:
  - the two foreign keys with their `ondelete`;
  - the two unique constraints by name;
  - indexes `ix_ingredient_image_ingredient_id` and `ix_ingredient_image_image_id`.
- Downgrade drops both, `ingredient_image` first.

```python
"""the image library and ingredient galleries

Revision ID: m1images
Revises: i2storage
Create Date: 2026-10-02

One table of stored pictures and one gallery table per owner type, with real
foreign keys rather than media's polymorphic owner columns - see
app/models/image.py. Recipes and kitchen notes add their own gallery tables in
their own revisions.

Downgrade drops the tables. The files under IMAGE_DIR are not touched: a
migration has no business deleting the only copy of a photograph.
"""

import sqlalchemy as sa

from alembic import op

revision = "m1images"
down_revision = "i2storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("thumb_key", sa.String(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checksum", name="uq_image_checksum"),
    )
    op.create_table(
        "ingredient_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("focus", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["image_id"], ["image.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("ingredient_id", "position", name="uq_ingredient_image_position"),
        sa.UniqueConstraint("ingredient_id", "image_id", name="uq_ingredient_image_once"),
    )
    op.create_index("ix_ingredient_image_ingredient_id", "ingredient_image", ["ingredient_id"])
    op.create_index("ix_ingredient_image_image_id", "ingredient_image", ["image_id"])


def downgrade() -> None:
    op.drop_index("ix_ingredient_image_image_id", "ingredient_image")
    op.drop_index("ix_ingredient_image_ingredient_id", "ingredient_image")
    op.drop_table("ingredient_image")
    op.drop_table("image")
```

- [ ] **Step 7: Schemas**

`app/schemas/image.py`:

```python
"""Image shapes, and the one focus-point rule every gallery shares."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

_FOCUS = re.compile(r"^(\d{1,3}(?:\.\d+)?)% (\d{1,3}(?:\.\d+)?)%$")


def check_focus(value: str | None) -> str | None:
    """'X% Y%' with both in 0..100, or None for centred (media's rule)."""
    if value is None:
        return None
    match = _FOCUS.match(value.strip())
    if not match or any(float(part) > 100 for part in match.groups()):
        raise ValueError("A focus point is 'X% Y%' with both between 0 and 100")
    return value.strip()


class ImageSummary(BaseModel):
    id: int
    url: str
    thumb_url: str
    width: int
    height: int
    byte_size: int
    original_filename: str | None = None
    uploaded_at: datetime | None = None
    attachment_count: int = 0


class ImageOwner(BaseModel):
    type: str
    id: int
    display_name: str


class ImageDetail(ImageSummary):
    owners: list[ImageOwner] = []


class ImageAttachmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_id: int
    focus: str | None = None

    @field_validator("focus")
    @classmethod
    def focus_is_valid(cls, value):
        return check_focus(value)


class AttachedImage(BaseModel):
    image_id: int
    url: str
    thumb_url: str
    width: int
    height: int
    focus: str | None = None


class CoverRef(BaseModel):
    thumb_url: str
    focus: str | None = None
```

Export all of them from `app/schemas/__init__.py`. `IngredientSummary` gains `cover: CoverRef | None = None`, and `IngredientResponse` gains `images: list[AttachedImage] = []`. Both are imported from `app.schemas.image`.

- [ ] **Step 8: The image service**

`app/services/images.py`:

```python
"""Reading an upload, normalising it, storing it, and deleting it.

Media's pipeline (media/app/services/integrations/image_library.py), carried
over: the extension and Content-Type are ignored; Pillow verifies, then the
image is reopened and RE-ENCODED to JPEG. The re-encode is the security
control - it strips EXIF (GPS included) and anything riding in the file - so
nothing that was uploaded is ever served as uploaded.

Two additions media does not have, both because these are phone photographs:
the EXIF orientation is applied BEFORE the metadata is dropped, or every
portrait photo lands sideways; and a pixel ceiling turns a decompression bomb
into a 422 rather than a worker eating memory.

IMAGE_DIR is read from `config.settings` on every call, never bound at import.
Media's cover route imports its directory by value, which is why patching it
in a test does nothing there.
"""

import hashlib
import io
import os
import warnings
from pathlib import Path

from fastapi import UploadFile
from PIL import Image as PILImage
from PIL import ImageOps
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import config
from app.errors import AppError
from app.models import Image, Ingredient, IngredientImage

LONG_EDGE = 2000
THUMB_EDGE = 400
JPEG_QUALITY = 88
CHUNK = 1024 * 1024
# ~50 megapixels: well above any phone camera, far below a bomb.
MAX_PIXELS = 50_000_000

# (attachment model, owner type name, owner model). Plans 2 and 3 append their
# gallery tables here; owners() and attachment counts read only this list.
OWNER_TABLES: list[tuple[type, str, type]] = [
    (IngredientImage, "ingredient", Ingredient),
]


def image_dir() -> Path:
    return Path(config.settings.image_dir)


def image_url(key: str) -> str:
    return f"/images/{key}"


def _read_capped(upload: UploadFile) -> bytes:
    limit = config.settings.max_image_upload_mb * 1024 * 1024
    if upload.size is not None and upload.size > limit:
        raise AppError(413, f"Images are limited to {config.settings.max_image_upload_mb} MB.")
    data = bytearray()
    while chunk := upload.file.read(CHUNK):
        data.extend(chunk)
        if len(data) > limit:
            raise AppError(
                413, f"Images are limited to {config.settings.max_image_upload_mb} MB."
            )
    return bytes(data)


def _open(raw: bytes) -> PILImage.Image:
    PILImage.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with warnings.catch_warnings():
            # Pillow WARNS between 1x and 2x the ceiling and raises above it;
            # both are a bomb as far as this app is concerned.
            warnings.simplefilter("error", PILImage.DecompressionBombWarning)
            PILImage.open(io.BytesIO(raw)).verify()
            image = PILImage.open(io.BytesIO(raw))
            image.load()
    except (PILImage.DecompressionBombError, PILImage.DecompressionBombWarning):
        raise AppError(422, "That image is too large to process.") from None
    except Exception:
        raise AppError(422, "That file is not an image this app can read.") from None
    return image


def _to_rgb(image: PILImage.Image) -> PILImage.Image:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = PILImage.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return image.convert("RGB")


def _jpeg(image: PILImage.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue()


def normalise(raw: bytes) -> tuple[bytes, bytes, int, int]:
    """(full JPEG, thumbnail JPEG, width, height) of the normalised image."""
    image = _to_rgb(ImageOps.exif_transpose(_open(raw)))
    image.thumbnail((LONG_EDGE, LONG_EDGE))
    thumb = image.copy()
    thumb.thumbnail((THUMB_EDGE, THUMB_EDGE))
    return _jpeg(image), _jpeg(thumb), image.width, image.height


def _write(key: str, data: bytes) -> None:
    path = image_dir() / key
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    partial.write_bytes(data)
    os.replace(partial, path)


def store_upload(db: Session, upload: UploadFile) -> tuple[Image, bool]:
    full, thumb, width, height = normalise(_read_capped(upload))
    checksum = hashlib.sha256(full).hexdigest()
    storage_key = f"library/{checksum}.jpg"
    thumb_key = f"library/thumbs/{checksum}.jpg"

    existing = db.query(Image).filter(Image.checksum == checksum).one_or_none()
    # Written again even when the row exists: if the file was lost, an
    # identical re-upload is how it comes back.
    _write(storage_key, full)
    _write(thumb_key, thumb)
    if existing is not None:
        return existing, False

    image = Image(
        checksum=checksum,
        storage_key=storage_key,
        thumb_key=thumb_key,
        original_filename=upload.filename,
        byte_size=len(full),
        width=width,
        height=height,
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return image, True


def attachment_counts(db: Session) -> dict[int, int]:
    counts: dict[int, int] = {}
    for model, _, _ in OWNER_TABLES:
        for image_id, n in db.query(model.image_id, func.count(model.id)).group_by(model.image_id):
            counts[image_id] = counts.get(image_id, 0) + n
    return counts


def owners(db: Session, image_id: int) -> list[dict]:
    found = []
    for model, type_name, owner_model in OWNER_TABLES:
        owner_fk = next(c for c in model.__table__.columns if c.name.endswith("_id") and c.name != "image_id")
        rows = (
            db.query(owner_model)
            .join(model, getattr(model, owner_fk.name) == owner_model.id)
            .filter(model.image_id == image_id)
            .all()
        )
        found += [{"type": type_name, "id": r.id, "display_name": r.display_name} for r in rows]
    return found


def delete_image(db: Session, image: Image) -> None:
    attached = owners(db, image.id)
    if attached:
        raise AppError(409, "That image is still attached; remove it there first.", owners=attached)
    keys = (image.storage_key, image.thumb_key)
    db.delete(image)
    db.commit()
    for key in keys:
        (image_dir() / key).unlink(missing_ok=True)


def resolve_attachments(db: Session, entries) -> dict[int, Image]:
    """The images a gallery PUT names: 404 for an unknown id, 422 for a repeat."""
    ids = [entry.image_id for entry in entries]
    if len(set(ids)) != len(ids):
        raise AppError(422, "The same image is listed twice.")
    found = {row.id: row for row in db.query(Image).filter(Image.id.in_(ids))} if ids else {}
    missing = [i for i in ids if i not in found]
    if missing:
        raise AppError(404, f"No such image: {missing[0]}.")
    return found
```

`owners()` derives the owner foreign-key column from the attachment table: the one column ending in `_id` other than `image_id`. Plans 2 and 3 then only append to `OWNER_TABLES`. If a later gallery table ever has a second `_id` column, make the tuple carry the column explicitly instead.

- [ ] **Step 9: The image router and the ingredient gallery route**

`app/routers/image.py`:

```python
"""The image library. Reading is public; uploading and deleting sit behind Access."""

from fastapi import Depends, File, Query, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.errors import AppError
from app.models import Image
from app.routing import read_router, write_router
from app.services import images

router = read_router("images", "Images")
edit = write_router("images", "Images")


def _summary(row: Image, counts: dict[int, int]) -> schemas.ImageSummary:
    return schemas.ImageSummary(
        id=row.id,
        url=images.image_url(row.storage_key),
        thumb_url=images.image_url(row.thumb_key),
        width=row.width,
        height=row.height,
        byte_size=row.byte_size,
        original_filename=row.original_filename,
        uploaded_at=row.uploaded_at,
        attachment_count=counts.get(row.id, 0),
    )


def _get(db: Session, image_id: int) -> Image:
    row = db.query(Image).filter(Image.id == image_id).one_or_none()
    if row is None:
        raise AppError(404, "No such image.")
    return row


@router.get("", response_model=list[schemas.ImageSummary])
def list_images(
    unused: bool | None = None,
    limit: int = Query(default=60, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Newest first. `unused` filters in SQL, before the page is cut.

    The filter must not run in Python after limit/offset - that silently
    shortens pages (docs/notes/decisions.md, "a row-hiding filter belongs in
    SQL").
    """
    counts = images.attachment_counts(db)
    query = db.query(Image)
    if unused is not None:
        used_ids = list(counts)
        query = query.filter(~Image.id.in_(used_ids) if unused else Image.id.in_(used_ids))
    rows = query.order_by(Image.uploaded_at.desc(), Image.id.desc()).offset(offset).limit(limit)
    return [_summary(row, counts) for row in rows]


@router.get("/{image_id}", response_model=schemas.ImageDetail)
def get_image(image_id: int, db: Session = Depends(get_db)):
    row = _get(db, image_id)
    attached = images.owners(db, image_id)
    return schemas.ImageDetail(
        **_summary(row, {row.id: len(attached)}).model_dump(), owners=attached
    )


@edit.post("", response_model=schemas.ImageSummary, status_code=201)
def upload_image(file: UploadFile = File(...), db: Session = Depends(get_db)):
    row, created = images.store_upload(db, file)
    body = _summary(row, images.attachment_counts(db)).model_dump(mode="json")
    return JSONResponse(status_code=201 if created else 200, content=body)


@edit.delete("/{image_id}", status_code=204)
def delete_image(image_id: int, db: Session = Depends(get_db)):
    images.delete_image(db, _get(db, image_id))
    return Response(status_code=204)
```

In `app/services/ingredients.py` add the following, and add `selectinload(Ingredient.images).selectinload(IngredientImage.image)` to `_loaded`:

```python
def set_images(db: Session, ingredient: Ingredient, entries) -> None:
    from app.services.images import resolve_attachments

    found = resolve_attachments(db, entries)
    ingredient.images = []
    db.flush()  # clear the old positions before reusing them
    ingredient.images = [
        IngredientImage(image_id=found[e.image_id].id, position=i, focus=e.focus)
        for i, e in enumerate(entries)
    ]
    db.commit()
```

In `app/routers/ingredient.py`:

- Import `images` from `app.services`.
- Add the gallery route:

```python
@edit.put("/{ingredient_id}/images", response_model=schemas.IngredientResponse)
def set_ingredient_images(
    ingredient_id: int,
    payload: list[schemas.ImageAttachmentIn],
    db: Session = Depends(get_db),
):
    """Replace the gallery, in order. Position 0 is the cover."""
    ingredient = ingredients.get(db, ingredient_id)
    ingredients.set_images(db, ingredient, payload)
    return _response(ingredients.get(db, ingredient_id))
```

- `_response()` gains:

```python
        images=[
            schemas.AttachedImage(
                image_id=a.image.id,
                url=images.image_url(a.image.storage_key),
                thumb_url=images.image_url(a.image.thumb_key),
                width=a.image.width,
                height=a.image.height,
                focus=a.focus,
            )
            for a in row.images
        ],
```

- `_summary()` gains:

```python
    if row.images:
        cover = row.images[0]
        summary.cover = schemas.CoverRef(
            thumb_url=images.image_url(cover.image.thumb_key), focus=cover.focus
        )
```

In `app/errors.py` add sentences for:
- `uq_image_checksum`: "That image is already in the library."
- `uq_ingredient_image_position`: "Two images cannot share one position."
- `uq_ingredient_image_once`: "That image is already in this gallery."

- [ ] **Step 10: Serving, the catch-all and the dev proxy**

In `app/main.py`:

- Import `image` from `app.routers` and include `image.router` and `image.edit` beside the others.
- Before the `if dist.is_dir():` block, add:

```python
    # Uploaded images. Public, like every read here, and safe to cache
    # forever: names are content hashes, so a replaced picture is a new URL.
    # check_dir=False so a fresh machine without data/images still starts;
    # the directory is created on first upload.
    from app import config as app_config

    image_root = Path(app_config.settings.image_dir)
    image_root.mkdir(parents=True, exist_ok=True)
    app.mount("/images", StaticFiles(directory=image_root, check_dir=False), name="images")
```

- In the SPA catch-all, beside the `api` and `health` guards, add:

```python
            if full_path == "images" or full_path.startswith("images/"):
                raise HTTPException(status_code=404)
```

- Extend its docstring's guard paragraph to say `/images` is refused for the same reason: a missing picture must be a 404, not `index.html`.

The mount is created when `create_app()` runs, so the test fixture `image_dir` (autouse) has to patch the setting before the `client` fixture builds the app. Autouse fixtures are set up first, which is why it is autouse.

In `frontend/vite.config.js`, add `'/images': 'http://localhost:8001'` to the proxy map, in the same form the `/health` entry uses.

In `.gitignore`, under "Rebuilt locally", add `data/images/`. In `.dockerignore`, add `data/`.

- [ ] **Step 11: Run the image tests and the full suite**

Run (with the lock): `venv/Scripts/python.exe -m pytest -q`

Expected: all PASS. Check the bomb test's duration with `-k bomb --durations=1`: it should run in under two seconds. If it takes longer, the ceiling was not applied before decoding.

- [ ] **Step 12: Lint and commit**

```bash
venv/Scripts/ruff.exe check .
cd frontend && npm run lint && cd ..
```

Stage exactly the files this task touched, naming each one, and commit:

```bash
git commit -m "feat: an image library with re-encoded uploads, and ingredient galleries" -- <paths>
```

---

### Task 5: Production bind mount

**Files:**
- Modify: `docker-compose.prod.yml`, `tests/unit/test_prod_compose.py`

**Interfaces:**
- Consumes: `IMAGE_DIR` defaults to `data/images`, which resolves to `/app/data/images` in the container (`WORKDIR /app`).

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_prod_compose.py`:

```python
def test_uploaded_images_are_a_bind_mount_outside_the_image(compose):
    """The only copy of every uploaded photograph. Without the mount it lives
    in the container's writable layer and the next deploy deletes it."""
    mounts = compose["services"]["app"].get("volumes", [])
    assert "./data/images:/app/data/images" in mounts, mounts
```

Run (with the lock): `venv/Scripts/python.exe -m pytest -q tests/unit/test_prod_compose.py`

Expected: FAIL.

- [ ] **Step 2: Add the mount**

In `docker-compose.prod.yml`, under `app:` after `environment:`:

```yaml
    volumes:
      # Uploaded images: the ONLY copy of every photograph uploaded to this
      # app. A bind mount rather than a named volume so a backup job sees
      # ordinary files. There is no such job yet - docs/open-items.md.
      - ./data/images:/app/data/images
```

Run: `venv/Scripts/python.exe -m pytest -q tests/unit/test_prod_compose.py`

Expected: PASS. That includes the existing `test_no_mount_names_a_single_file`, which now has a mount to check.

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: bind-mount uploaded images in production" -- docker-compose.prod.yml tests/unit/test_prod_compose.py
```

---

### Task 6: Docs, open items, and the branch's PR

**Files:**
- Create: `docs/open-items.md`
- Modify: `docs/data-model.md`, `docs/api.md`, `docs/testing.md`, `docs/notes/decisions.md`, `docs/deployment.md`, `CLAUDE.md`

- [ ] **Step 1: Read each page before editing it**

Edit each page in its own voice, present tense, describing what is true now. **Grep each claim you change, not just the file** (platform `CLAUDE.md`, "Rule"). At minimum, grep for `duration_days`, `uq_ingredient_preservation_method`, "Six tables" and "single typical number".

- [ ] **Step 2: Write the pages**

- `docs/data-model.md`:
  - Replace "Six tables" with the true count.
  - Rewrite the `ingredient_preservation` section: state, range, the new unique key, and why the range replaced the typical number.
  - Add sections for `ingredient_heating`, `ingredient_link`, `ingredient.rating`, the three managed vocabularies and their seeds, `image` and `ingredient_image` (per-owner galleries, RESTRICT on the image side, focus), and the new rows in the deletion table.
- `docs/api.md`: every new route and parameter from Tasks 1, 2 and 4, the changed delete parameters, and `GET /api/vocabularies/fixed`.
- `docs/testing.md`:
  - The new files.
  - The load-bearing fixtures: `air_fryer` makes the in-use refusal bite; the pre-existing `飯` and `肉類` rows make the seed test bite; `image_dir` is autouse because the mount is built when the app is.
  - The image tests never touch the real `data/images`.
- `docs/notes/decisions.md`, a new section "Storage ranges, heating, images":
  - Range rather than typical number: this reverses module 1's line, and the reason is that the sheet states ranges.
  - Per-owner gallery tables rather than media's polymorphic table, and why.
  - EXIF transpose and the pixel ceiling as additions to media's pipeline.
  - `IMAGE_DIR` as a setting, read at call time.
  - Seeding in a migration with `ON CONFLICT DO NOTHING`.
  - The lossy downgrade of `i2storage`.
- `docs/deployment.md`: the `data/images` bind mount, that the directory must exist on the box before the first upload (or be created by the first upload — say which, after checking), and that it is not backed up.
- `docs/open-items.md` (new):

```markdown
# Open items

Known defects and unmade decisions nobody is working on. Everything here is
open by definition; an item is closed by deleting it in the change that fixes
it.

## Uploaded images have no backup

`data/images` on the box is bind-mounted and is the only copy of every
uploaded photograph. Nothing copies it anywhere. A dish photograph cannot be
re-fetched, unlike a cover image an API supplies again. media solves the same
problem with its own rclone-to-R2 timer; whether food copies that or the
platform defines one file-backup contract for every app is a platform decision,
raised with the manager session.
```

- `CLAUDE.md`, "Status": module 1 now includes storage state and ranges, heating, links, rating, the three vocabularies and the image library. Recipes are still next. Name the head revision `m1images`.

- [ ] **Step 3: Commit the docs**

```bash
git commit -m "docs: storage ranges, heating, vocabularies and the image library" -- docs/data-model.md docs/api.md docs/testing.md docs/notes/decisions.md docs/deployment.md docs/open-items.md CLAUDE.md
```

(`git commit -- <paths>` on a new, untracked file needs it staged first: `git add docs/open-items.md` immediately before the commit, in the same command line.)

- [ ] **Step 4: Verify in the running app**

```powershell
.\dev.ps1
```

Then, in a browser on `http://localhost:8001` (after `cd frontend && npm run build`):
1. Create an ingredient with a preservation row. Edit it. Confirm the detail page shows its range.
2. Delete it through the dialog.
3. Confirm the category select now lists the ten seeded categories.

Then through the API (`curl` or the browser's devtools):
4. Upload an image to `/api/edit/images`.
5. `PUT` it onto an ingredient.
6. Open the returned `/images/...` URL.
7. Try to delete the image: expect 409.
8. Clear the gallery, delete the image again: expect 204.

Plan 4 builds the UI for steps 4–8. Report what was done and what was seen, including anything that did not work.

- [ ] **Step 5: Ask the manager about file backup**

If `ListAgents` shows a manager session, send it the open item's text and ask for a platform decision. If it does not, say so in the PR body and tell the owner.

- [ ] **Step 6: Push and open the PR into `dev`**

```bash
git push -u origin feat/ingredient-storage-heating-images
gh pr create --base dev --title "Ingredient storage and heating, vocabularies, image library" --body "<body>"
```

The body, with no AI trailers:
- What changed, by task.
- Every module-1 defect Task 3 found and fixed.
- The migration chain: `i1ngredients` → `v1ocabulary` → `i2storage` → `m1images`.
- That `i2storage`'s downgrade is lossy, and how.
- The bind mount, and the open backup item.

Wait for CI to go green. Then merge it yourself; a PR into `dev` needs no approval. Pull `dev`.

The branch is finished with after the merge, so tear it down. Plan 2 starts from the updated `dev`:

```bash
git checkout dev && git pull origin dev
git branch -d feat/ingredient-storage-heating-images && git push origin --delete feat/ingredient-storage-heating-images
```

---

## Self-review notes

- **Spec coverage for branch 1:**
  - ingredient `rating`: Task 2.
  - storage state and range: Task 2.
  - heating: Task 2.
  - links: Task 2.
  - vocabularies and seeds, including categories and labels: Task 1.
  - fixed-enum endpoint: Task 2.
  - image library, ingredient galleries, serving, catch-all and size cap: Task 4.
  - bind mount: Task 5.
  - open item and manager question: Task 6.
  - module-1 CRUD tests: Task 3.
  - docs: Task 6.
- **Deferred to their own plans, per the spec's delivery section:**
  - plan 2: recipe usage counts for courses and equipment, ingredient "used in", and merge;
  - plan 3: kitchen-note galleries;
  - plan 4: every UI change beyond the compatibility edits in Task 2;
  - plan 5: the import.
- **Names that later plans depend on:** `VocabRef`, `vocabularies.USAGE`, `FIXED_VOCABULARIES`, `images.OWNER_TABLES`, `images.resolve_attachments`, `images.image_url`, `ImageAttachmentIn`, `AttachedImage`, `CoverRef`, and `set_images(db, owner, entries)`.
