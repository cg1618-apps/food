"""The recipe library. Reads are public; writes sit behind Access.

The same shape as `app/routers/ingredient.py`: a read router and a write
router from `app.routing`, a response built explicitly, and a delete that
takes the counts its dialog showed.
"""

from fastapi import Depends, Query, Response
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.errors import StaleCountError
from app.models import Recipe, RecipeImage
from app.routing import read_router, write_router
from app.services import images, recipes

router = read_router("recipes", "Recipes")
edit = write_router("recipes", "Recipes")


def dish_ref(row) -> schemas.DishRef:
    return schemas.DishRef(id=row.id, display_name=row.display_name, kind=row.kind)


def recipe_ref(row: Recipe) -> schemas.RecipeRef:
    return schemas.RecipeRef(id=row.id, display_name=row.display_name, dish=dish_ref(row.dish))


def _vocab(rows) -> list[schemas.VocabRef]:
    return [schemas.VocabRef(id=r.id, display_name=r.display_name) for r in rows]


def _ref(value) -> schemas.VocabRef | None:
    return schemas.VocabRef(id=value.id, display_name=value.display_name) if value else None


def summary(row: Recipe) -> schemas.RecipeSummary:
    return schemas.RecipeSummary(
        id=row.id,
        display_name=row.display_name,
        name=row.name,
        dish=dish_ref(row.dish),
        status=_ref(row.status),
        course=_ref(row.dish.course),
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
        sub_dish=dish_ref(line.sub_dish) if line.sub_dish else None,
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


def _dish_brief(dish) -> schemas.DishBrief:
    return schemas.DishBrief(
        **dish_ref(dish).model_dump(),
        course=_ref(dish.course),
        region=_ref(dish.region),
        labels=_vocab(dish.labels),
        serves_as=_vocab(dish.serves_as),
    )


def _response(row: Recipe) -> schemas.RecipeResponse:
    """Built explicitly rather than straight off the ORM row, as the
    ingredient's is: a line's target is one of two shapes, lines and steps
    are split by group, and `written_up` and `other_recipes` are derived."""
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
        name=row.name,
        dish=_dish_brief(row.dish),
        status=_ref(row.status),
        servings=row.servings,
        time=row.time,
        storage_notes=row.storage_notes,
        notes=row.notes,
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
        methods=_vocab(row.methods),
        equipment=_vocab(row.equipment),
        images=images.attached(row.images),
        other_recipes=[recipe_ref(r) for r in recipes.other_recipes(row)],
        written_up=recipes.written_up(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ==========================================
# PUBLIC READS
# ==========================================


@router.get("", response_model=list[schemas.RecipeSummary])
def list_recipes(
    q: str | None = Query(
        default=None, description="Matches the recipe's own name, or its dish's names and aliases"
    ),
    dish_id: list[int] | None = Query(None),
    kind: list[str] | None = Query(None, description="The dish's kind"),
    course_id: list[int] | None = Query(None, description="The dish's course"),
    region_id: list[int] | None = Query(None, description="The dish's region"),
    label_id: list[int] | None = Query(None, description="A label on the dish"),
    status_id: list[int] | None = Query(None),
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
        dish_id=dish_id,
        kind=kind,
        course_id=course_id,
        region_id=region_id,
        label_id=label_id,
        status_id=status_id,
        method_id=method_id,
        equipment_id=equipment_id,
        author_id=author_id,
        ingredient_id=ingredient_id,
        written_up=written_up,
    )
    return [summary(row) for row in rows]


@router.get("/{recipe_id}", response_model=schemas.RecipeResponse)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)):
    return _response(recipes.get(db, recipe_id))


@router.get("/{recipe_id}/cascade", response_model=dict)
def cascade_preview(recipe_id: int, db: Session = Depends(get_db)):
    """What deleting this would remove. Nothing blocks deleting a recipe:
    lines name dishes, never a recipe, and the dish stays."""
    recipes.get(db, recipe_id)
    return recipes.cascade_counts(db, recipe_id)


# ==========================================
# WRITES - behind Cloudflare Access
# ==========================================


@edit.post("", response_model=schemas.RecipeResponse, status_code=201)
def create_recipe(payload: schemas.RecipeCreate, db: Session = Depends(get_db)):
    return _response(recipes.create(db, payload))


@edit.patch("/{recipe_id}", response_model=schemas.RecipeResponse)
def update_recipe(recipe_id: int, payload: schemas.RecipeUpdate, db: Session = Depends(get_db)):
    """Also the in-place status change: a PATCH carrying only `status_id`."""
    return _response(recipes.update(db, recipe_id, payload))


@edit.delete("/{recipe_id}", status_code=204)
def delete_recipe(
    recipe_id: int,
    sources: int = Query(..., description="Source count the dialog showed"),
    lines: int = Query(..., description="Ingredient-line count the dialog showed, grouped or not"),
    steps: int = Query(..., description="Step count the dialog showed, grouped or not"),
    db: Session = Depends(get_db),
):
    """Delete, with the counts the user was shown echoed back.

    The dish stays, even when this was its last recipe: a dish is worth
    keeping on its own, and deleting it is its own decision.
    """
    recipe = recipes.get(db, recipe_id)
    actual = recipes.cascade_counts(db, recipe_id)
    shown = {"sources": sources, "lines": lines, "steps": steps}
    words = {"sources": "sources", "lines": "ingredient lines", "steps": "steps"}
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
    return _response(recipes.get(db, recipe_id))
