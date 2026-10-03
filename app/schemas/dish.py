"""Request and response shapes for the dish library.

The recipe schemas' discipline: validators mirror the database's constraints,
inputs are `extra="forbid"`, and `DishUpdate` is all-optional and applied with
`exclude_unset`. `DishRef` and `DishBrief` - how other rows point at a dish -
live in `app/schemas/recipe.py` beside `IngredientRef`, because the recipe
shapes need them and this module needs the recipe's.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.constants import DISH_KINDS
from app.schemas.image import AttachedImage, CoverRef
from app.schemas.ingredient import _clean_aliases
from app.schemas.recipe import RecipeRef, RecipeSummary, _check_choice, _normalise
from app.schemas.vocabulary import VocabRef

LIST_FIELDS = ("aliases", "serves_as_ids", "label_ids")


class DishCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None
    name_alt: str | None = None
    kind: str = "dish"
    course_id: int | None = None
    region_id: int | None = None
    description: str | None = None
    aliases: list[str] = []
    serves_as_ids: list[int] = []
    label_ids: list[int] = []

    @field_validator("name_cn", "name_en", "name_alt", "description", mode="before")
    @classmethod
    def normalise_text(cls, value):
        return _normalise(value)

    @field_validator("kind")
    @classmethod
    def kind_is_known(cls, value):
        return _check_choice(value, DISH_KINDS, "dish kind")

    @field_validator("aliases")
    @classmethod
    def clean_aliases(cls, values: list[str]) -> list[str]:
        return _clean_aliases(values)

    @model_validator(mode="after")
    def at_least_one_name(self):
        # Mirrors ck_dish_has_a_name.
        if not any((self.name_cn, self.name_en, self.name_alt)):
            raise ValueError("A dish needs at least one name")
        return self


class DishUpdate(BaseModel):
    """Every field optional, and only what was SENT is applied. The
    at-least-one-name rule is checked by the service against the merged row,
    as `IngredientUpdate`'s is."""

    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None
    name_alt: str | None = None
    kind: str | None = None
    course_id: int | None = None
    region_id: int | None = None
    description: str | None = None
    aliases: list[str] | None = None
    serves_as_ids: list[int] | None = None
    label_ids: list[int] | None = None

    @field_validator("name_cn", "name_en", "name_alt", "description", mode="before")
    @classmethod
    def normalise_text(cls, value):
        return _normalise(value)

    # Validators run only on fields that were sent, so an explicit null is
    # checked - and refused - while an absent kind is left alone.
    @field_validator("kind")
    @classmethod
    def kind_is_known(cls, value):
        return _check_choice(value, DISH_KINDS, "dish kind")

    @field_validator("aliases")
    @classmethod
    def clean_aliases(cls, values: list[str] | None) -> list[str] | None:
        return None if values is None else _clean_aliases(values)


class DishSummary(BaseModel):
    """What a library row needs. `cover` is the dish's first picture, else the
    first of its recipes' covers; `recipe_count` how many recipes make it."""

    id: int
    display_name: str = ""
    name_cn: str | None = None
    name_en: str | None = None
    name_alt: str | None = None
    kind: str
    course: VocabRef | None = None
    region: VocabRef | None = None
    labels: list[VocabRef] = []
    recipe_count: int = 0
    cover: CoverRef | None = None


class DishResponse(BaseModel):
    id: int
    display_name: str = ""
    name_cn: str | None = None
    name_en: str | None = None
    name_alt: str | None = None
    kind: str
    course: VocabRef | None = None
    region: VocabRef | None = None
    description: str | None = None

    aliases: list[str] = []
    serves_as: list[VocabRef] = []
    labels: list[VocabRef] = []
    images: list[AttachedImage] = []
    # The dish's own recipes, as the recipe library lists them.
    recipes: list[RecipeSummary] = []
    # Recipes with a line naming this dish - what a sauce is used in.
    used_in: list[RecipeRef] = []

    created_at: datetime | None = None
    updated_at: datetime | None = None
