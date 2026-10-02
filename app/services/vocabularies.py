"""How many rows use each vocabulary value - for the settings page and for the
409 a delete answers while a value is in use.

One function per vocabulary, registered in USAGE. Plan 2 adds the recipe link
tables to these counters; a vocabulary with no counter yet reports zero rather
than being special-cased by its router.
"""

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.models import CookingMethod, Equipment, RecipeCourse


def _cooking_method_usage(db: Session) -> dict[int, int]:
    from sqlalchemy import func

    from app.models import IngredientHeating

    rows = (
        db.query(IngredientHeating.method_id, func.count(IngredientHeating.id))
        .group_by(IngredientHeating.method_id)
        .all()
    )
    return dict(rows)


def _nothing_yet(db: Session) -> dict[int, int]:
    return {}


USAGE: dict[type, Callable[[Session], dict[int, int]]] = {
    RecipeCourse: _nothing_yet,
    CookingMethod: _cooking_method_usage,
    Equipment: _nothing_yet,
}


def usage(db: Session, model) -> dict[int, int]:
    return USAGE[model](db)
