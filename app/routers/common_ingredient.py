"""常用食材: the list the recipe form's chips are drawn from.

One read and one write. The write replaces the whole list, so adding, removing
and reordering are each one call carrying the list as it should now be.
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import CommonIngredient
from app.routing import read_router, write_router
from app.services import common_ingredients

router = read_router("common-ingredients", "Common ingredients")
edit = write_router("common-ingredients", "Common ingredients")


def _response(row: CommonIngredient) -> schemas.CommonIngredientResponse:
    ingredient = row.ingredient
    return schemas.CommonIngredientResponse(
        ingredient=schemas.IngredientRef(
            id=ingredient.id,
            display_name=ingredient.display_name,
            needs_detail=ingredient.needs_detail,
        ),
        sort_order=row.sort_order,
    )


@router.get("", response_model=list[schemas.CommonIngredientResponse])
def list_common_ingredients(db: Session = Depends(get_db)):
    return [_response(row) for row in common_ingredients.listed(db)]


@edit.put("", response_model=list[schemas.CommonIngredientResponse])
def replace_common_ingredients(
    payload: schemas.CommonIngredientsIn, db: Session = Depends(get_db)
):
    """Replace the list with `ingredient_ids`, in that order; answers the list.

    An id naming no ingredient, or one named twice, is a 422 and changes
    nothing.
    """
    return [_response(row) for row in common_ingredients.replace(db, payload.ingredient_ids)]
