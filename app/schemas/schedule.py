"""The weekly schedule on the wire.

A day is written whole: `ScheduleDayIn` is everything the day holds, and what
it leaves out is cleared. Blank strings are null, a meal is keyed by its slot,
and an unknown slot or field is refused by `extra="forbid"` rather than
dropped. Every date in a requested range is answered, stored or not, so a
`ScheduleDayResponse` with every field null is an ordinary answer.
"""

import datetime as dt

from pydantic import BaseModel, ConfigDict, field_validator

from app.constants import MEAL_SLOTS
from app.schemas.recipe import DishRef, RecipeRef, _normalise


class MealIn(BaseModel):
    """Any of the three, or none - a meal with none is not stored. A recipe
    with no dish takes the recipe's dish."""

    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    dish_id: int | None = None
    recipe_id: int | None = None

    @field_validator("text", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)


class ScheduleDayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_buy: str | None = None
    thaw_morning: str | None = None
    thaw_noon: str | None = None
    thaw_evening: str | None = None
    fruit: str | None = None
    note: str | None = None
    # Keyed by slot; a slot left out or null is an empty meal.
    meals: dict[str, MealIn | None] = {}

    @field_validator(
        "to_buy", "thaw_morning", "thaw_noon", "thaw_evening", "fruit", "note", mode="before"
    )
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)

    @field_validator("meals")
    @classmethod
    def slots_are_known(cls, value: dict):
        unknown = [slot for slot in value if slot not in MEAL_SLOTS]
        if unknown:
            raise ValueError(f"A meal slot is one of {', '.join(MEAL_SLOTS)}")
        return value


class MealResponse(BaseModel):
    text: str | None = None
    dish: DishRef | None = None
    recipe: RecipeRef | None = None


class ScheduleDayResponse(BaseModel):
    date: dt.date
    # Monday 0 ... Sunday 6, as Python's date.weekday(); a week here runs
    # Saturday (5) to Friday (4).
    weekday: int
    to_buy: str | None = None
    thaw_morning: str | None = None
    thaw_noon: str | None = None
    thaw_evening: str | None = None
    fruit: str | None = None
    note: str | None = None
    # Every slot, in MEAL_SLOTS order; null where nothing is planned.
    meals: dict[str, MealResponse | None]
