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
# Its own small read router: the creators are not a recipe, and nesting them
# under /api/recipes would put a string where a recipe id is read.
creators = read_router("recipe-creators", "Recipes")


def recipe_ref(row: Recipe) -> schemas.RecipeRef:
    return schemas.RecipeRef(id=row.id, display_name=row.display_name, kind=row.kind)


def _vocab(rows) -> list[schemas.VocabRef]:
    return [schemas.VocabRef(id=r.id, display_name=r.display_name) for r in rows]


def _course(row: Recipe) -> schemas.VocabRef | None:
    return schemas.VocabRef(id=row.course.id, display_name=row.course.display_name) if row.course else None


def _summary(row: Recipe) -> schemas.RecipeSummary:
    return schemas.RecipeSummary(
        id=row.id,
        display_name=row.display_name,
        name_cn=row.name_cn,
        name_en=row.name_en,
        name_alt=row.name_alt,
        kind=row.kind,
        status=row.status,
        course=_course(row),
        methods=_vocab(row.methods),
        creators=recipes.creators(row),
        time=row.time,
        written_up=recipes.written_up(row),
        cover=images.cover(row.images),
    )


def _response(row: Recipe, used_in: list[Recipe]) -> schemas.RecipeResponse:
    """Built explicitly rather than straight off the ORM row, as the
    ingredient's is: aliases are strings on the wire, a line's target is one of
    two shapes, and `written_up` and `versions` are derived."""
    return schemas.RecipeResponse(
        id=row.id,
        display_name=row.display_name,
        name_cn=row.name_cn,
        name_en=row.name_en,
        name_alt=row.name_alt,
        kind=row.kind,
        status=row.status,
        course=_course(row),
        servings=row.servings,
        time=row.time,
        description=row.description,
        storage_notes=row.storage_notes,
        notes=row.notes,
        aliases=sorted(alias.value for alias in row.aliases),
        sources=[schemas.SourceResponse.model_validate(s) for s in row.sources],
        lines=[
            schemas.LineResponse(
                id=line.id,
                position=line.position,
                section=line.section,
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
            for line in row.lines
        ],
        steps=[schemas.StepResponse.model_validate(s) for s in row.steps],
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
    status: list[str] | None = Query(None),
    kind: list[str] | None = Query(None),
    label_id: list[int] | None = Query(None),
    method_id: list[int] | None = Query(None),
    equipment_id: list[int] | None = Query(None),
    creator: list[str] | None = Query(None, description="Exact; repeat for any of several"),
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
        status=status,
        kind=kind,
        label_id=label_id,
        method_id=method_id,
        equipment_id=equipment_id,
        creator=creator,
        ingredient_id=ingredient_id,
        written_up=written_up,
    )
    return [_summary(row) for row in rows]


@creators.get("", response_model=list[str])
def list_creators(db: Session = Depends(get_db)):
    """Every distinct source creator, sorted - for suggestions and the filter."""
    return recipes.all_creators(db)


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
    """Also the in-place status change: a PATCH carrying only `status`."""
    return _full(db, recipes.update(db, recipe_id, payload))


@edit.delete("/{recipe_id}", status_code=204)
def delete_recipe(
    recipe_id: int,
    aliases: int = Query(..., description="Alias count the dialog showed"),
    sources: int = Query(..., description="Source count the dialog showed"),
    lines: int = Query(..., description="Ingredient-line count the dialog showed"),
    steps: int = Query(..., description="Step count the dialog showed"),
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
