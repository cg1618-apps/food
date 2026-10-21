"""常用食材: the chips the recipe form offers, ungrouped and in groups.

One read and one write. The write replaces the whole structure, so adding,
removing and reordering a chip, and adding, renaming, reordering and deleting
a group, are each one call carrying the structure as it should now be.
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.routing import read_router, write_router
from app.services import common_ingredients

router = read_router("common-ingredients", "Common ingredients")
edit = write_router("common-ingredients", "Common ingredients")


def _chips(rows) -> list[schemas.IngredientRef]:
    return [
        schemas.IngredientRef(
            id=row.ingredient.id,
            display_name=row.ingredient.display_name,
            needs_detail=row.ingredient.needs_detail,
        )
        for row in rows
    ]


def _response(structure) -> schemas.CommonIngredientsResponse:
    ungrouped, groups = structure
    return schemas.CommonIngredientsResponse(
        ungrouped=_chips(ungrouped),
        groups=[
            schemas.CommonIngredientGroupResponse(id=group.id, name=group.name, ingredients=_chips(rows))
            for group, rows in groups
        ],
    )


@router.get("", response_model=schemas.CommonIngredientsResponse)
def list_common_ingredients(db: Session = Depends(get_db)):
    return _response(common_ingredients.listed(db))


@edit.put("", response_model=schemas.CommonIngredientsResponse)
def replace_common_ingredients(
    payload: schemas.CommonIngredientsIn, db: Session = Depends(get_db)
):
    """Replace the structure with the one sent, in that order; answers it.

    An ingredient named twice anywhere, an id naming no ingredient or no
    group, a group sent twice, and a blank or repeated group name are each a
    422 and change nothing.
    """
    return _response(common_ingredients.replace(db, payload))
