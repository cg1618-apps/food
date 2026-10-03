"""The weekly schedule: what is planned for each calendar date.

A `schedule_day` is one date's plain fields - four marks (to buy, take out of
the freezer in the morning, at noon, in the evening) that are true or false,
and two texts, the fruit and a note - and a `schedule_meal` is one of its four
meals (MEAL_SLOTS). A date nobody has written anything for has no row: the API
answers every date in a range and fills the missing ones with false and null,
and a save that leaves a day or a meal empty deletes its row rather than
storing nothing.

A meal is free text and any number of items. A `schedule_meal_item` NAMES a
dish and optionally one recipe of it; it owns neither. The dish is RESTRICT,
so a dish on the schedule cannot go from under it - the API refuses first,
naming the dates. The recipe is SET NULL: a recipe is one way of making the
dish, and when it goes the item still says what was planned.
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base

DAY_FLAGS = ("to_buy", "thaw_morning", "thaw_noon", "thaw_evening")
DAY_TEXTS = ("fruit", "note")
DAY_FIELDS = DAY_FLAGS + DAY_TEXTS


def _flag() -> Column:
    return Column(Boolean, nullable=False, default=False, server_default=text("false"))


class ScheduleDay(Base):
    """One calendar date. The date is the key: there is one row per date at
    most, and nothing else would identify it."""

    __tablename__ = "schedule_day"

    date = Column(Date, primary_key=True)

    to_buy = _flag()  # 要買?
    thaw_morning = _flag()  # 早退冰?
    thaw_noon = _flag()  # 中退冰?
    thaw_evening = _flag()  # 晚退冰?
    fruit = Column(Text, nullable=True)  # 水果
    note = Column(Text, nullable=True)  # 備註

    meals = relationship(
        "ScheduleMeal",
        back_populates="day",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ScheduleMeal(Base):
    """One meal of one day: free text, items, or both - at least one (an
    empty meal is not stored)."""

    __tablename__ = "schedule_meal"

    id = Column(Integer, primary_key=True)
    date = Column(
        Date, ForeignKey("schedule_day.date", ondelete="CASCADE"), nullable=False
    )
    # Validated against MEAL_SLOTS in the schema layer.
    slot = Column(String, nullable=False)
    text = Column(Text, nullable=True)

    day = relationship("ScheduleDay", back_populates="meals")
    items = relationship(
        "ScheduleMealItem",
        back_populates="meal",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ScheduleMealItem.position",
    )

    __table_args__ = (UniqueConstraint("date", "slot", name="uq_schedule_meal_slot"),)


class ScheduleMealItem(Base):
    """One dish of a meal, optionally with one of its recipes, at a position.

    That the recipe is one of the dish's, and that no meal holds the same dish
    and recipe twice, are rules a CHECK cannot see - the first spans two
    tables, the second treats a NULL recipe as a value; `app/services/schedule.py`
    enforces both.
    """

    __tablename__ = "schedule_meal_item"

    id = Column(Integer, primary_key=True)
    meal_id = Column(
        Integer, ForeignKey("schedule_meal.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    dish_id = Column(
        Integer, ForeignKey("dish.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    recipe_id = Column(
        Integer, ForeignKey("recipe.id", ondelete="SET NULL"), nullable=True, index=True
    )

    meal = relationship("ScheduleMeal", back_populates="items")
    dish = relationship("Dish")
    recipe = relationship("Recipe")

    __table_args__ = (
        UniqueConstraint("meal_id", "position", name="uq_schedule_meal_item_position"),
    )
