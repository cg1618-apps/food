"""常用食材: the ingredients the recipe form offers as one-tap chips, ungrouped
or in the owner's named groups (肉, 調味料 …).

A list of its own rather than a flag or a label on the ingredient, because it
is ORDERED - the owner arranges the chips - and an order is a position in one
list, not a property of one row. One row per listed ingredient; the ingredient
is the key, so nothing can be listed twice, in one group or across them.

The groups are 常用食材's own, not 設定's 材料分組: they arrange shortcuts,
not a recipe's lines, and the owner keeps the two apart
(docs/notes/decisions.md).
"""

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base


class CommonIngredientGroup(Base):
    """One named group of chips. Ordered by `sort_order`; the name is required
    and unique in any case, as a vocabulary's is."""

    __tablename__ = "common_ingredient_group"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="ck_common_ingredient_group_has_a_name"),
        Index("uq_common_ingredient_group_name", func.lower(name), unique=True),
    )


class CommonIngredient(Base):
    """CASCADE on the ingredient: an ingredient deleted leaves the list. A
    merge moves the source's entry to the target first
    (app/services/ingredients.py), group and place with it.

    SET NULL on the group: a group deleted leaves its chips, ungrouped.
    `sort_order` is the chip's place within its group, or within 未分組 when
    `group_id` is null."""

    __tablename__ = "common_ingredient"

    ingredient_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="CASCADE"), primary_key=True
    )
    group_id = Column(
        Integer,
        ForeignKey("common_ingredient_group.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sort_order = Column(Integer, nullable=False)

    ingredient = relationship("Ingredient", passive_deletes="all")
