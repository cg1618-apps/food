"""常用食材 on the wire: read as an ordered list, written as a whole list."""

from pydantic import BaseModel, ConfigDict

from app.schemas.recipe import IngredientRef


class CommonIngredientResponse(BaseModel):
    """One chip. `ingredient` is the shape a recipe line embeds."""

    ingredient: IngredientRef
    sort_order: int


class CommonIngredientsIn(BaseModel):
    """The whole list, in order. It replaces whatever was there."""

    model_config = ConfigDict(extra="forbid")

    ingredient_ids: list[int]
