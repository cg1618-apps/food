"""The weekly schedule: what is planned for each calendar date.

A `schedule_day` is one date's plain fields - what to buy, what to take out of
the freezer in the morning, at noon and in the evening, the fruit, a note -
and a `schedule_meal` is one of its four meals (MEAL_SLOTS). A date nobody has
written anything for has no row: the API answers every date in a range and
fills the missing ones with nulls, and a save that leaves a day or a meal
empty deletes its row rather than storing nothing.

A meal NAMES a dish and a recipe; it owns neither. The dish is RESTRICT, so a
dish on the schedule cannot go from under it - the API refuses first, naming
the dates. The recipe is SET NULL: a recipe is one way of making the dish, and
when it goes the meal still says what was planned.
"""

from sqlalchemy import Column, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base

DAY_FIELDS = ("to_buy", "thaw_morning", "thaw_noon", "thaw_evening", "fruit", "note")


class ScheduleDay(Base):
    """One calendar date. The date is the key: there is one row per date at
    most, and nothing else would identify it."""

    __tablename__ = "schedule_day"

    date = Column(Date, primary_key=True)

    to_buy = Column(Text, nullable=True)  # 要買?
    thaw_morning = Column(Text, nullable=True)  # 早退冰?
    thaw_noon = Column(Text, nullable=True)  # 中退冰?
    thaw_evening = Column(Text, nullable=True)  # 晚退冰?
    fruit = Column(Text, nullable=True)  # 水果
    note = Column(Text, nullable=True)  # 備註

    meals = relationship(
        "ScheduleMeal",
        back_populates="day",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ScheduleMeal(Base):
    """One meal of one day: free text, a dish, a recipe of that dish - any of
    them, at least one (an empty meal is not stored).

    That the recipe is one of the dish's is a rule across two tables, which a
    CHECK cannot see; `app/services/schedule.py` enforces it.
    """

    __tablename__ = "schedule_meal"

    id = Column(Integer, primary_key=True)
    date = Column(
        Date, ForeignKey("schedule_day.date", ondelete="CASCADE"), nullable=False
    )
    # Validated against MEAL_SLOTS in the schema layer.
    slot = Column(String, nullable=False)
    text = Column(Text, nullable=True)
    dish_id = Column(
        Integer, ForeignKey("dish.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    recipe_id = Column(
        Integer, ForeignKey("recipe.id", ondelete="SET NULL"), nullable=True, index=True
    )

    day = relationship("ScheduleDay", back_populates="meals")
    dish = relationship("Dish")
    recipe = relationship("Recipe")

    __table_args__ = (UniqueConstraint("date", "slot", name="uq_schedule_meal_slot"),)
