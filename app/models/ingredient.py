"""The ingredient library: the row, its category tree, its aliases, its keeping.

Four tables in one file because they are one family and only ever change
together - media's convention, where `staff.py` holds Person, PersonRole,
Studio, Publisher and PublisherScope.
"""

from sqlalchemy import (
    Boolean,
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


class IngredientCategory(Base, NameFallbackMixin):
    """A tree. An ingredient may point at any node, not only at a leaf.

    Depth is unbounded and there is no CHECK that could make it otherwise: "no
    cycles" needs a recursive query, so the guard lives on the write path, not
    here. Requiring a leaf was rejected - you often know a thing is 醬油
    without knowing which sub-type, and demanding a leaf means inventing 其他
    nodes under every branch.
    """

    __tablename__ = "ingredient_category"

    id = Column(Integer, primary_key=True)
    parent_id = Column(
        Integer, ForeignKey("ingredient_category.id", ondelete="RESTRICT"), nullable=True
    )

    name_cn = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default=text("0"))

    # Exactly one row may set this, and stub ingredients created from a recipe
    # line are filed here. That is what lets `ingredient.category_id` be NOT
    # NULL without a required category interrupting recipe writing to ask a
    # taxonomy question. The partial unique index below is what enforces "one",
    # rather than every future caller remembering to check.
    is_fallback = Column(Boolean, nullable=False, server_default=text("false"))

    parent = relationship("IngredientCategory", remote_side=[id], back_populates="children")
    # passive_deletes="all" on both: without it SQLAlchemy helpfully sets the
    # child's foreign key to NULL before issuing the DELETE, so the database
    # never gets to apply RESTRICT. A re-parenting that the schema forbids
    # then succeeds through the ORM and fails only through raw SQL.
    children = relationship(
        "IngredientCategory", back_populates="parent", passive_deletes="all"
    )
    ingredients = relationship(
        "Ingredient", back_populates="category", passive_deletes="all"
    )

    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(name_cn, name_en) >= 1", name="ck_ingredient_category_has_a_name"
        ),
        # Two siblings may not share a Chinese name. Expressed as an index
        # rather than a UniqueConstraint for two reasons a plain
        # UNIQUE(parent_id, name_cn) gets wrong:
        #
        #   coalesce(parent_id, 0) - a NULL parent means "top level", and
        #   under the default NULLS DISTINCT two root categories both named
        #   醬油 would not collide at all, which is the case most likely to
        #   happen.
        #
        #   WHERE name_cn IS NOT NULL - so that any number of siblings may
        #   have no Chinese name. Without it, the second such sibling is
        #   refused for having nothing rather than for clashing.
        Index(
            "uq_ingredient_category_sibling_cn",
            text("coalesce(parent_id, 0)"),
            func.lower(name_cn),
            unique=True,
            postgresql_where=name_cn.isnot(None),
        ),
        Index(
            "uq_ingredient_category_one_fallback",
            "is_fallback",
            unique=True,
            postgresql_where=text("is_fallback"),
        ),
    )


