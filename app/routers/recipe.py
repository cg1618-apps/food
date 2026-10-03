"""The recipe library. Reads are public; writes sit behind Access.

The same shape as `app/routers/ingredient.py`: a read router and a write
router from `app.routing`, a response built explicitly, and a delete that
takes the counts its dialog showed.
"""

from fastapi import Depends, Query, Response
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.errors import AppError, StaleCountError
from app.models import Recipe, RecipeImage
from app.routing import read_router, write_router
from app.services import images, recipes

router = read_router("recipes", "Recipes")
edit = write_router("recipes", "Recipes")


def recipe_ref(row: Recipe) -> schemas.RecipeRef:
    return schemas.RecipeRef(id=row.id, display_name=row.display_name, kind=row.kind)


def _vocab(rows) -> list[schemas.VocabRef]:
    return [schemas.VocabRef(id=r.id, display_name=r.display_name) for r in rows]


def _ref(value) -> schemas.VocabRef | None:
    return schemas.VocabRef(id=value.id, display_name=value.display_name) if value else None


def _summary(row: Recipe) -> schemas.RecipeSummary:
    return schemas.RecipeSummary(
        id=row.id,
        display_name=row.display_name,
        name_cn=row.name_cn,
        name_en=row.name_en,
        name_alt=row.name_alt,
        kind=row.kind,
        status=_ref(row.status),
        course=_ref(row.course),
        methods=_vocab(row.methods),
        authors=_vocab(recipes.authors(row)),
        time=row.time,
        written_up=recipes.written_up(row),
        cover=images.cover(row.images),
    )


def _line(line) -> schemas.LineResponse:
    return schemas.LineResponse(
        id=line.id,
        position=line.position,
        ingredient=schemas.IngredientRef(
            id=line.ingredient.id,
            display_name=line.ingredient.display_name,
            needs_detail=line.ingredient.needs_detail,
        )
        if line.ingredient
        else None,
        sub_recipe=recipe_ref(line.sub_recipe) if line.sub_recipe else None,
        amount=line.amount,
        note=line.note,
        is_optional=line.is_optional,
    )


def _step(step) -> schemas.StepResponse:
    return schemas.StepResponse(
        id=step.id, position=step.position, kind=step.kind, body=step.body
    )


def _grouped(rows, groups, build_row, build_group):
    """The ungrouped rows, and each group with its own: `rows` is the
    recipe's whole list in position order, so each group's keep theirs."""
    by_group: dict[int | None, list] = {}
    for item in rows:
        by_group.setdefault(item.group_id, []).append(build_row(item))
    return by_group.get(None, []), [
        build_group(group, by_group.get(group.id, [])) for group in groups
    ]


def _group_fields(group) -> dict:
    return {
        "id": group.id,
        "position": group.position,
        "group": _ref(group.group),
        "name": group.name,
        "display_name": group.display_name,
    }


def _response(row: Recipe, used_in: list[Recipe]) -> schemas.RecipeResponse:
    """Built explicitly rather than straight off the ORM row, as the
    ingredient's is: aliases are strings on the wire, a line's target is one of
    two shapes, lines and steps are split by group, and `written_up` and
    `versions` are derived."""
    lines, line_groups = _grouped(
        row.lines,
        row.line_groups,
        _line,
        lambda group, rows: schemas.LineGroupResponse(**_group_fields(group), lines=rows),
    )
    steps, step_groups = _grouped(
        row.steps,
        row.step_groups,
        _step,
        lambda group, rows: schemas.StepGroupResponse(**_group_fields(group), steps=rows),
    )
    return schemas.RecipeResponse(
        id=row.id,
        display_name=row.display_name,
        name_cn=row.name_cn,
        name_en=row.name_en,
        name_alt=row.name_alt,
        kind=row.kind,
        status=_ref(row.status),
        course=_ref(row.course),
        servings=row.servings,
        time=row.time,
        description=row.description,
        storage_notes=row.storage_notes,
        notes=row.notes,
        aliases=sorted(alias.value for alias in row.aliases),
        sources=[
            schemas.SourceResponse(
                id=s.id,
                platform=_ref(s.platform),
                author=_ref(s.author),
                url=s.url,
                title=s.title,
                sort_order=s.sort_order,
            )
            for s in row.sources
        ],
        lines=lines,
        line_groups=line_groups,
        steps=steps,
        step_groups=step_groups,
        serves_as=_vocab(row.serves_as),
        labels=_vocab(row.labels),
        methods=_vocab(row.methods),
        equipment=_vocab(row.equipment),
        images=images.attached(row.images),
        variant_of=recipe_ref(row.variant_of) if row.variant_of else None,
        versions=[recipe_ref(v) for v in recipes.versions(row)],
        used_in=[recipe_ref(r) for r in used_in],
        written_up=recipes.written_up(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _full(db: Session, row: Recipe) -> schemas.RecipeResponse:
    return _response(row, recipes.used_in(db, row.id))


# ==========================================
# PUBLIC READS
# ==========================================


@router.get("", response_model=list[schemas.RecipeSummary])
def list_recipes(
    q: str | None = Query(default=None, description="Matches any name slot or an alias"),
    course_id: list[int] | None = Query(None),
    status_id: list[int] | None = Query(None),
    kind: list[str] | None = Query(None),
    label_id: list[int] | None = Query(None),
    method_id: list[int] | None = Query(None),
    equipment_id: list[int] | None = Query(None),
    author_id: list[int] | None = Query(None, description="A source's author"),
    ingredient_id: list[int] | None = Query(None),
    written_up: bool | None = None,
    db: Session = Depends(get_db),
):
    """The library: a bare array sorted by display name, as the ingredient
    list is. A repeated parameter means "any of" its values."""
    rows = recipes.search(
        db,
        q=q,
        course_id=course_id,
        status_id=status_id,
        kind=kind,
        label_id=label_id,
        method_id=method_id,
        equipment_id=equipment_id,
        author_id=author_id,
        ingredient_id=ingredient_id,
        written_up=written_up,
    )
    return [_summary(row) for row in rows]


@router.get("/{recipe_id}", response_model=schemas.RecipeResponse)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)):
    return _full(db, recipes.get(db, recipe_id))


