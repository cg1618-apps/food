"""Cross-cutting tags. 辛, 素, 常備, 貴.

A label is not a category. A category says where a thing sits in one taxonomy
and every ingredient has exactly one; a label says something true about it that
cuts across the tree, and an ingredient may carry any number or none. Merging
the two would mean either a second tree or an ingredient with several
categories, and both were rejected.

Its own table rather than free strings on the ingredient, so that renaming 常備
to 常備品 is one row rather than a search-and-replace that misses the typos.
"""

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import NameFallbackMixin


class Label(Base, NameFallbackMixin):
    """Two name slots, not three: a tag has no formal alternative form."""

    __tablename__ = "label"

    id = Column(Integer, primary_key=True)
    name_cn = Column(String, nullable=True)
    name_en = Column(String, nullable=True)

    ingredients = relationship(
        "Ingredient", secondary="ingredient_label", back_populates="labels"
    )

    __table_args__ = (
        CheckConstraint("num_nonnulls(name_cn, name_en) >= 1", name="ck_label_has_a_name"),
        # Default NULLS DISTINCT, deliberately - see the long note in
        # app/models/ingredient.py. Any number of labels may have no English
        # name; no two may share one.
        Index("uq_label_name_cn", func.lower(name_cn), unique=True),
        Index("uq_label_name_en", func.lower(name_en), unique=True),
    )


class IngredientLabel(Base):
    """The link table. Both sides CASCADE - a link has no life of its own."""

    __tablename__ = "ingredient_label"

    ingredient_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="CASCADE"), primary_key=True
    )
    label_id = Column(Integer, ForeignKey("label.id", ondelete="CASCADE"), primary_key=True)
