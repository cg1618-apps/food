"""The ingredient library. Reads are public; writes sit behind Access.

The two routers below are the whole read/write split, and the prefixes come
from `app.routing` rather than being written out here - a literal "/api/edit"
in this file would be a second copy of the one thing that module exists to be
the only copy of.

There is no auth dependency on the write routes and there is not meant to be.
The gate is Cloudflare Access, in front of the box, on the path prefix. What
this file owes that arrangement is simply that every mutation lives under the
prefix, which `tests/api/test_route_prefixes.py` asserts.
"""

from fastapi import Depends, Query, Response
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.errors import AppError, StaleCountError
from app.models import Ingredient, IngredientImage
from app.routers.recipe import recipe_ref
from app.routing import read_router, write_router
from app.services import images, ingredients, recipes
from app.services.lookup import check_label_scope

router = read_router("ingredients", "Ingredients")
edit = write_router("ingredients", "Ingredients")


def _summary(row: Ingredient, counts: dict[int, int]) -> schemas.IngredientSummary:
    """`counts` is `recipes.used_in_counts` for every row being shown, fetched
    once by the caller rather than once per row."""
    summary = schemas.IngredientSummary.model_validate(row)
    fridge = ingredients.fridge_range(row)
    summary.fridge = schemas.StorageRange(**fridge) if fridge else None
    summary.cover = images.cover(row.images)
    summary.used_in_count = counts.get(row.id, 0)
    return summary


def _summaries(db: Session, rows: list[Ingredient]) -> list[schemas.IngredientSummary]:
    counts = recipes.used_in_counts(db, [row.id for row in rows])
    return [_summary(row, counts) for row in rows]


def _related(row: Ingredient, counts: dict[int, int]) -> schemas.RelatedIngredient:
    """A parent or child on the full row: the summary's own columns, its count
    and where to get it, without the fridge range and cover a list row loads
    for itself."""
    summary = schemas.RelatedIngredient.model_validate(row)
    summary.used_in_count = counts.get(row.id, 0)
    return summary


def _full(db: Session, row: Ingredient) -> schemas.IngredientResponse:
    """The full response, with what it needs from outside the row."""
    related = ([row.parent] if row.parent else []) + list(row.children)
    counts = recipes.used_in_counts(db, [row.id] + [r.id for r in related])
    return _response(row, counts, recipes.recipes_using_ingredient(db, [row.id]))


