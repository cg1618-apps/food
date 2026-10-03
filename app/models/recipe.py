"""The recipe library: the recipe, what it is made of, how it is made, and
where it came from. What is true of the dish whoever makes it - its names,
kind, course, region, labels - lives on the dish (`app/models/dish.py`).

One family, one file, as `ingredient.py` is. The gallery table is the exception
and lives in `image.py` beside `IngredientImage`, because the galleries share a
shape with each other more than with their owners.

Two directions of deletion meet here and they differ on purpose (the table is
in `docs/data-model.md`): what a recipe OWNS cascades with it; what it NAMES -
its dish, an ingredient, a sub-dish, a status, a source platform, an author, a
method, a piece of equipment, a 材料分組 or 步驟分組 value - is RESTRICT, so
nothing in use disappears from under a recipe.

A line's or a step's own group is the third direction: SET NULL, so a group
that goes takes no row with it - the row is ungrouped instead, which is what
the form's 移除分組 does too.
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


class Recipe(Base):
    """One specific way of making a dish - 照燒雞腿排 as one author makes it.

    The dish carries what is true of the dish whoever cooks it - its names,
    kind, course, region, labels; the recipe carries what this way of making
    it needs. A recipe's own `name` is optional and only says how it differs
    from its dish's other recipes; its display name falls back to the dish's.

    "Written up" is derived - at least one line or step - and never stored. A
    stored flag would disagree with the content the first time someone forgot
    to tick it.
    """

    __tablename__ = "recipe"

    id = Column(Integer, primary_key=True)

    # RESTRICT: a dish with recipes cannot be deleted from under them, and
    # deleting the last recipe of a dish leaves the dish.
    dish_id = Column(
        Integer, ForeignKey("dish.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name = Column(String, nullable=True)
    # No server default: which status comes first is the owner's data, so
    # `recipes.create` picks it, and the column only refuses a missing one.
    status_id = Column(
        Integer, ForeignKey("recipe_status.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Free text: "2-3 人", "1hr", "30m". Nothing computes with either.
    servings = Column(String, nullable=True)
    time = Column(String, nullable=True)

    storage_notes = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=get_taipei_now)
    updated_at = Column(DateTime, default=get_taipei_now, onupdate=get_taipei_now)

    dish = relationship("Dish", back_populates="recipes")
    status = relationship("RecipeStatus")

    sources = relationship(
        "RecipeSource",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeSource.sort_order",
    )
    # Every line and step of the recipe, grouped or not, in position order -
    # which is the order the page shows them: ungrouped first, then group by
    # group. The groups are their own lists; a row names its group.
    lines = relationship(
        "RecipeLine",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeLine.position",
    )
    steps = relationship(
        "RecipeStep",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeStep.position",
    )
    line_groups = relationship(
        "RecipeLineGroup",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeLineGroup.position",
    )
    step_groups = relationship(
        "RecipeStepGroup",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeStepGroup.position",
    )
    images = relationship(
        "RecipeImage",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeImage.position",
    )

    methods = relationship("CookingMethod", secondary="recipe_method")
    equipment = relationship("Equipment", secondary="recipe_equipment")

    @property
    def display_name(self) -> str:
        """The recipe's own name, else its dish's display name.

        "" rather than None when neither is there, as `NameFallbackMixin`
        does - a recipe not yet flushed may have no dish loaded.
        """
        if self.name and self.name.strip():
            return self.name
        return self.dish.display_name if self.dish is not None else ""


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

    `url` is optional because a book has none, and the author is optional
    because a page may have none worth naming. A row that is only a platform
    says nothing, hence the CHECK: an author, a link or a title.
    """

    __tablename__ = "recipe_source"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(
        Integer, ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform_id = Column(
        Integer,
        ForeignKey("source_platform.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    author_id = Column(
        Integer, ForeignKey("author.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    url = Column(String, nullable=True)
    title = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default=text("0"))

    recipe = relationship("Recipe", back_populates="sources")
    platform = relationship("SourcePlatform")
    author = relationship("Author")

    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(author_id, url, title) >= 1", name="ck_recipe_source_has_content"
        ),
    )


class RecipeLineGroup(Base, NameFallbackMixin):
    """One group of a recipe's ingredient lines - its 醬汁, its 主料.

    Real rows rather than a label on each line: a group exists on its own (an
    empty one is kept), has its own place in the recipe, and is renamed once.
    It names a 材料分組 value from 設定 or carries a one-off `name`, exactly
    one of the two. The write path stores a typed name that matches a value
    as that value, so the same group is never both.

    A recipe may not hold one group twice: unique on the value, and on the
    one-off name case-insensitively. Both uniques are NULLS DISTINCT, so the
    rows using the other arm never collide on the NULL.

    `display_name` is the value's, else the one-off name: the mixin reads
    `name_cn` and `name_en`, which are the value's here.
    """

    __tablename__ = "recipe_line_group"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(
        Integer, ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    line_group_id = Column(
        Integer, ForeignKey("line_group.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    name = Column(String, nullable=True)

    recipe = relationship("Recipe", back_populates="line_groups")
    # passive_deletes="all", as across every RESTRICT here.
    group = relationship("LineGroup", passive_deletes="all")

    __table_args__ = (
        UniqueConstraint("recipe_id", "position", name="uq_recipe_line_group_position"),
        UniqueConstraint("recipe_id", "line_group_id", name="uq_recipe_line_group_value"),
        Index("uq_recipe_line_group_name", "recipe_id", func.lower(name), unique=True),
        CheckConstraint(
            "num_nonnulls(line_group_id, name) = 1", name="ck_recipe_line_group_one_name"
        ),
    )

    @property
    def name_cn(self):
        return self.group.name_cn if self.group else self.name

    @property
    def name_en(self):
        return self.group.name_en if self.group else None


class RecipeStepGroup(Base, NameFallbackMixin):
    """One group of a recipe's steps - its 備料, its 烹飪. The same shape and
    rules as RecipeLineGroup, naming a 步驟分組 value instead."""

    __tablename__ = "recipe_step_group"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(
        Integer, ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    step_group_id = Column(
        Integer, ForeignKey("step_group.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    name = Column(String, nullable=True)

    recipe = relationship("Recipe", back_populates="step_groups")
    group = relationship("StepGroup", passive_deletes="all")

    __table_args__ = (
        UniqueConstraint("recipe_id", "position", name="uq_recipe_step_group_position"),
        UniqueConstraint("recipe_id", "step_group_id", name="uq_recipe_step_group_value"),
        Index("uq_recipe_step_group_name", "recipe_id", func.lower(name), unique=True),
        CheckConstraint(
            "num_nonnulls(step_group_id, name) = 1", name="ck_recipe_step_group_one_name"
        ),
    )

    @property
    def name_cn(self):
        return self.group.name_cn if self.group else self.name

    @property
    def name_en(self):
        return self.group.name_en if self.group else None


class RecipeLine(Base):
    """One ingredient line: an ingredient, or a dish - usually a sauce - never
    both. A line names the DISH, not one recipe of it: 照燒醬 is used, however
    it is made.

    Which kind of line it is comes from which column is set, never from a
    stored discriminator that could disagree with them.

    Nothing is unique on the ingredient - the same one may appear twice, once
    for the meat and once for the sauce - only on the position, which runs
    through the whole recipe in the order the page shows it (ungrouped lines
    first, then group by group), not restarting in each group. The nesting
    graph may not cycle and a recipe may not use its own dish; a CHECK sees one
    row and cannot see the recipe's dish, so the write path refuses both.
    """

    __tablename__ = "recipe_line"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(
        Integer, ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    # The recipe group the line sits in; null is ungrouped. SET NULL rather
    # than CASCADE: a group going never takes its lines with it (the module
    # docstring). The write path only ever names a group of the same recipe;
    # a single-column key cannot say so, and a composite one could not be
    # SET NULL without nulling recipe_id too.
    group_id = Column(
        Integer, ForeignKey("recipe_line_group.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ingredient_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    sub_dish_id = Column(
        Integer, ForeignKey("dish.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    amount = Column(String, nullable=True)
    note = Column(String, nullable=True)
    is_optional = Column(Boolean, nullable=False, server_default=text("false"))

    recipe = relationship("Recipe", back_populates="lines")
    group = relationship("RecipeLineGroup")
    # passive_deletes="all" on both, as across every RESTRICT here: the ORM
    # must not null the column before the DELETE, or the database never gets
    # to refuse and an ingredient in use disappears from under its recipes.
    ingredient = relationship("Ingredient", passive_deletes="all")
    sub_dish = relationship("Dish", passive_deletes="all")

    __table_args__ = (
        UniqueConstraint("recipe_id", "position", name="uq_recipe_line_position"),
        CheckConstraint(
            "num_nonnulls(ingredient_id, sub_dish_id) = 1", name="ck_recipe_line_one_target"
        ),
    )


class RecipeStep(Base):
    """One row of the method, in order: the position runs through the whole
    recipe as a line's does.

    The position is not the step's number. Only a `step`-kind row is
    numbered; an optional step and a note sit in the order unnumbered, so the
    number is counted by whoever draws the page, never stored.
    """

    __tablename__ = "recipe_step"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(
        Integer, ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    # As RecipeLine.group_id.
    group_id = Column(
        Integer, ForeignKey("recipe_step_group.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Validated against STEP_KINDS in the schema layer.
    kind = Column(String, nullable=False, server_default=text("'step'"))
    body = Column(Text, nullable=False)

    recipe = relationship("Recipe", back_populates="steps")
    group = relationship("RecipeStepGroup")

    __table_args__ = (
        UniqueConstraint("recipe_id", "position", name="uq_recipe_step_position"),
    )
