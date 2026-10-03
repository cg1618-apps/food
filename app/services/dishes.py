"""Reading and writing dishes. The router does HTTP; this does the work.

A dish is what is true of a dish whoever cooks it - names, kind, course,
region, labels, serves-as, a description, a gallery - and its recipes are the
specific ways of making it. Writes validate everything before they change
anything, as `recipes` does.

"Used in" for a dish is the recipes with a line naming it, directly; there is
no reverse relationship from a dish to those lines, so it is a query here.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError
from app.models import (
    Dish,
    DishAlias,
    DishImage,
    DishLabel,
    Label,
    Recipe,
    RecipeCourse,
    RecipeImage,
    RecipeLine,
    RecipeSource,
    Region,
    ScheduleMeal,
)
from app.schemas.dish import LIST_FIELDS
from app.services import images
from app.services.lookup import fetch_all
from app.services.search import ESCAPE, contains

# The id lists a dish carries, the relationship each fills, the model it
# names, and the word a 422 uses for it.
_LINKED = {
    "serves_as_ids": ("serves_as", RecipeCourse, "course"),
    "label_ids": ("labels", Label, "label"),
}


def _recipe_rows():
    """What a dish's recipe list reads, per recipe - the library summary."""
    recipes = selectinload(Dish.recipes)
    return [
        recipes.selectinload(Recipe.status),
        recipes.selectinload(Recipe.methods),
        recipes.selectinload(Recipe.sources).selectinload(RecipeSource.author),
        recipes.selectinload(Recipe.images).selectinload(RecipeImage.image),
        recipes.selectinload(Recipe.lines),
        recipes.selectinload(Recipe.steps),
    ]


def _loaded(query):
    return query.options(
        selectinload(Dish.course),
        selectinload(Dish.region),
        selectinload(Dish.aliases),
        selectinload(Dish.labels),
        selectinload(Dish.serves_as),
        selectinload(Dish.images).selectinload(DishImage.image),
        *_recipe_rows(),
    )


def _summary_loaded(query):
    """Every relationship a library row reads, in one round trip each - the
    cover falls back to a recipe's, so recipes' galleries are loaded too."""
    return query.options(
        selectinload(Dish.course),
        selectinload(Dish.region),
        selectinload(Dish.labels),
        selectinload(Dish.images).selectinload(DishImage.image),
        selectinload(Dish.recipes).selectinload(Recipe.images).selectinload(RecipeImage.image),
    )


def get(db: Session, dish_id: int) -> Dish:
    row = _loaded(db.query(Dish)).filter(Dish.id == dish_id).one_or_none()
    if row is None:
        raise AppError(404, "No such dish.")
    return row


def cover(dish: Dish):
    """The dish's first picture; else the first cover among its recipes, in
    recipe order - a dish shows something before it has pictures of its own."""
    if dish.images:
        return images.cover(dish.images)
    for recipe in dish.recipes:
        if recipe.images:
            return images.cover(recipe.images)
    return None


def used_in(db: Session, dish_id: int) -> list[Recipe]:
    """Distinct recipes with a line naming this dish DIRECTLY.

    Depth zero: a recipe using a sauce whose recipe uses this one is not
    counted - the depth "used in" has for an ingredient too.
    """
    rows = (
        db.query(Recipe)
        .options(selectinload(Recipe.dish))
        .filter(
            Recipe.id.in_(
                select(RecipeLine.recipe_id).where(RecipeLine.sub_dish_id == dish_id).scalar_subquery()
            )
        )
        .all()
    )
    return sorted(rows, key=lambda r: (r.display_name.casefold(), r.id))


def by_name(db: Session, names: list[str]) -> Dish | None:
    """A dish answering to any of `names`, in a name slot or an alias.

    Case-insensitive and exact. A near match is the typeahead's job, before
    the user chooses "new"; here only an exact one is reused - the oldest,
    when names are shared.
    """
    lowered = [n.lower() for n in names]
    alias_match = (
        select(DishAlias.dish_id).where(func.lower(DishAlias.value).in_(lowered)).scalar_subquery()
    )
    return (
        db.query(Dish)
        .filter(
            or_(
                func.lower(Dish.name_cn).in_(lowered),
                func.lower(Dish.name_en).in_(lowered),
                func.lower(Dish.name_alt).in_(lowered),
                Dish.id.in_(alias_match),
            )
        )
        .order_by(Dish.id)
        .first()
    )