@router.get("/{recipe_id}/cascade", response_model=dict)
def cascade_preview(recipe_id: int, db: Session = Depends(get_db)):
    """What deleting this would remove, and how many recipes block it.

    `used_in` is a blocking count, not a cascaded one - like an ingredient's
    `children` - and it is not echoed back on the delete.
    """
    recipes.get(db, recipe_id)
    counts = recipes.cascade_counts(db, recipe_id)
    counts["used_in"] = len(recipes.used_in(db, recipe_id))
    return counts


# ==========================================
# WRITES - behind Cloudflare Access
# ==========================================


@edit.post("", response_model=schemas.RecipeResponse, status_code=201)
def create_recipe(payload: schemas.RecipeCreate, db: Session = Depends(get_db)):
    return _full(db, recipes.create(db, payload))


@edit.patch("/{recipe_id}", response_model=schemas.RecipeResponse)
def update_recipe(recipe_id: int, payload: schemas.RecipeUpdate, db: Session = Depends(get_db)):
    """Also the in-place status change: a PATCH carrying only `status_id`."""
    return _full(db, recipes.update(db, recipe_id, payload))


@edit.delete("/{recipe_id}", status_code=204)
def delete_recipe(
    recipe_id: int,
    aliases: int = Query(..., description="Alias count the dialog showed"),
    sources: int = Query(..., description="Source count the dialog showed"),
    lines: int = Query(..., description="Ingredient-line count the dialog showed, grouped or not"),
    steps: int = Query(..., description="Step count the dialog showed, grouped or not"),
    db: Session = Depends(get_db),
):
    """Delete, with the counts the user was shown echoed back.

    A recipe another recipe's line names is refused BEFORE the database is
    asked, with those recipes on the body - the RESTRICT would refuse too, but
    could only say that something refers to it, not what. Versions survive the
    delete with `variant_of_id` null.
    """
    recipe = recipes.get(db, recipe_id)
    users = recipes.used_in(db, recipe_id)
    if users:
        raise AppError(
            409,
            "Other recipes use this one, so it cannot be removed.",
            used_in=[{"id": r.id, "display_name": r.display_name} for r in users],
        )

    actual = recipes.cascade_counts(db, recipe_id)
    shown = {"aliases": aliases, "sources": sources, "lines": lines, "steps": steps}
    words = {"aliases": "aliases", "sources": "sources", "lines": "ingredient lines", "steps": "steps"}
    for field, expected in shown.items():
        if actual[field] != expected:
            raise StaleCountError(field, words[field], expected, actual[field])

    db.delete(recipe)
    db.commit()
    return Response(status_code=204)


@edit.put("/{recipe_id}/images", response_model=schemas.RecipeResponse)
def set_recipe_images(
    recipe_id: int,
    payload: list[schemas.ImageAttachmentIn],
    db: Session = Depends(get_db),
):
    """Replace the gallery, in order. Position 0 is the cover."""
    recipe = recipes.get(db, recipe_id)
    images.set_images(db, recipe, "images", RecipeImage, payload)
    return _full(db, recipes.get(db, recipe_id))
