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
from app.models import Ingredient
from app.routing import read_router, write_router
from app.services import ingredients

router = read_router("ingredients", "Ingredients")
edit = write_router("ingredients", "Ingredients")


def _response(row: Ingredient) -> schemas.IngredientResponse:
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
        parent=schemas.IngredientSummary.model_validate(row.parent) if row.parent else None,
        children=[schemas.IngredientSummary.model_validate(c) for c in row.children],
        description=row.description,
        selection_notes=row.selection_notes,
        sourcing_notes=row.sourcing_notes,
        preservation_notes=row.preservation_notes,
        needs_detail=row.needs_detail,
        aliases=sorted(alias.value for alias in row.aliases),
        preservation=[
            schemas.PreservationResponse.model_validate(entry) for entry in row.preservation
        ],
        labels=[
            schemas.ingredient.LabelRef(id=label.id, display_name=label.display_name)
            for label in row.labels
        ],
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
    )
    return [schemas.IngredientSummary.model_validate(row) for row in rows]


@router.get("/{ingredient_id}", response_model=schemas.IngredientResponse)
def get_ingredient(ingredient_id: int, db: Session = Depends(get_db)):
    return _response(ingredients.get(db, ingredient_id))


@router.get("/{ingredient_id}/cascade", response_model=dict)
def cascade_preview(ingredient_id: int, db: Session = Depends(get_db)):
    """What deleting this would remove, for the confirmation dialog.

    Public because it is a read, and because the dialog that uses it is behind
    Access anyway. It returns counts, never rows.
    """
    ingredients.get(db, ingredient_id)
    counts = ingredients.cascade_counts(db, ingredient_id)
    counts["children"] = ingredients.child_count(db, ingredient_id)
    return counts


# ==========================================
# WRITES - behind Cloudflare Access
# ==========================================


@edit.post("", response_model=schemas.IngredientResponse, status_code=201)
def create_ingredient(payload: schemas.IngredientCreate, db: Session = Depends(get_db)):
    return _response(ingredients.create(db, payload))


@edit.patch("/{ingredient_id}", response_model=schemas.IngredientResponse)
def update_ingredient(
    ingredient_id: int, payload: schemas.IngredientUpdate, db: Session = Depends(get_db)
):
    return _response(ingredients.update(db, ingredient_id, payload))


@edit.delete("/{ingredient_id}", status_code=204)
def delete_ingredient(
    ingredient_id: int,
    aliases: int = Query(..., description="Alias count the dialog showed"),
    preservation: int = Query(..., description="Preservation-note count the dialog showed"),
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
    """
    ingredient = ingredients.get(db, ingredient_id)
    actual = ingredients.cascade_counts(db, ingredient_id)

    if actual["aliases"] != aliases:
        raise StaleCountError("aliases", aliases, actual["aliases"])
    if actual["preservation"] != preservation:
        raise StaleCountError("preservation notes", preservation, actual["preservation"])

    db.delete(ingredient)
    db.commit()
    return Response(status_code=204)


@edit.post("/{ingredient_id}/labels/{label_id}", status_code=204)
def attach_label(ingredient_id: int, label_id: int, db: Session = Depends(get_db)):
    from app.models import Label

    ingredient = ingredients.get(db, ingredient_id)
    label = db.query(Label).filter(Label.id == label_id).one_or_none()
    if label is None:
        raise AppError(404, "No such label.")
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
