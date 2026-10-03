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
from app.models import Dish, Recipe, ScheduleDay, ScheduleMeal
from app.models.schedule import DAY_FIELDS

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
    rows = (
        db.query(ScheduleDay)
        .options(
            selectinload(ScheduleDay.meals).selectinload(ScheduleMeal.dish),
            selectinload(ScheduleDay.meals)
            .selectinload(ScheduleMeal.recipe)
            .selectinload(Recipe.dish),
        )
        .filter(ScheduleDay.date >= start, ScheduleDay.date < end)
        .all()
    )
    stored = {row.date: row for row in rows}
    return [(start + timedelta(days=i), stored.get(start + timedelta(days=i))) for i in range(days)]


def _resolve_meal(db: Session, slot: str, meal) -> dict | None:
    """The row values for one meal, or None when it is empty.

    A recipe given without a dish takes the recipe's dish; a recipe of a
    different dish than the one given is refused.
    """
    if meal is None or (meal.text is None and meal.dish_id is None and meal.recipe_id is None):
        return None
    dish_id = meal.dish_id
    if dish_id is not None and db.get(Dish, dish_id) is None:
        raise AppError(422, f"No such dish: {dish_id}.")
    if meal.recipe_id is not None:
        recipe = db.get(Recipe, meal.recipe_id)
        if recipe is None:
            raise AppError(422, f"No such recipe: {meal.recipe_id}.")
        if dish_id is None:
            dish_id = recipe.dish_id
        elif recipe.dish_id != dish_id:
            raise AppError(
                422,
                f"The {MEAL_SLOTS[slot]} recipe is not a recipe of that meal's dish.",
            )
    return {"slot": slot, "text": meal.text, "dish_id": dish_id, "recipe_id": meal.recipe_id}


def replace_day(db: Session, day: date, payload) -> None:
    """Make `day` hold exactly `payload`. Nothing left - no field and no
    meal - deletes the day's row instead of storing an empty one."""
    meals = [
        resolved
        for slot in MEAL_SLOTS
        if (resolved := _resolve_meal(db, slot, payload.meals.get(slot))) is not None
    ]
    fields = {field: getattr(payload, field) for field in DAY_FIELDS}

    row = db.get(ScheduleDay, day)
    if not meals and all(value is None for value in fields.values()):
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
    # kept never meets its old row in the unique constraint.
    row.meals = []
    db.flush()
    row.meals = [ScheduleMeal(**values) for values in meals]
    db.commit()


def meal_dates(db: Session, dish_id: int) -> list[date]:
    """The dates with a meal naming this dish, earliest first, each once."""
    rows = (
        db.query(ScheduleMeal.date)
        .filter(ScheduleMeal.dish_id == dish_id)
        .distinct()
        .order_by(ScheduleMeal.date)
        .all()
    )
    return [row.date for row in rows]
