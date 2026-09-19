"""The category tree, and the editor behind it.

The tree cannot be deferred to a later module: `ingredient.category_id` is NOT
NULL and the migration seeds exactly one category, so without somewhere to
create the rest, every ingredient in the app would be filed under 未分類
forever.
"""

from fastapi import Depends, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.errors import AppError
from app.models import Ingredient, IngredientCategory
from app.routing import read_router, write_router
from app.services.hierarchy import build_tree, check_parent

router = read_router("ingredient-categories", "Categories")
edit = write_router("ingredient-categories", "Categories")


def _counts(db: Session) -> dict[int, int]:
    """Ingredients per category, for every category, in one query.

    One GROUP BY rather than a count per node: the tree endpoint returns every
    category, so a per-node count would be a query per row - the N+1 that grows
    with the data and not with the code, which is why it survives review.
    """
    rows = (
        db.query(Ingredient.category_id, func.count(Ingredient.id))
        .group_by(Ingredient.category_id)
        .all()
    )
    return dict(rows)


@router.get("", response_model=list[schemas.CategoryNode])
def category_tree(db: Session = Depends(get_db)):
    """The whole tree, nested, in one response. A few dozen rows."""
    rows = db.query(IngredientCategory).all()
    return build_tree(rows, _counts(db), schemas.CategoryNode)


@edit.post("", response_model=schemas.CategoryResponse, status_code=201)
def create_category(payload: schemas.CategoryCreate, db: Session = Depends(get_db)):
    check_parent(db, IngredientCategory, None, payload.parent_id, "category")
    category = IngredientCategory(
        name_cn=payload.name_cn,
        name_en=payload.name_en,
        parent_id=payload.parent_id,
        sort_order=payload.sort_order,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return schemas.CategoryResponse.model_validate(category)


@edit.patch("/{category_id}", response_model=schemas.CategoryResponse)
def update_category(
    category_id: int, payload: schemas.CategoryUpdate, db: Session = Depends(get_db)
):
    category = db.query(IngredientCategory).filter_by(id=category_id).one_or_none()
    if category is None:
        raise AppError(404, "No such category.")

    changes = payload.model_dump(exclude_unset=True)
    if "parent_id" in changes:
        check_parent(db, IngredientCategory, category.id, changes["parent_id"], "category")

    for field, value in changes.items():
        setattr(category, field, value)

    if not any((category.name_cn, category.name_en)):
        raise AppError(422, "A category needs at least one name.")

    db.commit()
    db.refresh(category)
    return schemas.CategoryResponse.model_validate(category)


@edit.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    """Delete a category, if nothing is filed in it and nothing sits under it.

    No confirmation count here, deliberately: this delete cascades nothing.
    Both relationships are RESTRICT, so the answer is a refusal rather than a
    number, and a dialog offering "this will remove 12 ingredients" would be
    describing something that cannot happen.

    The fallback row is refused outright rather than left to the foreign keys,
    because it is reachable even when empty - and deleting it would leave a
    NOT NULL column with nowhere to point for every stub created afterwards.
    """
    category = db.query(IngredientCategory).filter_by(id=category_id).one_or_none()
    if category is None:
        raise AppError(404, "No such category.")
    if category.is_fallback:
        raise AppError(
            409,
            "That is the fallback category. New ingredients are filed there, so it "
            "cannot be removed.",
        )

    db.delete(category)
    db.commit()
    return Response(status_code=204)
