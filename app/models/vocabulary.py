"""Small managed vocabularies: recipe courses, cooking methods, equipment.

Three tables with one shape, declared once through a mixin. They are tables
rather than lists in `app/constants.py` because the owner edits them - renaming
煮 to 水煮 must be one row, not a deploy. The closed lists in constants are the
ones the app's own logic branches on (storage state, recipe status); these are
the ones it only displays and filters by.

`declared_attr` builds each table's constraints from its own name and its own
copied columns: `cls.name_cn` inside it is the subclass's column, not the
mixin's, which is what lets one definition produce three correctly-bound
expression indexes.
"""

from sqlalchemy import CheckConstraint, Column, Index, Integer, String, func, text
from sqlalchemy.orm import declared_attr

from app.database import Base
from app.models.base import NameFallbackMixin


class VocabularyMixin(NameFallbackMixin):
    id = Column(Integer, primary_key=True)
    name_cn = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default=text("0"))

    @declared_attr.directive
    def __table_args__(cls):
        table = cls.__tablename__
        return (
            CheckConstraint(
                "num_nonnulls(name_cn, name_en) >= 1", name=f"ck_{table}_has_a_name"
            ),
            # Default NULLS DISTINCT, deliberately - the long note in
            # app/models/ingredient.py applies unchanged.
            Index(f"uq_{table}_name_cn", func.lower(cls.name_cn), unique=True),
            Index(f"uq_{table}_name_en", func.lower(cls.name_en), unique=True),
        )


class RecipeCourse(Base, VocabularyMixin):
    """主食, 配菜, 湯 … - where a dish sits in a meal."""

    __tablename__ = "recipe_course"


class CookingMethod(Base, VocabularyMixin):
    """煮, 煎, 氣炸 … - shared by recipes and the ingredient heating guide."""

    __tablename__ = "cooking_method"


class Equipment(Base, VocabularyMixin):
    """鍋子, 平底鍋, 氣炸鍋 …"""

    __tablename__ = "equipment"
