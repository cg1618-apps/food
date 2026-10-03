"""常用食材: reading the ordered list, and replacing it whole."""

from sqlalchemy.orm import Session, joinedload

from app.errors import AppError
from app.models import CommonIngredient, Ingredient
from app.services.lookup import fetch_all


def listed(db: Session) -> list[CommonIngredient]:
    return (
        db.query(CommonIngredient)
        .options(joinedload(CommonIngredient.ingredient))
        .order_by(CommonIngredient.sort_order, CommonIngredient.ingredient_id)
        .all()
    )


def replace(db: Session, ingredient_ids: list[int]) -> list[CommonIngredient]:
    """Make the list exactly `ingredient_ids`, numbered 0, 1, 2 … in that order.

    A repeat is refused rather than collapsed: the list is the order the owner
    arranged, and a payload naming one ingredient twice is a client that has
    lost track of it - quietly keeping the first would save an order nobody
    sent. Both refusals come before anything is written.
    """
    if len(set(ingredient_ids)) != len(ingredient_ids):
        raise AppError(422, "An ingredient can be on the list only once.")
    fetch_all(db, Ingredient, ingredient_ids, "ingredient")

    db.query(CommonIngredient).delete(synchronize_session="fetch")
    db.add_all(
        CommonIngredient(ingredient_id=ingredient_id, sort_order=position)
        for position, ingredient_id in enumerate(ingredient_ids)
    )
    db.commit()
    return listed(db)
