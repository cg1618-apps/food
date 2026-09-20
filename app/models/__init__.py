"""Every model, imported here so string relationships resolve.

SQLAlchemy resolves `relationship("Ingredient")` by name against a registry
that only holds classes which have actually been imported. Importing one model
module on its own therefore works until it points at a table nobody imported,
and then fails at first use rather than at import - so everything is imported
here and every caller reaches models through this package.

Alembic's autogenerate reads `Base.metadata`, which is populated by the same
imports; a model missing from this file is a table missing from the diff.
"""

from app.models.ingredient import (
    Ingredient,
    IngredientAlias,
    IngredientCategory,
    IngredientPreservation,
)
from app.models.label import IngredientLabel, Label

__all__ = [
    "Ingredient",
    "IngredientAlias",
    "IngredientCategory",
    "IngredientLabel",
    "IngredientPreservation",
    "Label",
]