class Ingredient(Base, NameFallbackMixin):
    """One thing you cook with.

    `parent_id` is an ordinary ingredient, not an abstract grouping node: 醬油
    is itself stockable, cookable and citable on a recipe line, and happens to
    have 生抽 and 老抽 beneath it. That is the whole reason this column exists -
    a recipe line may name either level, and module 4's "what can I cook" has to
    resolve between them in BOTH directions. Do not add an "is a group" flag;
    there are no groups.
    """

    __tablename__ = "ingredient"

    id = Column(Integer, primary_key=True)

    name_cn = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    # A formal alternative - another script, a romanisation - that is worth
    # SHOWING on the detail page. Anything you might merely TYPE to find the
    # row is an alias and belongs in ingredient_alias. Without that line the
    # two hold the same strings within a month.
    name_alt = Column(String, nullable=True)

    category_id = Column(
        Integer,
        ForeignKey("ingredient_category.id", ondelete="RESTRICT"),
        nullable=False,
    )
    parent_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="RESTRICT"), nullable=True
    )

    description = Column(Text, nullable=True)
    selection_notes = Column(Text, nullable=True)
    sourcing_notes = Column(Text, nullable=True)
    # Keeping advice that belongs to no single method. Per-method advice, and
    # the time it lasts, live in ingredient_preservation.
    preservation_notes = Column(Text, nullable=True)

    # Explicit, never derived from "has no notes": salt needs no selection
    # guide, and a derived flag could never be told so.
    needs_detail = Column(Boolean, nullable=False, server_default=text("false"))

    created_at = Column(DateTime, default=get_taipei_now)
    updated_at = Column(DateTime, default=get_taipei_now, onupdate=get_taipei_now)

    category = relationship("IngredientCategory", back_populates="ingredients")
    parent = relationship("Ingredient", remote_side=[id], back_populates="children")
    children = relationship("Ingredient", back_populates="parent", passive_deletes="all")
    aliases = relationship(
        "IngredientAlias", back_populates="ingredient", cascade="all, delete-orphan"
    )
    preservation = relationship(
        "IngredientPreservation",
        back_populates="ingredient",
        cascade="all, delete-orphan",
        order_by="IngredientPreservation.sort_order",
    )
    labels = relationship("Label", secondary="ingredient_label", back_populates="ingredients")

    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(name_cn, name_en, name_alt) >= 1",
            name="ck_ingredient_has_a_name",
        ),
        # One name slot, one index, and the default NULLS DISTINCT is the
        # CORRECT behaviour here - it is what lets any number of ingredients
        # have no English name while no two share one.
        #
        # This is where media's scar does NOT transfer, and the difference is
        # easy to miss. Its `uq_person_name` spans several name columns at
        # once, and there a NULL in any column makes the whole constraint
        # inert, so it needs NULLS NOT DISTINCT. Adding that to a
        # SINGLE-column index does the opposite: it makes NULL equal to NULL,
        # and the second row with no name_en is refused. Most rows here will
        # have only name_cn, so that reads as "the database is broken".
        #
        # lower() rather than a citext column: one fewer extension, and the
        # comparison is visible in the index definition rather than in a type.
        Index("uq_ingredient_name_cn", func.lower(name_cn), unique=True),
        Index("uq_ingredient_name_en", func.lower(name_en), unique=True),
        # name_alt is deliberately NOT unique. It is a catch-all slot, not a
        # key, and two ingredients may legitimately share a romanisation.
    )


class IngredientAlias(Base):
    """Anything you might type to find an ingredient. Never displayed.

    A child table rather than an array column: media carries no
    `postgresql.ARRAY` anywhere and records replacing list-in-a-column with a
    real table twice as a regret, because a list in a column cannot be indexed,
    joined or constrained. This one is all three.

    Uniqueness is per ingredient, not global. Two different ingredients may
    legitimately answer to overlapping strings, and a global constraint would
    refuse the second one at the moment of typing it. Module 2's stub creation
    warns about a likely duplicate instead of refusing it.
    """

    __tablename__ = "ingredient_alias"

    id = Column(Integer, primary_key=True)
    ingredient_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value = Column(String, nullable=False)

    ingredient = relationship("Ingredient", back_populates="aliases")

    __table_args__ = (
        UniqueConstraint("ingredient_id", "value", name="uq_ingredient_alias"),
        Index("ix_ingredient_alias_lookup", func.lower(value)),
    )


class IngredientPreservation(Base):
    """One row per WAY of keeping the thing. 冷藏 5 天; 冷凍 90 天; 乾燥, no time.

    `duration_days` is a single typical number, not a range, and the range goes
    in `notes` ("3-5 天, less once cut"). The integer is what a future "what is
    about to go off" view can compute with; the prose is what is actually true.
    Storing only the prose would have made that view impossible, and storing
    only a range would have made every row two fields of ceremony.
    """

    __tablename__ = "ingredient_preservation"

    id = Column(Integer, primary_key=True)
    ingredient_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Validated against PRESERVATION_METHODS in the schema layer, not by a
    # Postgres enum - see app/constants.py.
    method = Column(String, nullable=False)
    duration_days = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default=text("0"))

    ingredient = relationship("Ingredient", back_populates="preservation")

    __table_args__ = (
        UniqueConstraint("ingredient_id", "method", name="uq_ingredient_preservation_method"),
        CheckConstraint(
            "duration_days IS NULL OR duration_days > 0",
            name="ck_ingredient_preservation_duration_positive",
        ),
    )
