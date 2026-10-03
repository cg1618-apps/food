"""Every model, imported here so string relationships resolve.

SQLAlchemy resolves `relationship("Ingredient")` by name against a registry
that only holds classes which have actually been imported. Importing one model
module on its own therefore works until it points at a table nobody imported,
and then fails at first use rather than at import - so everything is imported
here and every caller reaches models through this package.

Alembic's autogenerate reads `Base.metadata`, which is populated by the same
imports; a model missing from this file is a table missing from the diff.
"""

from app.models.common_ingredient import CommonIngredient
from app.models.dish import Dish, DishAlias, DishLabel, DishServesAs
from app.models.image import DishImage, Image, IngredientImage, KitchenNoteImage, RecipeImage
from app.models.ingredient import (
    Ingredient,
    IngredientAlias,
    IngredientCategory,
    IngredientHeating,
    IngredientLink,
    IngredientPreservation,
)
from app.models.kitchen_note import KitchenNote, KitchenNoteLabel
from app.models.label import IngredientLabel, Label
from app.models.recipe import (
    Recipe,
    RecipeEquipment,
    RecipeLine,
    RecipeLineGroup,
    RecipeMethod,
    RecipeSource,
    RecipeStep,
    RecipeStepGroup,
)
from app.models.recipe_template import RecipeTemplate
from app.models.schedule import ScheduleDay, ScheduleMeal, ScheduleMealItem
from app.models.tbd import TbdEntry, TbdLink
from app.models.vocabulary import (
    Author,
    CookingMethod,
    Equipment,
    LineGroup,
    RecipeCourse,
    RecipeStatus,
    Region,
    SourcePlatform,
    StepGroup,
)

__all__ = [
    "Author",
    "CommonIngredient",
    "CookingMethod",
    "Dish",
    "DishAlias",
    "DishImage",
    "DishLabel",
    "DishServesAs",
    "Equipment",
    "Image",
    "Ingredient",
    "IngredientAlias",
    "IngredientCategory",
    "IngredientHeating",
    "IngredientImage",
    "IngredientLabel",
    "IngredientLink",
    "IngredientPreservation",
    "KitchenNote",
    "KitchenNoteImage",
    "KitchenNoteLabel",
    "Label",
    "LineGroup",
    "Recipe",
    "RecipeCourse",
    "RecipeEquipment",
    "RecipeImage",
    "RecipeLine",
    "RecipeLineGroup",
    "RecipeMethod",
    "RecipeSource",
    "RecipeStatus",
    "RecipeStep",
    "RecipeStepGroup",
    "RecipeTemplate",
    "Region",
    "ScheduleDay",
    "ScheduleMeal",
    "ScheduleMealItem",
    "SourcePlatform",
    "StepGroup",
    "TbdEntry",
    "TbdLink",
]
