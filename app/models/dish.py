"""The dish library: a dish or a sauce in general - 照燒雞腿排, 照燒醬 - which
the recipes are specific ways of making.

One table for both kinds. A dish and a sauce carry the same fields at the same
level, and `kind` keeps them apart so the libraries can be filtered now and
split later without a migration (docs/notes/decisions.md).

What a dish OWNS - aliases, serves-as and label links, gallery rows -
cascades with it. What it NAMES - a course, a region - is RESTRICT. What names
IT - a recipe's `dish_id`, a recipe line's `sub_dish_id`, a scheduled meal's
`dish_id` - is RESTRICT too, so a dish with recipes, one a recipe uses as an
ingredient, or one on the schedule cannot go from under them; the API refuses
first, naming them.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base, get_taipei_now
from app.models.base import NameFallbackMixin


class Dish(Base, NameFallbackMixin):
    """One dish or sauce, whatever recipe makes it.

    Names are NOT unique, as recipe names were not: two dishes may share a
    name, and the migration that created this table could produce two from two
    unrelated recipes of one name. A name typed into the recipe form reuses an
    existing dish answering to it exactly, which is what keeps the ordinary
    case to one row.
    """

    __tablename__ = "dish"

    id = Column(Integer, primary_key=True)

    name_cn = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    name_alt = Column(String, nullable=True)

    # Validated against DISH_KINDS in the schema layer.
    kind = Column(String, nullable=False, server_default=text("'dish'"))
    course_id = Column(
        Integer, ForeignKey("recipe_course.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    region_id = Column(
        Integer, ForeignKey("region.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=get_taipei_now)
    updated_at = Column(DateTime, default=get_taipei_now, onupdate=get_taipei_now)

    course = relationship("RecipeCourse")
    region = relationship("Region")
    aliases = relationship("DishAlias", back_populates="dish", cascade="all, delete-orphan")
    images = relationship(
        "DishImage",
        back_populates="dish",
        cascade="all, delete-orphan",
        order_by="DishImage.position",
    )
    # passive_deletes="all": a dish's recipes are RESTRICT, so the ORM must
    # never null their dish_id before the DELETE - the database refuses.
    recipes = relationship(
        "Recipe", back_populates="dish", passive_deletes="all", order_by="Recipe.id"
    )

    labels = relationship("Label", secondary="dish_label")
    serves_as = relationship("RecipeCourse", secondary="dish_serves_as")

    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(name_cn, name_en, name_alt) >= 1", name="ck_dish_has_a_name"
        ),
    )


class DishAlias(Base):
    """Anything you might type to find a dish. Never displayed.

    As `IngredientAlias`: a real table rather than an array, and unique per
    dish rather than globally.
    """

    __tablename__ = "dish_alias"

    id = Column(Integer, primary_key=True)
    dish_id = Column(Integer, ForeignKey("dish.id", ondelete="CASCADE"), nullable=False, index=True)
    value = Column(String, nullable=False)

    dish = relationship("Dish", back_populates="aliases")

    __table_args__ = (
        UniqueConstraint("dish_id", "value", name="uq_dish_alias"),
        Index("ix_dish_alias_lookup", func.lower(value)),
    )


class DishServesAs(Base):
    """The other courses a dish can stand in for - a soup that is a meal.

    Both sides CASCADE. Unlike `dish.course_id`, a serves-as link is not a
    reason to refuse deleting a course: it is a hint, not where the dish is
    filed.
    """

    __tablename__ = "dish_serves_as"

    dish_id = Column(Integer, ForeignKey("dish.id", ondelete="CASCADE"), primary_key=True)
    course_id = Column(
        Integer, ForeignKey("recipe_course.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class DishLabel(Base):
    """Both sides CASCADE, as `ingredient_label` - one label behaviour for
    every owner."""

    __tablename__ = "dish_label"

    dish_id = Column(Integer, ForeignKey("dish.id", ondelete="CASCADE"), primary_key=True)
    # Indexed on its own: the composite key leads with dish_id, so it cannot
    # serve "which dishes carry this label" - nor the cascade from the label.
    label_id = Column(
        Integer, ForeignKey("label.id", ondelete="CASCADE"), primary_key=True, index=True
    )
