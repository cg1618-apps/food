"""Label shapes. Two name slots, because a tag has no formal alternative, and
one scope - the library the label belongs to."""

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.constants import LABEL_SCOPES
from app.schemas.recipe import _check_choice


def _blank_to_none(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class LabelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None
    # Required: a label is added inside the library it belongs to.
    scope: str

    @field_validator("name_cn", "name_en", mode="before")
    @classmethod
    def normalise_names(cls, value):
        return _blank_to_none(value)

    @field_validator("scope")
    @classmethod
    def scope_is_known(cls, value):
        return _check_choice(value, LABEL_SCOPES, "label scope")

    @model_validator(mode="after")
    def at_least_one_name(self):
        # Mirrors ck_label_has_a_name.
        if not any((self.name_cn, self.name_en)):
            raise ValueError("A label needs at least one name")
        return self


class LabelUpdate(BaseModel):
    """`scope` moves the label to another library - refused by the router
    while anything carries it. An explicit null is refused here: a label
    always has a library."""

    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None
    scope: str | None = None

    @field_validator("name_cn", "name_en", mode="before")
    @classmethod
    def normalise_names(cls, value):
        return _blank_to_none(value)

    @field_validator("scope")
    @classmethod
    def scope_is_known(cls, value):
        return _check_choice(value, LABEL_SCOPES, "label scope")


class LabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str = ""
    name_cn: str | None = None
    name_en: str | None = None
    scope: str
    # Links per owner, and their total. `usage_count` is the name the other
    # vocabularies use for "how many things carry this". Only the field of
    # the label's own scope can be non-zero - the API links a label nowhere
    # else - but all three are served, so a reader need not know that.
    ingredient_count: int = 0
    dish_count: int = 0
    note_count: int = 0
    usage_count: int = 0
