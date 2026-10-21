"""常用食材 on the wire: read as one structure, written as one structure.

    { "ungrouped": [chip], "groups": [{ id, name, ingredients: [chip] }] }

in display order, 未分組 first. A write sends the same structure with ids in
place of chips, and replaces whatever was there.
"""

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.recipe import IngredientRef, _normalise


class CommonIngredientGroupResponse(BaseModel):
    """One group and its chips, in order. A chip is the shape a recipe line
    embeds."""

    id: int
    name: str
    ingredients: list[IngredientRef]


class CommonIngredientsResponse(BaseModel):
    ungrouped: list[IngredientRef]
    groups: list[CommonIngredientGroupResponse]


class CommonIngredientGroupIn(BaseModel):
    """A group as it should now be. With `id` it is that group, renamed and
    moved; without, a new one."""

    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    name: str
    ingredient_ids: list[int]

    @field_validator("name", mode="before")
    @classmethod
    def name_is_not_blank(cls, value):
        value = _normalise(value)
        if value is None:
            raise ValueError("A group needs a name")
        return value


class CommonIngredientsIn(BaseModel):
    """The whole structure, in order. It replaces whatever was there: a
    stored group not sent is deleted."""

    model_config = ConfigDict(extra="forbid")

    ungrouped: list[int]
    groups: list[CommonIngredientGroupIn]