def _response(
    row: Ingredient, counts: dict[int, int], used_in: list
) -> schemas.IngredientResponse:
    """Built explicitly rather than straight off the ORM row.

    `aliases` is a list of strings on the wire and a list of rows in the
    database, and `display_name` is computed - so the mapping is written out
    once here instead of being half-declared in the schema and half-guessed by
    `from_attributes`.
    """
    return schemas.IngredientResponse(
        id=row.id,
        display_name=row.display_name,
        name_cn=row.name_cn,
        name_en=row.name_en,
        name_alt=row.name_alt,
        category=schemas.ingredient.CategoryRef(
            id=row.category.id, display_name=row.category.display_name
        )
        if row.category
        else None,
        parent=_related(row.parent, counts) if row.parent else None,
        children=[_related(c, counts) for c in row.children],
        description=row.description,
        selection_notes=row.selection_notes,
        sourcing_notes=row.sourcing_notes,
        preservation_notes=row.preservation_notes,
        needs_detail=row.needs_detail,
        rating=row.rating,
        aliases=sorted(alias.value for alias in row.aliases),
        preservation=[
            schemas.PreservationResponse.model_validate(entry) for entry in row.preservation
        ],
        labels=[
            schemas.ingredient.LabelRef(id=label.id, display_name=label.display_name)
            for label in row.labels
        ],
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
        images=images.attached(row.images),
        used_in=[recipe_ref(r) for r in used_in],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ==========================================
# PUBLIC READS
# ==========================================


@router.get("", response_model=list[schemas.IngredientSummary])
def list_ingredients(
    q: str | None = Query(default=None, description="Matches any name slot or an alias"),
    category_id: int | None = None,
    label_id: int | None = None,
    parent_id: int | None = None,
    needs_detail: bool | None = None,
    rating: str | None = None,
    has_parent: bool | None = None,
    group_id: int | None = Query(
        default=None, description="An ingredient and its varieties at any depth"
    ),
    db: Session = Depends(get_db),
):
    """The library, the search box, and module 2's typeahead - one endpoint.

    A bare array, the whole table, sorted by display name in Python. No
    pagination: this is a few hundred rows, and a page size is a decision that
    only buys something when there is something to buy.
    """
    rows = ingredients.search(
        db,
        q=q,
        category_id=category_id,
        label_id=label_id,
        parent_id=parent_id,
        needs_detail=needs_detail,
        rating=rating,
        has_parent=has_parent,
        group_id=group_id,
    )
    return _summaries(db, rows)


@router.get("/{ingredient_id}", response_model=schemas.IngredientResponse)
def get_ingredient(ingredient_id: int, db: Session = Depends(get_db)):
    return _full(db, ingredients.get(db, ingredient_id))


@router.get("/{ingredient_id}/cascade", response_model=dict)
def cascade_preview(ingredient_id: int, db: Session = Depends(get_db)):
    """What deleting this would remove, for the confirmation dialog.

    Public because it is a read, and because the dialog that uses it is behind
    Access anyway. It returns counts, never rows. `children` and `recipes`
    block the delete rather than being removed by it.
    """
    ingredients.get(db, ingredient_id)
    counts = ingredients.cascade_counts(db, ingredient_id)
    counts["children"] = ingredients.child_count(db, ingredient_id)
    counts["recipes"] = len(recipes.recipes_naming_ingredient(db, ingredient_id))
    return counts


@router.get("/{ingredient_id}/merge-preview", response_model=schemas.MergePreview)
def merge_preview(ingredient_id: int, into: int = Query(...), db: Session = Depends(get_db)):
    """What merging this into `into` would move, drop and add. Writes nothing.

    Computed by the same function the merge executes, so the preview cannot
    describe a merge other than the one that runs.
    """
    return _merge_preview(db, ingredients.merge_plan(db, ingredient_id, into))


def _merge_preview(db: Session, plan: ingredients.MergePlan) -> schemas.MergePreview:
    counts = recipes.used_in_counts(db, [plan.source.id, plan.target.id])
    return schemas.MergePreview(
        source=_summary(plan.source, counts),
        target=_summary(plan.target, counts),
        moves=plan.moves(),
        new_aliases=plan.new_aliases,
        dropped_preservation=[
            {"state": r.state, "method": r.method} for r in plan.dropped_preservation
        ],
        prose=plan.prose,
        fingerprint=plan.fingerprint(),
    )


# ==========================================
# WRITES - behind Cloudflare Access
# ==========================================


@edit.post("", response_model=schemas.IngredientResponse, status_code=201)
def create_ingredient(payload: schemas.IngredientCreate, db: Session = Depends(get_db)):
    return _full(db, ingredients.create(db, payload))


@edit.patch("/{ingredient_id}", response_model=schemas.IngredientResponse)
def update_ingredient(
    ingredient_id: int, payload: schemas.IngredientUpdate, db: Session = Depends(get_db)
):
    return _full(db, ingredients.update(db, ingredient_id, payload))


@edit.delete("/{ingredient_id}", status_code=204)
def delete_ingredient(
    ingredient_id: int,
    aliases: int = Query(..., description="Alias count the dialog showed"),
    preservation: int = Query(..., description="Preservation-note count the dialog showed"),
    heating: int = Query(..., description="Heating-note count the dialog showed"),
    links: int = Query(..., description="Link count the dialog showed"),
    db: Session = Depends(get_db),
):
    """Delete, with the counts the user was shown echoed back.

    The counts are REQUIRED parameters, not optional ones, so a caller that
    forgets them is a 422 rather than a silent unconfirmed delete. If either
    has moved since the dialog opened, this answers 409 carrying both numbers,
    and the dialog corrects itself in place rather than asking for a reload.

    It is an optimistic check and not a lock: nothing is held between the count
    and the delete. With one user the case it guards is a tab left open, which
    is the common one - a second person editing concurrently does not exist
    here.

    Children are not part of the count. They are RESTRICT, so an ingredient
    with children cannot be deleted at all, and that is a refusal rather than a
    number - the IntegrityError handler turns it into a 409 saying so.

    Recipe lines are RESTRICT too, but refused here, before the database is
    asked, so the 409 can name the recipes: `used_in` on the body is what the
    user has to change first. Lines naming a child do not block this - the
    child does, on its own.
    """
    ingredient = ingredients.get(db, ingredient_id)
    naming = recipes.recipes_naming_ingredient(db, ingredient_id)
    if naming:
        raise AppError(
            409,
            "A recipe still uses this ingredient; change or merge it there first.",
            used_in=[{"id": r.id, "display_name": r.display_name} for r in naming],
        )
    actual = ingredients.cascade_counts(db, ingredient_id)

    if actual["aliases"] != aliases:
        raise StaleCountError("aliases", "aliases", aliases, actual["aliases"])
    if actual["preservation"] != preservation:
        raise StaleCountError("preservation", "preservation notes", preservation, actual["preservation"])
    if actual["heating"] != heating:
        raise StaleCountError("heating", "heating notes", heating, actual["heating"])
    if actual["links"] != links:
        raise StaleCountError("links", "links", links, actual["links"])

    db.delete(ingredient)
    db.commit()
    return Response(status_code=204)


@edit.put("/{ingredient_id}/images", response_model=schemas.IngredientResponse)
def set_ingredient_images(
    ingredient_id: int,
    payload: list[schemas.ImageAttachmentIn],
    db: Session = Depends(get_db),
):
    """Replace the gallery, in order. Position 0 is the cover."""
    ingredient = ingredients.get(db, ingredient_id)
    images.set_images(db, ingredient, "images", IngredientImage, payload)
    return _full(db, ingredients.get(db, ingredient_id))


@edit.post("/{ingredient_id}/merge", response_model=schemas.IngredientResponse)
def merge_ingredient(ingredient_id: int, payload: schemas.MergeIn, db: Session = Depends(get_db)):
    """Merge this ingredient into `into` and delete it; answers the target.

    The fix for a duplicate, rather than deleting one of the two: every line,
    child and note the duplicate carries survives on the row that stays.

    `fingerprint` is the preview's. The plan is recomputed here and, if it is
    no longer the one the user confirmed, the merge is refused with the fresh
    preview on the body - the same stale-tab case `StaleCountError` guards on
    delete, for an action that drops more.
    """
    plan = ingredients.merge_plan(db, ingredient_id, payload.into)
    if plan.fingerprint() != payload.fingerprint:
        raise AppError(
            409,
            "This merge has changed since the preview. Check it and confirm again.",
            preview=_merge_preview(db, plan).model_dump(mode="json"),
        )
    return _full(db, ingredients.merge(db, plan))


@edit.post("/{ingredient_id}/labels/{label_id}", status_code=204)
def attach_label(ingredient_id: int, label_id: int, db: Session = Depends(get_db)):
    """A label of another library is 422, as it is in `label_ids`."""
    from app.models import Label

    ingredient = ingredients.get(db, ingredient_id)
    label = db.query(Label).filter(Label.id == label_id).one_or_none()
    if label is None:
        raise AppError(404, "No such label.")
    check_label_scope([label], "ingredient")
    if label not in ingredient.labels:
        ingredient.labels.append(label)
        db.commit()
    return Response(status_code=204)


@edit.delete("/{ingredient_id}/labels/{label_id}", status_code=204)
def detach_label(ingredient_id: int, label_id: int, db: Session = Depends(get_db)):
    ingredient = ingredients.get(db, ingredient_id)
    ingredient.labels = [label for label in ingredient.labels if label.id != label_id]
    db.commit()
    return Response(status_code=204)
