"""Reading and writing the weekly schedule. The router does HTTP; this does
the work.

A week runs Saturday to Friday, as the owner's sheet does. Dates are local
calendar dates with no time and no zone: the box and the one person who uses
this are in the same timezone (Asia/Taipei), so "today" is the date there, as
every timestamp here is (`app.database.get_taipei_now`). The frontend always
sends the range it wants; the server's default is only for a bare request.

A day is written whole. Validation happens before anything changes, so a
refused save leaves the stored day exactly as it was.
"""

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session, selectinload

from app.constants import MEAL_SLOTS
from app.database import TAIPEI
from app.errors import AppError
from app.models import Dish, Recipe, ScheduleDay, ScheduleMeal, ScheduleMealItem
from app.models.schedule import DAY_FIELDS, DAY_FLAGS, DAY_TEXTS

SATURDAY = 5  # date.weekday(): Monday 0 ... Sunday 6
DEFAULT_DAYS = 14  # this week and next, as the sheet shows them
MAX_DAYS = 62


def today() -> date:
    """The calendar date in the owner's timezone. A function so tests can
    pin it."""
    return datetime.now(TAIPEI).date()


def week_start(day: date) -> date:
    """The Saturday on or before `day` - the first day of its week."""
    return day - timedelta(days=(day.weekday() - SATURDAY) % 7)


def days_in(db: Session, start: date, days: int) -> list[tuple[date, ScheduleDay | None]]:
    """Every date from `start` for `days` days, each with its stored row or
    None - a date nobody wrote anything for has no row."""
    end = start + timedelta(days=days)
    items = selectinload(ScheduleDay.meals).selectinload(ScheduleMeal.items)
    rows = (
        db.query(ScheduleDay)
        .options(
            items.selectinload(ScheduleMealItem.dish),
            items.selectinload(ScheduleMealItem.recipe).selectinload(Recipe.dish),
        )
        .filter(ScheduleDay.date >= start, ScheduleDay.date < end)
        .all()
    )
    stored = {row.date: row for row in rows}
    return [(start + timedelta(days=i), stored.get(start + timedelta(days=i))) for i in range(days)]


def _resolve_item(db: Session, label: str, item) -> tuple[int, int | None]:
    """One item's (dish_id, recipe_id). A recipe given without a dish takes
    the recipe's dish; a recipe of a different dish than the one given is
    refused, and so is an item naming neither."""
    dish_id = item.dish_id
    if dish_id is None and item.recipe_id is None:
        raise AppError(422, f"An item of the {label} meal names no dish.")
    if dish_id is not None and db.get(Dish, dish_id) is None:
        raise AppError(422, f"No such dish: {dish_id}.")
    if item.recipe_id is not None:
        recipe = db.get(Recipe, item.recipe_id)
        if recipe is None:
            raise AppError(422, f"No such recipe: {item.recipe_id}.")
        if dish_id is None:
            dish_id = recipe.dish_id
        elif recipe.dish_id != dish_id:
            raise AppError(422, f"A {label} recipe is not a recipe of its item's dish.")
    return dish_id, item.recipe_id


def _resolve_meal(db: Session, slot: str, meal) -> dict | None:
    """The row values for one meal, or None when it is empty.

    The same dish twice is allowed only with different recipes: the same
    dish and the same recipe (or no recipe) twice in one meal says nothing
    the first one did not, and is refused rather than silently merged.
    """
    if meal is None or (meal.text is None and not meal.items):
        return None
    label = MEAL_SLOTS[slot]
    items = [_resolve_item(db, label, item) for item in meal.items]
    if len(set(items)) != len(items):
        raise AppError(422, f"The {label} meal names the same dish and recipe twice.")
    return {"slot": slot, "text": meal.text, "items": items}


def replace_day(db: Session, day: date, payload) -> None:
    """Make `day` hold exactly `payload`. Nothing left - no mark, no text and
    no meal - deletes the day's row instead of storing an empty one."""
    meals = [
        resolved
        for slot in MEAL_SLOTS
        if (resolved := _resolve_meal(db, slot, payload.meals.get(slot))) is not None
    ]
    fields = {field: getattr(payload, field) for field in DAY_FIELDS}

    row = db.get(ScheduleDay, day)
    if not meals and not any(fields[flag] for flag in DAY_FLAGS) and all(
        fields[name] is None for name in DAY_TEXTS
    ):
        if row is not None:
            db.delete(row)
        db.commit()
        return

    if row is None:
        row = ScheduleDay(date=day)
        db.add(row)
    for field, value in fields.items():
        setattr(row, field, value)
    # Cleared and flushed before the new meals are added, so a slot that is
    # kept never meets its old row in the unique constraint; the items go
    # with their meals.
    row.meals = []
    db.flush()
    row.meals = [
        ScheduleMeal(
            slot=meal["slot"],
            text=meal["text"],
            items=[
                ScheduleMealItem(position=position, dish_id=dish_id, recipe_id=recipe_id)
                for position, (dish_id, recipe_id) in enumerate(meal["items"])
            ],
        )
        for meal in meals
    ]
    db.commit()


def meal_dates(db: Session, dish_id: int) -> list[date]:
    """The dates with a meal item naming this dish, earliest first, each
    once however many items name it that day."""
    rows = (
        db.query(ScheduleMeal.date)
        .join(ScheduleMealItem, ScheduleMealItem.meal_id == ScheduleMeal.id)
        .filter(ScheduleMealItem.dish_id == dish_id)
        .distinct()
        .order_by(ScheduleMeal.date)
        .all()
    )
    return [row.date for row in rows]
