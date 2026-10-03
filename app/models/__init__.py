"""Every model, imported here so string relationships resolve.

SQLAlchemy resolves `relationship("Ingredient")` by name against a registry
that only holds classes which have actually been imported. Importing one model
module on its own therefore works until it points at a table nobody imported,
and then fails at first use rather than at import - so everything is imported
here and every caller reaches models through this package.

Alembic's autogenerate reads `Base.metadata`, which is populated by the same
imports; a model missing from this file is a table missing from the diff.
"""

from app.models.image import Image, IngredientImage, KitchenNoteImage, RecipeImage
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
    RecipeAlias,
    RecipeEquipment,
    RecipeLabel,
    RecipeLine,
    RecipeLineGroup,
    RecipeMethod,
    RecipeServesAs,
    RecipeSource,
    RecipeStep,
    RecipeStepGroup,
)
from app.models.vocabulary import (
    Author,
    CookingMethod,
    Equipment,
    LineGroup,
    RecipeCourse,
    RecipeStatus,
    SourcePlatform,
    StepGroup,
)

__all__ = [
    "Author",
    "CookingMethod",
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
    "RecipeAlias",
    "RecipeCourse",
    "RecipeEquipment",
    "RecipeImage",
    "RecipeLabel",
    "RecipeLine",
    "RecipeLineGroup",
    "RecipeMethod",
    "RecipeServesAs",
    "RecipeSource",
    "RecipeStatus",
    "RecipeStep",
    "RecipeStepGroup",
    "SourcePlatform",
    "StepGroup",
]