def matches(q: str):
    """The clause a search term matches a dish by: any name slot or alias."""
    term = contains(q)
    alias_match = (
        select(DishAlias.dish_id)
        .where(func.lower(DishAlias.value).like(func.lower(term), escape=ESCAPE))
        .scalar_subquery()
    )
    return or_(
        Dish.name_cn.ilike(term, escape=ESCAPE),
        Dish.name_en.ilike(term, escape=ESCAPE),
        Dish.name_alt.ilike(term, escape=ESCAPE),
        Dish.id.in_(alias_match),
    )


def search(
    db: Session,
    q: str | None = None,
    kind: list[str] | None = None,
    course_id: list[int] | None = None,
    region_id: list[int] | None = None,
    label_id: list[int] | None = None,
) -> list[Dish]:
    """The library list. Each multi-valued filter means "any of" its values;
    different filters narrow each other. Subqueries rather than joins, for the
    reason `ingredients.search` gives."""
    query = _summary_loaded(db.query(Dish))
    if q:
        query = query.filter(matches(q))
    if kind:
        query = query.filter(Dish.kind.in_(kind))
    if course_id:
        query = query.filter(Dish.course_id.in_(course_id))
    if region_id:
        query = query.filter(Dish.region_id.in_(region_id))
    if label_id:
        query = query.filter(
            Dish.id.in_(select(DishLabel.dish_id).where(DishLabel.label_id.in_(label_id)).scalar_subquery())
        )
    rows = query.all()
    rows.sort(key=lambda r: (r.display_name.casefold(), r.id))
    return rows


# --- writing ------------------------------------------------------------------


def _check_scalars(db: Session, scalars: dict) -> None:
    if scalars.get("course_id") is not None:
        fetch_all(db, RecipeCourse, [scalars["course_id"]], "course")
    if scalars.get("region_id") is not None:
        fetch_all(db, Region, [scalars["region_id"]], "region")


def _check_and_fetch(db: Session, lists: dict) -> dict:
    return {
        field: fetch_all(db, model, lists[field], what)
        for field, (_, model, what) in _LINKED.items()
        if lists.get(field) is not None
    }


def _apply_aliases(dish: Dish, values: list[str]) -> None:
    """Reconciled by value, as `ingredients._apply_aliases` and for its reason."""
    wanted = list(dict.fromkeys(values))
    dish.aliases = [row for row in dish.aliases if row.value in wanted]
    kept = {row.value for row in dish.aliases}
    dish.aliases.extend(DishAlias(value=v) for v in wanted if v not in kept)


def _apply_lists(dish: Dish, lists: dict, fetched: dict) -> None:
    if lists.get("aliases") is not None:
        _apply_aliases(dish, lists["aliases"])
    for field, rows in fetched.items():
        setattr(dish, _LINKED[field][0], rows)


def create(db: Session, payload) -> Dish:
    lists = {field: getattr(payload, field) for field in LIST_FIELDS}
    scalars = payload.model_dump(exclude=set(LIST_FIELDS))
    _check_scalars(db, scalars)
    fetched = _check_and_fetch(db, lists)

    dish = Dish(**scalars)
    db.add(dish)
    db.flush()
    _apply_lists(dish, lists, fetched)
    db.commit()
    return get(db, dish.id)


def update(db: Session, dish_id: int, payload) -> Dish:
    dish = get(db, dish_id)
    sent = payload.model_fields_set
    lists = {field: getattr(payload, field) for field in LIST_FIELDS if field in sent}
    scalars = {field: getattr(payload, field) for field in sent if field not in LIST_FIELDS}

    # Against the MERGED row, before anything is assigned: assigning first
    # would let an autoflush write the nameless row.
    merged = [scalars.get(f, getattr(dish, f)) for f in ("name_cn", "name_en", "name_alt")]
    if not any(merged):
        raise AppError(422, "A dish needs at least one name.")
    _check_scalars(db, scalars)
    fetched = _check_and_fetch(db, lists)

    for field, value in scalars.items():
        setattr(dish, field, value)
    _apply_lists(dish, lists, fetched)
    db.commit()
    return get(db, dish_id)


def cascade_counts(db: Session, dish_id: int) -> dict[str, int]:
    """What the delete dialog shows: the aliases a delete takes with it, and
    the three counts that refuse it - recipes of the dish, recipes using it,
    and meals on the schedule naming it.

    Serves-as and label links cascade too but are not counted, as for a
    recipe; gallery rows go and the pictures stay.
    """
    return {
        "aliases": db.query(DishAlias).filter(DishAlias.dish_id == dish_id).count(),
        "recipes": db.query(Recipe).filter(Recipe.dish_id == dish_id).count(),
        "used_in": len(used_in(db, dish_id)),
        "meals": db.query(ScheduleMeal).filter(ScheduleMeal.dish_id == dish_id).count(),
    }
