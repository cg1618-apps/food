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

    # How good this one is, S to D - the Fruit sheet's grades. Used mostly on
    # varieties (愛文芒果 under 芒果). Validated against RATINGS.
    rating = Column(String, nullable=True)

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
    heating = relationship(
        "IngredientHeating",
        back_populates="ingredient",
        cascade="all, delete-orphan",
        order_by="IngredientHeating.sort_order",
    )
    links = relationship(
        "IngredientLink",
        back_populates="ingredient",
        cascade="all, delete-orphan",
        order_by="IngredientLink.sort_order",
    )
    images = relationship(
        "IngredientImage",
        back_populates="ingredient",
        cascade="all, delete-orphan",
        order_by="IngredientImage.position",
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
    """One row per state and WAY of keeping the thing.

    未使用 冷藏 3-5 天; 已開封 冷藏 1-2 天; 熟食 冷凍 2-3 月. The state axis comes
    from the reference sheet's Unused / Opened columns and its 熟肉 rows.

    The duration is a RANGE, both ends optional: the sheet states a range in
    almost every row, and module 1's single typical number would have meant
    inventing one. "infinite" and "see the date" are notes, with both ends
    null.
    """

    __tablename__ = "ingredient_preservation"

    id = Column(Integer, primary_key=True)
    ingredient_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Validated against PRESERVATION_STATES / PRESERVATION_METHODS in the
    # schema layer - see app/constants.py.
    state = Column(String, nullable=False, server_default=text("'unused'"))
    method = Column(String, nullable=False)
    duration_min_days = Column(Integer, nullable=True)
    duration_max_days = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default=text("0"))

    ingredient = relationship("Ingredient", back_populates="preservation")

    __table_args__ = (
        UniqueConstraint(
            "ingredient_id", "state", "method", name="uq_ingredient_preservation_state_method"
        ),
        CheckConstraint(
            "(duration_min_days IS NULL OR duration_min_days > 0) "
            "AND (duration_max_days IS NULL OR duration_max_days > 0)",
            name="ck_ingredient_preservation_duration_positive",
        ),
        CheckConstraint(
            "duration_min_days IS NULL OR duration_max_days IS NULL "
            "OR duration_min_days <= duration_max_days",
            name="ck_ingredient_preservation_duration_order",
        ),
    )


class IngredientHeating(Base):
    """How to heat or cook one thing quickly - the reference's 加熱 sheet.

    Not unique on method: 香腸 may be air-fried two ways. Temperature is
    stored in Celsius only; Fahrenheit is computed for display, because two
    stored temperatures can disagree and one cannot.
    """

    __tablename__ = "ingredient_heating"

    id = Column(Integer, primary_key=True)
    ingredient_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False, index=True
    )
    method_id = Column(
        Integer, ForeignKey("cooking_method.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    temperature_c = Column(Integer, nullable=True)
    duration = Column(String, nullable=True)
    preheat = Column(Boolean, nullable=False, server_default=text("false"))
    flip = Column(Boolean, nullable=False, server_default=text("false"))
    notes = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default=text("0"))

    ingredient = relationship("Ingredient", back_populates="heating")
    method = relationship("CookingMethod", passive_deletes="all")

    __table_args__ = (
        CheckConstraint(
            "temperature_c IS NULL OR temperature_c > 0",
            name="ck_ingredient_heating_temperature_positive",
        ),
    )


class IngredientLink(Base):
    """A reference link: where the selection or storage advice came from."""

    __tablename__ = "ingredient_link"

    id = Column(Integer, primary_key=True)
    ingredient_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url = Column(String, nullable=False)
    title = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default=text("0"))

    ingredient = relationship("Ingredient", back_populates="links")
