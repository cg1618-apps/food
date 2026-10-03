"""Request and response shapes for the recipe library.

The same discipline as `app/schemas/ingredient.py`: every validator mirrors a
database constraint so a bad payload is a 422 here rather than an
IntegrityError later, inputs are `extra="forbid"`, and `RecipeUpdate` is an
all-optional model applied with `exclude_unset`.

A recipe belongs to one dish - `dish_id`, or `new_dish` for a name the save
reuses an existing dish for or creates. What is true of the dish (names, kind,
course, region, labels, serves-as) is the dish's and is written through
`app/schemas/dish.py`; a recipe's response embeds a `DishBrief` to show it.

A line carries no type field. Which kind of line it is comes from which target
is set - an ingredient or a dish - and `extra="forbid"` turns a payload
claiming a type into a 422 rather than something a later reader might trust.

Lines and steps travel in pairs: `lines` are the ungrouped lines and
`line_groups` the groups with theirs, and the same for `steps` and
`step_groups`. A save replaces a pair together, so a PATCH sending one half
without the other is a 422 rather than a guess about the half it left out.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.constants import DISH_KINDS, STEP_KINDS
from app.schemas.image import AttachedImage, CoverRef
from app.schemas.ingredient import _blank_to_none, _check_url
from app.schemas.vocabulary import VocabRef

LIST_FIELDS = (
    "sources",
    "lines",
    "line_groups",
    "steps",
    "step_groups",
    "method_ids",
    "equipment_ids",
)


def _check_choice(value: str | None, choices: dict, what: str) -> str:
    # None is refused too: a kind is NOT NULL, so an explicit null on a PATCH
    # is a bad value rather than "clear it".
    if value not in choices:
        raise ValueError(f"A {what} is one of {', '.join(choices)}")
    return value


def _not_null(value, what: str, owner: str = "recipe"):
    """For a NOT NULL id that may be left out: absent is never validated, so
    only an explicit null reaches this and is refused."""
    if value is None:
        raise ValueError(f"A {owner}'s {what} cannot be cleared; choose another")
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


class NewDishIn(NewNameIn):
    """A dish typed into the recipe form that is not in the library yet - the
    recipe's own dish. A name answering to an existing dish reuses it, kind
    and all; otherwise the save creates it with this kind."""

    kind: str = "dish"

    @field_validator("kind")
    @classmethod
    def kind_is_known(cls, value):
        return _check_choice(value, DISH_KINDS, "dish kind")


class NewSubDishIn(NewDishIn):
    """A dish typed into a recipe LINE: the same, but a sauce unless told -
    what a line names is usually something cooked to go into another dish."""

    kind: str = "sauce"


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
    """One line: `ingredient_id` or `new_ingredient`, `sub_dish_id` or
    `new_dish` - exactly one of the four."""

    model_config = ConfigDict(extra="forbid")

    ingredient_id: int | None = None
    sub_dish_id: int | None = None
    new_ingredient: NewNameIn | None = None
    new_dish: NewSubDishIn | None = None
    amount: str | None = None
    note: str | None = None
    is_optional: bool = False

    @field_validator("amount", "note", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)

    @model_validator(mode="after")
    def exactly_one_target(self):
        # Mirrors ck_recipe_line_one_target, with new_ingredient and new_dish
        # counted as an ingredient and a dish that do not exist yet.
        targets = (self.ingredient_id, self.sub_dish_id, self.new_ingredient, self.new_dish)
        if sum(t is not None for t in targets) != 1:
            raise ValueError(
                "A line names exactly one of ingredient_id, sub_dish_id, "
                "new_ingredient or new_dish"
            )
        return self


class StepIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str
    # Left out, an ordinary numbered step.
    kind: str = "step"

    @field_validator("body")
    @classmethod
    def body_is_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A step needs some text")
        return value

    @field_validator("kind")
    @classmethod
    def kind_is_known(cls, value):
        return _check_choice(value, STEP_KINDS, "step kind")


def _one_group_name(group, value_field: str):
    # Mirrors ck_recipe_line_group_one_name / ck_recipe_step_group_one_name.
    if (getattr(group, value_field) is None) == (group.name is None):
        raise ValueError(f"A group names exactly one of {value_field} or name")
    return group


class LineGroupIn(BaseModel):
    """One group of lines: a 材料分組 value, or a one-off name - a name that
    matches a value is stored as that value - and the lines in it, in order.
    Empty is allowed: the group is kept."""

    model_config = ConfigDict(extra="forbid")

    line_group_id: int | None = None
    name: str | None = None
    lines: list[LineIn] = []

    @field_validator("name", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)

    @model_validator(mode="after")
    def exactly_one_name(self):
        return _one_group_name(self, "line_group_id")


class StepGroupIn(BaseModel):
    """One group of steps, as LineGroupIn, naming a 步驟分組 value."""

    model_config = ConfigDict(extra="forbid")

    step_group_id: int | None = None
    name: str | None = None
    steps: list[StepIn] = []

    @field_validator("name", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)

    @model_validator(mode="after")
    def exactly_one_name(self):
        return _one_group_name(self, "step_group_id")


class IngredientRef(BaseModel):
    """An ingredient as a recipe line shows it - `needs_detail` marks a stub."""

    id: int
    display_name: str = ""
    needs_detail: bool


class DishRef(BaseModel):
    """How a recipe, a line or a list points at a dish on the wire."""

    id: int
    display_name: str = ""
    kind: str


class DishBrief(DishRef):
    """The dish as a recipe's page shows it: enough to read what the dish
    says without opening it. Edited on the dish, never through the recipe."""

    course: VocabRef | None = None
    region: VocabRef | None = None
    labels: list[VocabRef] = []
    serves_as: list[VocabRef] = []


class RecipeRef(BaseModel):
    """How something points at a recipe on the wire - an ingredient's "used
    in", a dish's. `dish` is the dish it makes."""

    id: int
    display_name: str = ""
    dish: DishRef


