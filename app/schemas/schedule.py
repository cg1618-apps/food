"""The weekly schedule on the wire.

A day is written whole: `ScheduleDayIn` is everything the day holds, and what
it leaves out is cleared - a mark left out is false, a text left out is null.
Blank strings are null, a meal is keyed by its slot, and an unknown slot or
field is refused by `extra="forbid"` rather than dropped. Every date in a
requested range is answered, stored or not, so a `ScheduleDayResponse` with
every mark false and every text and meal null is an ordinary answer.
"""

import datetime as dt

from pydantic import BaseModel, ConfigDict, StrictBool, field_validator

from app.constants import MEAL_SLOTS
from app.schemas.recipe import DishRef, RecipeRef, _normalise


class MealItemIn(BaseModel):
    """A dish, a recipe of it, or a recipe alone - which names its dish."""

    model_config = ConfigDict(extra="forbid")

    dish_id: int | None = None
    recipe_id: int | None = None


class MealIn(BaseModel):
    """Free text and items, either or both - a meal with neither is not
    stored. The items' order is their position."""

    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    items: list[MealItemIn] = []

    @field_validator("text", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)


class ScheduleDayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Strict: "雞腿" is not a mark, and a string coerced to true would hide
    # a client that still sends the old text.
    to_buy: StrictBool = False
    thaw_morning: StrictBool = False
    thaw_noon: StrictBool = False
    thaw_evening: StrictBool = False
    fruit: str | None = None
    note: str | None = None
    # Keyed by slot; a slot left out or null is an empty meal.
    meals: dict[str, MealIn | None] = {}

    @field_validator("fruit", "note", mode="before")
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


class MealItemResponse(BaseModel):
    dish: DishRef
    recipe: RecipeRef | None = None


class MealResponse(BaseModel):
    text: str | None = None
    # In position order; empty when the meal is text alone.
    items: list[MealItemResponse] = []


class ScheduleDayResponse(BaseModel):
    date: dt.date
    # Monday 0 ... Sunday 6, as Python's date.weekday(); a week here runs
    # Saturday (5) to Friday (4).
    weekday: int
    to_buy: bool = False
    thaw_morning: bool = False
    thaw_noon: bool = False
    thaw_evening: bool = False
    fruit: str | None = None
    note: str | None = None
    # Every slot, in MEAL_SLOTS order; null where nothing is planned.
    meals: dict[str, MealResponse | None]
