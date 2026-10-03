"""Request and response shapes for the recipe library.

The same discipline as `app/schemas/ingredient.py`: every validator mirrors a
database constraint so a bad payload is a 422 here rather than an
IntegrityError later, inputs are `extra="forbid"`, and `RecipeUpdate` is an
all-optional model applied with `exclude_unset`.

A line carries no type field. Which kind of line it is comes from which target
is set, and `extra="forbid"` turns a payload claiming a type into a 422 rather
than something a later reader might trust.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.constants import RECIPE_KINDS
from app.schemas.image import AttachedImage, CoverRef
from app.schemas.ingredient import _blank_to_none, _check_url, _clean_aliases
from app.schemas.vocabulary import VocabRef

LIST_FIELDS = (
    "aliases",
    "sources",
    "lines",
    "steps",
    "serves_as_ids",
    "label_ids",
    "method_ids",
    "equipment_ids",
)


def _check_choice(value: str | None, choices: dict, what: str) -> str:
    # None is refused too: kind is NOT NULL, so an explicit null on a PATCH is
    # a bad value rather than "clear it".
    if value not in choices:
        raise ValueError(f"A {what} is one of {', '.join(choices)}")
    return value


def _not_null(value, what: str):
    """For a NOT NULL id that may be left out: absent is never validated, so
    only an explicit null reaches this and is refused."""
    if value is None:
        raise ValueError(f"A recipe's {what} cannot be cleared; choose another")
    return value


def _normalise(value):
    return _blank_to_none(value) if value is None or isinstance(value, str) else value


class NewNameIn(BaseModel):
    """A name typed into the form that is not in the library yet - a line's
    ingredient, a source's author. Filed in whichever slot the form chose."""

    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None

    @field_validator("name_cn", "name_en", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)

    @model_validator(mode="after")
    def at_least_one_name(self):
        if not any((self.name_cn, self.name_en)):
            raise ValueError("A new name needs at least one of name_cn or name_en")
        return self


class SourceIn(BaseModel):
    """No `sort_order`: a source's order is its position in the list.

    The author is `author_id` or `new_author` - a name the save reuses an
    existing author for, or creates - or neither: a source may have none.
    """

    model_config = ConfigDict(extra="forbid")

    # Required, and checked against source_platform by the service.
    platform_id: int
    author_id: int | None = None
    new_author: NewNameIn | None = None
    url: str | None = None
    title: str | None = None

    @field_validator("url", "title", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)

    @field_validator("url")
    @classmethod
    def url_is_http(cls, value: str | None) -> str | None:
        return None if value is None else _check_url(value)

    @model_validator(mode="after")
    def says_something(self):
        if self.author_id is not None and self.new_author is not None:
            raise ValueError("A source names author_id or new_author, not both")
        # Mirrors ck_recipe_source_has_content, with new_author counted as an
        # author that does not exist yet.
        author = self.author_id is not None or self.new_author is not None
        if not (author or self.url or self.title):
            raise ValueError("A source needs an author, a link or a title")
        return self


class SourceResponse(BaseModel):
    id: int
    platform: VocabRef
    author: VocabRef | None = None
    url: str | None = None
    title: str | None = None
    sort_order: int


class LineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: str | None = None
    ingredient_id: int | None = None
    sub_recipe_id: int | None = None
    new_ingredient: NewNameIn | None = None
    amount: str | None = None
    note: str | None = None
    is_optional: bool = False

    @field_validator("section", "amount", "note", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)

    @model_validator(mode="after")
    def exactly_one_target(self):
        # Mirrors ck_recipe_line_one_target, with new_ingredient counted as an
        # ingredient that does not exist yet.
        targets = (self.ingredient_id, self.sub_recipe_id, self.new_ingredient)
        if sum(t is not None for t in targets) != 1:
            raise ValueError(
                "A line names exactly one of ingredient_id, sub_recipe_id or new_ingredient"
            )
        return self


class StepIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: str | None = None
    body: str

    @field_validator("section", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)

    @field_validator("body")
    @classmethod
    def body_is_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A step needs some text")
        return value


class IngredientRef(BaseModel):
    """An ingredient as a recipe line shows it - `needs_detail` marks a stub."""

    id: int
    display_name: str = ""
    needs_detail: bool


class RecipeRef(BaseModel):
    """How one recipe points at another on the wire."""

    id: int
    display_name: str = ""
    kind: str


class LineResponse(BaseModel):
    id: int
    position: int
    section: str | None = None
    ingredient: IngredientRef | None = None
    sub_recipe: RecipeRef | None = None
    amount: str | None = None
    note: str | None = None
    is_optional: bool


class StepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    section: str | None = None
    body: str


class RecipeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None
    name_alt: str | None = None
    kind: str = "dish"
    course_id: int | None = None
    variant_of_id: int | None = None
    # Left out, the first status in sort order (`recipes.create`).
    status_id: int | None = None
    servings: str | None = None
    time: str | None = None
    description: str | None = None
    storage_notes: str | None = None
    notes: str | None = None
    aliases: list[str] = []
    sources: list[SourceIn] = []
    lines: list[LineIn] = []
    steps: list[StepIn] = []
    serves_as_ids: list[int] = []
    label_ids: list[int] = []
    method_ids: list[int] = []
    equipment_ids: list[int] = []

    @field_validator("name_cn", "name_en", "name_alt", mode="before")
    @classmethod
    def normalise_names(cls, value):
        return _normalise(value)

    @field_validator("kind")
    @classmethod
    def kind_is_known(cls, value):
        return _check_choice(value, RECIPE_KINDS, "kind")

    @field_validator("status_id")
    @classmethod
    def status_is_not_null(cls, value):
        return _not_null(value, "status")

    @field_validator("aliases")
    @classmethod
    def clean_aliases(cls, values: list[str]) -> list[str]:
        return _clean_aliases(values)

    @model_validator(mode="after")
    def at_least_one_name(self):
        # Mirrors ck_recipe_has_a_name.
        if not any((self.name_cn, self.name_en, self.name_alt)):
            raise ValueError("A recipe needs at least one name")
        return self


class RecipeUpdate(BaseModel):
    """Every field optional, and only what was SENT is applied.

    As `IngredientUpdate`: the at-least-one-name rule depends on the row the
    PATCH lands on, so the service checks it against the merged result.
    """

    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None
    name_alt: str | None = None
    kind: str | None = None
    course_id: int | None = None
    variant_of_id: int | None = None
    status_id: int | None = None
    servings: str | None = None
    time: str | None = None
    description: str | None = None
    storage_notes: str | None = None
    notes: str | None = None
    aliases: list[str] | None = None
    sources: list[SourceIn] | None = None
    lines: list[LineIn] | None = None
    steps: list[StepIn] | None = None
    serves_as_ids: list[int] | None = None
    label_ids: list[int] | None = None
    method_ids: list[int] | None = None
    equipment_ids: list[int] | None = None

    @field_validator("name_cn", "name_en", "name_alt", mode="before")
    @classmethod
    def normalise_names(cls, value):
        return _normalise(value)

    # Validators run only on fields that were sent, so an explicit null is
    # checked - and refused - while an absent kind is left alone.
    @field_validator("kind")
    @classmethod
    def kind_is_known(cls, value):
        return _check_choice(value, RECIPE_KINDS, "kind")

    @field_validator("status_id")
    @classmethod
    def status_is_not_null(cls, value):
        return _not_null(value, "status")

    @field_validator("aliases")
    @classmethod
    def clean_aliases(cls, values: list[str] | None) -> list[str] | None:
        return None if values is None else _clean_aliases(values)


class RecipeSummary(BaseModel):
    """What a library row needs - the cover view and the table view both.

    `authors` is the distinct authors of the recipe's sources, in source
    order. `written_up` is derived, as on the full recipe.
    """

    id: int
    display_name: str = ""
    name_cn: str | None = None
    name_en: str | None = None
    name_alt: str | None = None
    kind: str
    status: VocabRef
    course: VocabRef | None = None
    methods: list[VocabRef] = []
    authors: list[VocabRef] = []
    time: str | None = None
    written_up: bool
    cover: CoverRef | None = None


class RecipeResponse(BaseModel):
    id: int
    display_name: str = ""
    name_cn: str | None = None
    name_en: str | None = None
    name_alt: str | None = None
    kind: str
    status: VocabRef
    course: VocabRef | None = None
    servings: str | None = None
    time: str | None = None
    description: str | None = None
    storage_notes: str | None = None
    notes: str | None = None

    aliases: list[str] = []
    sources: list[SourceResponse] = []
    lines: list[LineResponse] = []
    steps: list[StepResponse] = []
    serves_as: list[VocabRef] = []
    labels: list[VocabRef] = []
    methods: list[VocabRef] = []
    equipment: list[VocabRef] = []
    images: list[AttachedImage] = []

    variant_of: RecipeRef | None = None
    versions: list[RecipeRef] = []
    used_in: list[RecipeRef] = []
    written_up: bool

    created_at: datetime | None = None
    updated_at: datetime | None = None