class LineResponse(BaseModel):
    id: int
    position: int
    ingredient: IngredientRef | None = None
    sub_dish: DishRef | None = None
    amount: str | None = None
    note: str | None = None
    is_optional: bool


class StepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    kind: str
    body: str


class LineGroupResponse(BaseModel):
    """`group` is the 設定 value or null, `name` the one-off name or null -
    exactly one is set - and `display_name` whichever it is."""

    id: int
    position: int
    group: VocabRef | None = None
    name: str | None = None
    display_name: str = ""
    lines: list[LineResponse] = []


class StepGroupResponse(BaseModel):
    id: int
    position: int
    group: VocabRef | None = None
    name: str | None = None
    display_name: str = ""
    steps: list[StepResponse] = []


def _one_dish(model):
    if model.dish_id is not None and model.new_dish is not None:
        raise ValueError("A recipe names dish_id or new_dish, not both")
    return model


class RecipeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Exactly one: the recipe's dish, or a dish named for the save to find
    # or create.
    dish_id: int | None = None
    new_dish: NewDishIn | None = None
    # Optional: what tells this recipe from the dish's others. Left out, the
    # recipe is shown by its dish's name.
    name: str | None = None
    # Left out, the first status in sort order (`recipes.create`).
    status_id: int | None = None
    servings: str | None = None
    time: str | None = None
    storage_notes: str | None = None
    notes: str | None = None
    sources: list[SourceIn] = []
    lines: list[LineIn] = []
    line_groups: list[LineGroupIn] = []
    steps: list[StepIn] = []
    step_groups: list[StepGroupIn] = []
    method_ids: list[int] = []
    equipment_ids: list[int] = []

    @field_validator("name", mode="before")
    @classmethod
    def normalise_name(cls, value):
        return _normalise(value)

    @field_validator("status_id")
    @classmethod
    def status_is_not_null(cls, value):
        return _not_null(value, "status")

    @model_validator(mode="after")
    def exactly_one_dish(self):
        # Mirrors recipe.dish_id NOT NULL, with new_dish counted as a dish
        # that does not exist yet.
        _one_dish(self)
        if self.dish_id is None and self.new_dish is None:
            raise ValueError("A recipe belongs to a dish: send dish_id or new_dish")
        return self


class RecipeUpdate(BaseModel):
    """Every field optional, and only what was SENT is applied.

    `dish_id` or `new_dish` moves the recipe to another dish; neither leaves
    it where it is.
    """

    model_config = ConfigDict(extra="forbid")

    dish_id: int | None = None
    new_dish: NewDishIn | None = None
    name: str | None = None
    status_id: int | None = None
    servings: str | None = None
    time: str | None = None
    storage_notes: str | None = None
    notes: str | None = None
    sources: list[SourceIn] | None = None
    lines: list[LineIn] | None = None
    line_groups: list[LineGroupIn] | None = None
    steps: list[StepIn] | None = None
    step_groups: list[StepGroupIn] | None = None
    method_ids: list[int] | None = None
    equipment_ids: list[int] | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalise_name(cls, value):
        return _normalise(value)

    # Validators run only on fields that were sent, so an explicit null is
    # checked - and refused - while an absent one is left alone.
    @field_validator("status_id")
    @classmethod
    def status_is_not_null(cls, value):
        return _not_null(value, "status")

    @field_validator("dish_id")
    @classmethod
    def dish_is_not_null(cls, value):
        return _not_null(value, "dish")

    @model_validator(mode="after")
    def at_most_one_dish(self):
        return _one_dish(self)

    @model_validator(mode="after")
    def pairs_travel_together(self):
        """`lines` with `line_groups`, `steps` with `step_groups`: both or
        neither, and neither half null. Replacing one half alone would have
        to guess what happens to the rows in the other."""
        for rows, groups in (("lines", "line_groups"), ("steps", "step_groups")):
            sent = {rows, groups} & self.model_fields_set
            if not sent:
                continue
            if len(sent) == 1 or getattr(self, rows) is None or getattr(self, groups) is None:
                raise ValueError(f"{rows} and {groups} are replaced together; send both")
        return self


class RecipeSummary(BaseModel):
    """What a library row needs - the cover view and the table view both.

    `authors` is the distinct authors of the recipe's sources, in source
    order. `written_up` is derived, as on the full recipe. `course` is the
    dish's, for the table view's column.
    """

    id: int
    display_name: str = ""
    name: str | None = None
    dish: DishRef
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
    name: str | None = None
    dish: DishBrief
    status: VocabRef
    servings: str | None = None
    time: str | None = None
    storage_notes: str | None = None
    notes: str | None = None

    sources: list[SourceResponse] = []
    # The ungrouped rows; each group carries its own.
    lines: list[LineResponse] = []
    line_groups: list[LineGroupResponse] = []
    steps: list[StepResponse] = []
    step_groups: list[StepGroupResponse] = []
    methods: list[VocabRef] = []
    equipment: list[VocabRef] = []
    images: list[AttachedImage] = []

    # 其他版本: the dish's other recipes, by display name.
    other_recipes: list[RecipeRef] = []
    written_up: bool

    created_at: datetime | None = None
    updated_at: datetime | None = None
