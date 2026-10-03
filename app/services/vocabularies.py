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
    Author,
    CookingMethod,
    Equipment,
    IngredientHeating,
    LineGroup,
    Recipe,
    RecipeCourse,
    RecipeEquipment,
    RecipeLineGroup,
    RecipeMethod,
    RecipeSource,
    RecipeStatus,
    RecipeStepGroup,
    SourcePlatform,
    StepGroup,
)


def _count(db: Session, column) -> Counter:
    return Counter(dict(db.query(column, func.count()).group_by(column).all()))


def _course_usage(db: Session) -> dict[int, int]:
    counts = _count(db, Recipe.course_id)
    counts.pop(None, None)
    return dict(counts)


def _status_usage(db: Session) -> dict[int, int]:
    return dict(_count(db, Recipe.status_id))


def _platform_usage(db: Session) -> dict[int, int]:
    """Sources, not recipes: two sources from one book are two rows that would
    each stop the delete."""
    return dict(_count(db, RecipeSource.platform_id))


def _author_usage(db: Session) -> dict[int, int]:
    """Sources, as a platform's: a source with no author counts for nobody."""
    counts = _count(db, RecipeSource.author_id)
    counts.pop(None, None)
    return dict(counts)


def _nonnull(db: Session, column) -> dict[int, int]:
    counts = _count(db, column)
    counts.pop(None, None)
    return dict(counts)


def _line_group_usage(db: Session) -> dict[int, int]:
    """Recipe groups naming the value - one per recipe, since a recipe may
    not hold a group twice. A group with a one-off name counts for nothing."""
    return _nonnull(db, RecipeLineGroup.line_group_id)


def _step_group_usage(db: Session) -> dict[int, int]:
    """As a line group's."""
    return _nonnull(db, RecipeStepGroup.step_group_id)


def _cooking_method_usage(db: Session) -> dict[int, int]:
    return dict(_count(db, IngredientHeating.method_id) + _count(db, RecipeMethod.method_id))


def _equipment_usage(db: Session) -> dict[int, int]:
    return dict(_count(db, RecipeEquipment.equipment_id))


USAGE: dict[type, Callable[[Session], dict[int, int]]] = {
    RecipeCourse: _course_usage,
    RecipeStatus: _status_usage,
    SourcePlatform: _platform_usage,
    CookingMethod: _cooking_method_usage,
    Equipment: _equipment_usage,
    Author: _author_usage,
    LineGroup: _line_group_usage,
    StepGroup: _step_group_usage,
}


def usage(db: Session, model) -> dict[int, int]:
    return USAGE[model](db)
