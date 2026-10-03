"""加熱 on the wire: a note is a name and an optional body.

Inputs are `extra="forbid"` and `HeatingNoteUpdate` is applied with
`exclude_unset`, as every other update here.
"""

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.recipe import _normalise


def _required_name(value):
    value = _normalise(value)
    if value is None:
        raise ValueError("A note needs a name")
    return value


class HeatingNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    body: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def name_is_not_blank(cls, value):
        return _required_name(value)

    @field_validator("body", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)


class HeatingNoteUpdate(BaseModel):
    """Only what was SENT is applied. The name may be left out, never blanked."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    body: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def name_is_not_blank(cls, value):
        return _required_name(value)

    @field_validator("body", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)


class HeatingNoteResponse(BaseModel):
    id: int
    name: str
    body: str | None = None
    sort_order: int


class HeatingOrderIn(BaseModel):
    """Every note's id, in the order the page should show them."""

    model_config = ConfigDict(extra="forbid")

    ids: list[int]
