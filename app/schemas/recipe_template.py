"""Recipe templates on the wire.

A template's `body` is the recipe payload's structural half, validated by the
recipe's own input models - `LineIn`, `LineGroupIn`, `StepIn`, `StepGroupIn` -
so a template line, group or step is exactly a recipe's. What a template
leaves out (the dish, a name, status, sources, notes, the gallery) is refused
by `extra="forbid"` rather than silently dropped.

One thing the models accept that a template does not: a line's
`new_ingredient` or `new_dish`. A template never creates rows - it is applied
to a form, and nothing about it is saved until the recipe is - so the service
refuses those with a sentence saying to pick an existing one.

On the way out the body is in the recipe RESPONSE's shapes - a line's
`ingredient` / `sub_dish`, a group's `group` / `name` / `display_name`,
`methods` and `equipment` as refs - so the recipe form reads a template with
the code that reads a recipe. `dropped` counts the references that no longer
exist and were left out.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.recipe import (
    DishRef,
    IngredientRef,
    LineGroupIn,
    LineIn,
    StepGroupIn,
    StepIn,
    _normalise,
)
from app.schemas.vocabulary import VocabRef


def _name(value):
    value = _normalise(value)
    if value is None:
        raise ValueError("A template needs a name")
    return value


class TemplateBodyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    servings: str | None = None
    time: str | None = None
    lines: list[LineIn] = []
    line_groups: list[LineGroupIn] = []
    steps: list[StepIn] = []
    step_groups: list[StepGroupIn] = []
    method_ids: list[int] = []
    equipment_ids: list[int] = []

    @field_validator("servings", "time", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)


class TemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    # Left out, an empty template: a name and nothing else.
    body: TemplateBodyIn = TemplateBodyIn()

    @field_validator("name", mode="before")
    @classmethod
    def name_is_not_blank(cls, value):
        return _name(value)


class TemplateUpdate(BaseModel):
    """Only what was SENT is applied. `body`, when sent, replaces the whole
    body; neither field may be null."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    body: TemplateBodyIn | None = None

    @field_validator("name", mode="before")
    @classmethod
    def name_is_not_blank(cls, value):
        return _name(value)

    @field_validator("body", mode="before")
    @classmethod
    def body_is_not_null(cls, value):
        if value is None:
            raise ValueError("Send a body to replace it; it cannot be cleared to null")
        return value


class TemplateFromRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str

    @field_validator("name", mode="before")
    @classmethod
    def name_is_not_blank(cls, value):
        return _name(value)


class TemplateOrderIn(BaseModel):
    """Every template's id, in the order 設定 should list them."""

    model_config = ConfigDict(extra="forbid")

    ids: list[int]


class TemplateLine(BaseModel):
    ingredient: IngredientRef | None = None
    sub_dish: DishRef | None = None
    amount: str | None = None
    note: str | None = None
    is_optional: bool = False


class TemplateStep(BaseModel):
    kind: str
    body: str


class TemplateLineGroup(BaseModel):
    group: VocabRef | None = None
    name: str | None = None
    display_name: str = ""
    lines: list[TemplateLine] = []


class TemplateStepGroup(BaseModel):
    group: VocabRef | None = None
    name: str | None = None
    display_name: str = ""
    steps: list[TemplateStep] = []


class TemplateBody(BaseModel):
    servings: str | None = None
    time: str | None = None
    lines: list[TemplateLine] = []
    line_groups: list[TemplateLineGroup] = []
    steps: list[TemplateStep] = []
    step_groups: list[TemplateStepGroup] = []
    methods: list[VocabRef] = []
    equipment: list[VocabRef] = []


class TemplateSummary(BaseModel):
    """A row of the list: counts as stored, stale references included."""

    id: int
    name: str
    sort_order: int
    line_count: int
    step_count: int


class TemplateResponse(BaseModel):
    id: int
    name: str
    sort_order: int
    body: TemplateBody
    # References in the stored body that no longer exist, left out of `body`.
    dropped: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
