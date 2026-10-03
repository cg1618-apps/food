"""The weekly schedule. Reads are public; writes sit behind Access.

The read answers a range of dates - by default this week and next, Saturday
to Friday - with every date in it, stored or not. The write replaces one day
whole, and answers it as the read would.
"""

from datetime import date

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app import schemas
from app.constants import MEAL_SLOTS
from app.database import get_db
from app.models import ScheduleDay
from app.models.schedule import DAY_FIELDS
from app.routers.recipe import dish_ref, recipe_ref
from app.routing import read_router, write_router
from app.services import schedule

router = read_router("schedule", "Schedule")
edit = write_router("schedule", "Schedule")


def _day(day: date, row: ScheduleDay | None) -> schemas.ScheduleDayResponse:
    by_slot = {meal.slot: meal for meal in row.meals} if row else {}
    meals = {}
    for slot in MEAL_SLOTS:
        meal = by_slot.get(slot)
        meals[slot] = (
            schemas.MealResponse(
                text=meal.text,
                dish=dish_ref(meal.dish) if meal.dish else None,
                recipe=recipe_ref(meal.recipe) if meal.recipe else None,
            )
            if meal
            else None
        )
    fields = {field: getattr(row, field) if row else None for field in DAY_FIELDS}
    return schemas.ScheduleDayResponse(date=day, weekday=day.weekday(), meals=meals, **fields)


# ==========================================
# PUBLIC READS
# ==========================================


@router.get("", response_model=list[schemas.ScheduleDayResponse])
def read_schedule(
    start: date | None = Query(
        default=None, description="The first date; left out, this week's Saturday"
    ),
    days: int = Query(default=schedule.DEFAULT_DAYS, ge=1, le=schedule.MAX_DAYS),
    db: Session = Depends(get_db),
):
    """One entry per date from `start`, in order, stored or not: a bare array."""
    first = start if start is not None else schedule.week_start(schedule.today())
    return [_day(day, row) for day, row in schedule.days_in(db, first, days)]


# ==========================================
# WRITES - behind Cloudflare Access
# ==========================================


@edit.put("/{day}", response_model=schemas.ScheduleDayResponse)
def replace_day(day: date, payload: schemas.ScheduleDayIn, db: Session = Depends(get_db)):
    """Replace the whole day. What the body leaves out is cleared; a day left
    with nothing is deleted, and answered as an empty day."""
    schedule.replace_day(db, day, payload)
    db.expire_all()
    [(_, row)] = schedule.days_in(db, day, 1)
    return _day(day, row)
