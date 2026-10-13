"""Small managed vocabularies: courses, regions, recipe statuses, source
platforms, cooking methods, equipment, authors, and the groups a recipe's
ingredient lines and steps sit in.

Nine tables with one shape, declared once through a mixin. They are tables
rather than lists in `app/constants.py` because the owner edits them - renaming
煮 to 水煮 must be one row, not a deploy. The closed lists in constants are the
ones the app's own logic branches on (storage state, dish kind); these are
the ones it only displays and filters by.

`declared_attr` builds each table's constraints from its own name and its own
copied columns: `cls.name_cn` inside it is the subclass's column, not the
mixin's, which is what lets one definition produce nine correctly-bound
expression indexes.

An author alone carries more than the shared shape - a remark and a child
table of links (`author_link`) - declared on its own class below.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import declared_attr, relationship

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
    """主食, 配菜, 湯 … - where a dish sits in a meal. Named for the recipe it
    was first filed on; it files a dish now (`dish.course_id`)."""

    __tablename__ = "recipe_course"


class Region(Base, VocabularyMixin):
    """台式, 中式, 日式 … - where a dish comes from. Hand-ordered, as courses
    are: the order is the one the forms and filters offer them in."""

    __tablename__ = "region"


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

    The one vocabulary with more than names: a remark (`notes`) and links -
    a channel, a blog - shown above the recipe library when it is filtered
    to this author.
    """

    __tablename__ = "author"

    # Line breaks kept; blank is stored as NULL by the schema layer.
    notes = Column(Text, nullable=True)

    links = relationship(
        "AuthorLink",
        back_populates="author",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AuthorLink.position",
    )


class AuthorLink(Base):
    """tbd_link's shape and rules, on an author. CASCADE: an author deleted
    takes its links. Replaced wholesale on a save, so `position` is the order
    sent and carries no unique constraint - one would collide with the rows
    being replaced inside the same flush."""

    __tablename__ = "author_link"

    id = Column(Integer, primary_key=True)
    author_id = Column(
        Integer, ForeignKey("author.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    # http or https only, normalised in the schema layer: a bare host is
    # stored with https:// in front of it.
    url = Column(String, nullable=False)
    label = Column(String, nullable=True)

    author = relationship("Author", back_populates="links")

    __table_args__ = (CheckConstraint("btrim(url) <> ''", name="ck_author_link_has_a_url"),)


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
