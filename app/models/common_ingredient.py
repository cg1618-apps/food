"""常用食材: the ingredients the recipe form offers as one-tap chips.

A list of its own rather than a flag or a label on the ingredient, because it
is ORDERED - the owner arranges the chips - and an order is a position in one
list, not a property of one row. One row per listed ingredient; the ingredient
is the key, so nothing can be listed twice.
"""

from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.database import Base


class CommonIngredient(Base):
    """CASCADE: an ingredient deleted leaves the list. A merge moves the
    source's entry to the target first (app/services/ingredients.py)."""

    __tablename__ = "common_ingredient"

    ingredient_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="CASCADE"), primary_key=True
    )
    sort_order = Column(Integer, nullable=False)

    ingredient = relationship("Ingredient", passive_deletes="all")
