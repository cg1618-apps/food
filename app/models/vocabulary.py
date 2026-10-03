"""Small managed vocabularies: recipe courses, recipe statuses, source
platforms, cooking methods, equipment, authors, and the groups a recipe's
ingredient lines and steps sit in.

Eight tables with one shape, declared once through a mixin. They are tables
rather than lists in `app/constants.py` because the owner edits them - renaming
煮 to 水煮 must be one row, not a deploy. The closed lists in constants are the
ones the app's own logic branches on (storage state, recipe kind); these are
the ones it only displays and filters by.

`declared_attr` builds each table's constraints from its own name and its own
copied columns: `cls.name_cn` inside it is the subclass's column, not the
mixin's, which is what lets one definition produce eight correctly-bound
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


class RecipeStatus(Base, VocabularyMixin):
    """想試, 可煮, 常煮 … - how far a recipe has got from "saw it somewhere" to
    "cook it every week". The first in sort order is what a recipe saved
    without one is given."""

    __tablename__ = "recipe_status"


class SourcePlatform(Base, VocabularyMixin):
    """YouTube, 網站, 書 … - where one recipe source was found."""

    __tablename__ = "source_platform"


class CookingMethod(Base, VocabularyMixin):
    """煮, 煎, 氣炸 … - shared by recipes and the ingredient heating guide."""

    __tablename__ = "cooking_method"


class Equipment(Base, VocabularyMixin):
    """鍋子, 平底鍋, 氣炸鍋 …"""

    __tablename__ = "equipment"


class Author(Base, VocabularyMixin):
    """阿基師, 詹姆士, Babish … - who made a recipe source.

    Listed by name, never hand-ordered: every author is created with
    sort_order 0, so the factory's (sort_order, name) order is name order.
    Grows from the recipe form as much as from 設定 - a name typed into a
    source that no author answers to is created by the save.
    """

    __tablename__ = "author"


class LineGroup(Base, VocabularyMixin):
    """主料, 配料, 調味料 … - the 材料分組 a recipe's ingredient lines are
    grouped under. A recipe may also use a one-off group name that is not one
    of these (`recipe_line_group.name`)."""

    __tablename__ = "line_group"


class StepGroup(Base, VocabularyMixin):
    """備料, 烹飪, 醬汁 … - the 步驟分組 a recipe's steps are grouped under,
    a separate list from LineGroup: what groups ingredients is rarely what
    groups the method. One-off names as LineGroup."""

    __tablename__ = "step_group"
