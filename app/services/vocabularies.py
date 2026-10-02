"""How many rows use each vocabulary value - for the settings page and for the
409 a delete answers while a value is in use.

One function per vocabulary, registered in USAGE. Each counts exactly the
references that are RESTRICT in the schema, so the count is the number of
things that would stop the delete: a course counts the recipes filed in it and
not the recipes that merely serve as it, because those links CASCADE.
"""

from collections import Counter
from collections.abc import Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    CookingMethod,
    Equipment,
    IngredientHeating,
    Recipe,
    RecipeCourse,
    RecipeEquipment,
    RecipeMethod,
)


def _count(db: Session, column) -> Counter:
    return Counter(dict(db.query(column, func.count()).group_by(column).all()))


def _course_usage(db: Session) -> dict[int, int]:
    counts = _count(db, Recipe.course_id)
    counts.pop(None, None)
    return dict(counts)


def _cooking_method_usage(db: Session) -> dict[int, int]:
    return dict(_count(db, IngredientHeating.method_id) + _count(db, RecipeMethod.method_id))


def _equipment_usage(db: Session) -> dict[int, int]:
    return dict(_count(db, RecipeEquipment.equipment_id))


USAGE: dict[type, Callable[[Session], dict[int, int]]] = {
    RecipeCourse: _course_usage,
    CookingMethod: _cooking_method_usage,
    Equipment: _equipment_usage,
}


def usage(db: Session, model) -> dict[int, int]:
    return USAGE[model](db)
