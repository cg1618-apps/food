"""The recipe library: the recipe, what it is made of, how it is made, where it
came from, and the vocabularies it is tagged with.

One family, one file, as `ingredient.py` is. The gallery table is the exception
and lives in `image.py` beside `IngredientImage`, because the galleries share a
shape with each other more than with their owners.

Three directions of deletion meet here and they differ on purpose (the table is
in `docs/data-model.md`): what a recipe OWNS cascades with it; what it NAMES -
an ingredient, a sub-recipe, a course, a method, a piece of equipment - is
RESTRICT, so nothing in use disappears from under a recipe; and its versions
are SET NULL, because a version is a complete recipe in its own right.
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


class Recipe(Base, NameFallbackMixin):
    """One recipe - a dish, or a base used inside other dishes.

    Names are NOT unique, unlike every other named table here: versions of one
    dish share its name, and that is the ordinary case rather than a clash.

    "Written up" is derived - at least one line or step - and never stored. A
    stored flag would disagree with the content the first time someone forgot
    to tick it.
    """

    __tablename__ = "recipe"

    id = Column(Integer, primary_key=True)

    name_cn = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    name_alt = Column(String, nullable=True)

    # Validated against RECIPE_KINDS / RECIPE_STATUSES in the schema layer.
    kind = Column(String, nullable=False, server_default=text("'dish'"))
    course_id = Column(
        Integer, ForeignKey("recipe_course.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # One level deep - a version may not have versions, nor point at one - and
    # that is enforced on the write path, because a CHECK cannot see another
    # row. The CHECK below only covers the case a single row can state.
    variant_of_id = Column(
        Integer, ForeignKey("recipe.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status = Column(String, nullable=False, server_default=text("'want_to_try'"))

    # Free text: "2-3 人", "1hr", "30m". Nothing computes with either.
    servings = Column(String, nullable=True)
    time = Column(String, nullable=True)

    description = Column(Text, nullable=True)
    storage_notes = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=get_taipei_now)
    updated_at = Column(DateTime, default=get_taipei_now, onupdate=get_taipei_now)

    course = relationship("RecipeCourse")
    variant_of = relationship("Recipe", remote_side=[id], back_populates="variants")
    # passive_deletes=True so deleting the original leaves the database to
    # apply SET NULL to versions the session never loaded, rather than the ORM
    # selecting every one of them first to null the column itself.
    variants = relationship("Recipe", back_populates="variant_of", passive_deletes=True)

    aliases = relationship(
        "RecipeAlias", back_populates="recipe", cascade="all, delete-orphan"
    )
    sources = relationship(
        "RecipeSource",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeSource.sort_order",
    )
    # foreign_keys is required: recipe_line points at recipe twice, once as
    # its owner and once as the base it names.
    lines = relationship(
        "RecipeLine",
        back_populates="recipe",
        foreign_keys="RecipeLine.recipe_id",
        cascade="all, delete-orphan",
        order_by="RecipeLine.position",
    )
    steps = relationship(
        "RecipeStep",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeStep.position",
    )
    images = relationship(
        "RecipeImage",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeImage.position",
    )

    labels = relationship("Label", secondary="recipe_label")
    methods = relationship("CookingMethod", secondary="recipe_method")
    equipment = relationship("Equipment", secondary="recipe_equipment")
    serves_as = relationship("RecipeCourse", secondary="recipe_serves_as")

    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(name_cn, name_en, name_alt) >= 1", name="ck_recipe_has_a_name"
        ),
        CheckConstraint(
            "variant_of_id IS NULL OR variant_of_id <> id",
            name="ck_recipe_not_its_own_version",
        ),
    )


class RecipeAlias(Base):
    """Anything you might type to find a recipe. Never displayed.

    As `IngredientAlias`, and for the same reasons: a real table rather than an
    array, and unique per recipe rather than globally.
    """

    __tablename__ = "recipe_alias"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(
        Integer, ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value = Column(String, nullable=False)

    recipe = relationship("Recipe", back_populates="aliases")

    __table_args__ = (
        UniqueConstraint("recipe_id", "value", name="uq_recipe_alias"),
        Index("ix_recipe_alias_lookup", func.lower(value)),
    )


class RecipeServesAs(Base):
    """The other courses a dish can stand in for - a soup that is a meal.

    Both sides CASCADE. Unlike `recipe.course_id`, a serves-as link is not a
    reason to refuse deleting a course: it is a hint, not where the recipe is
    filed. It may repeat the recipe's own course; the UI does not offer that.
    """

    __tablename__ = "recipe_serves_as"

    recipe_id = Column(Integer, ForeignKey("recipe.id", ondelete="CASCADE"), primary_key=True)
    course_id = Column(
        Integer, ForeignKey("recipe_course.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class RecipeLabel(Base):
    """Both sides CASCADE, as `ingredient_label` - one label behaviour for
    every owner."""

    __tablename__ = "recipe_label"

    recipe_id = Column(Integer, ForeignKey("recipe.id", ondelete="CASCADE"), primary_key=True)
    # Indexed on its own: the composite key leads with recipe_id, so it cannot
    # serve "which recipes carry this label" - nor the cascade from the label.
    label_id = Column(
        Integer, ForeignKey("label.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class RecipeMethod(Base):
    """Method side RESTRICT: deleting a method in use is a 409 with a count,
    answered by the vocabulary router before the database is asked."""

    __tablename__ = "recipe_method"

    recipe_id = Column(Integer, ForeignKey("recipe.id", ondelete="CASCADE"), primary_key=True)
    method_id = Column(
        Integer, ForeignKey("cooking_method.id", ondelete="RESTRICT"), primary_key=True, index=True
    )


class RecipeEquipment(Base):
    """Equipment side RESTRICT, as `recipe_method`."""

    __tablename__ = "recipe_equipment"

    recipe_id = Column(Integer, ForeignKey("recipe.id", ondelete="CASCADE"), primary_key=True)
    equipment_id = Column(
        Integer, ForeignKey("equipment.id", ondelete="RESTRICT"), primary_key=True, index=True
    )


class RecipeSource(Base):
    """Where the recipe came from: a video, a page, a book.

    `url` is optional because a book has none; `creator` is free text, and its
    distinct values are what suggestions and the filter are built from. A row
    that is only a platform says nothing, hence the CHECK.
    """

    __tablename__ = "recipe_source"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(
        Integer, ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Validated against SOURCE_PLATFORMS in the schema layer.
    platform = Column(String, nullable=False)
    creator = Column(String, nullable=True)
    url = Column(String, nullable=True)
    title = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default=text("0"))

    recipe = relationship("Recipe", back_populates="sources")

    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(creator, url, title) >= 1", name="ck_recipe_source_has_content"
        ),
    )


class RecipeLine(Base):
    """One ingredient line: an ingredient, or another recipe, never both.

    Which kind of line it is comes from which column is set, never from a
    stored discriminator that could disagree with them.

    Nothing is unique on the ingredient - the same one may appear twice, once
    for the meat and once for the sauce - only on the position. The nesting
    graph may not cycle; a CHECK sees one row, so it refuses only the direct
    case (a line naming its own recipe) and the write path refuses the rest.
    """

    __tablename__ = "recipe_line"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(
        Integer, ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    # A free-text heading the line sits under - 醬汁, 醃料. Lines sharing one
    # are grouped by the UI; nothing else reads it.
    section = Column(String, nullable=True)
    ingredient_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    sub_recipe_id = Column(
        Integer, ForeignKey("recipe.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    amount = Column(String, nullable=True)
    note = Column(String, nullable=True)
    is_optional = Column(Boolean, nullable=False, server_default=text("false"))

    recipe = relationship("Recipe", back_populates="lines", foreign_keys=[recipe_id])
    # passive_deletes="all" on both, as across every RESTRICT here: the ORM
    # must not null the column before the DELETE, or the database never gets
    # to refuse and an ingredient in use disappears from under its recipes.
    ingredient = relationship("Ingredient", passive_deletes="all")
    sub_recipe = relationship("Recipe", foreign_keys=[sub_recipe_id], passive_deletes="all")

    __table_args__ = (
        UniqueConstraint("recipe_id", "position", name="uq_recipe_line_position"),
        CheckConstraint(
            "num_nonnulls(ingredient_id, sub_recipe_id) = 1", name="ck_recipe_line_one_target"
        ),
        CheckConstraint(
            "sub_recipe_id IS NULL OR sub_recipe_id <> recipe_id",
            name="ck_recipe_line_not_itself",
        ),
    )


class RecipeStep(Base):
    """One step of the method, in order."""

    __tablename__ = "recipe_step"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(
        Integer, ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    section = Column(String, nullable=True)
    body = Column(Text, nullable=False)

    recipe = relationship("Recipe", back_populates="steps")

    __table_args__ = (
        UniqueConstraint("recipe_id", "position", name="uq_recipe_step_position"),
    )
