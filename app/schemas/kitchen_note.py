"""Request and response shapes for kitchen notes.

The same discipline as `app/schemas/recipe.py`: every validator mirrors a
database constraint, inputs are `extra="forbid"`, and `KitchenNoteUpdate` is
all-optional and applied with `exclude_unset`.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.constants import KITCHEN_NOTE_KINDS
from app.schemas.image import AttachedImage, CoverRef
from app.schemas.ingredient import _check_url
from app.schemas.recipe import _check_choice, _normalise
from app.schemas.vocabulary import VocabRef


def _check_title(value):
    # Mirrors ck_kitchen_note_has_a_title. None is refused too: the column is
    # NOT NULL, so an explicit null on a PATCH is a bad value, not "clear it".
    # A non-string passes through to the str type check, which refuses it.
    value = _normalise(value)
    if value is None:
        raise ValueError("A note needs a title")
    return value


class KitchenNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    kind: str = "reference"
    url: str | None = None
    body: str | None = None
    label_ids: list[int] = []

    @field_validator("title", mode="before")
    @classmethod
    def title_is_not_blank(cls, value):
        return _check_title(value)

    @field_validator("kind")
    @classmethod
    def kind_is_known(cls, value):
        return _check_choice(value, KITCHEN_NOTE_KINDS, "kind")

    @field_validator("url", "body", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)

    @field_validator("url")
    @classmethod
    def url_is_http(cls, value: str | None) -> str | None:
        return None if value is None else _check_url(value)


class KitchenNoteUpdate(BaseModel):
    """Every field optional; only what was SENT is applied. `label_ids`
    replaces the labels when sent and leaves them alone when not."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    kind: str | None = None
    url: str | None = None
    body: str | None = None
    label_ids: list[int] | None = None

    # Validators run only on fields that were sent, so an explicit null title
    # or kind is checked - and refused - while an absent one is left alone.
    @field_validator("title", mode="before")
    @classmethod
    def title_is_not_blank(cls, value):
        return _check_title(value)

    @field_validator("kind")
    @classmethod
    def kind_is_known(cls, value):
        return _check_choice(value, KITCHEN_NOTE_KINDS, "kind")

    @field_validator("url", "body", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)

    @field_validator("url")
    @classmethod
    def url_is_http(cls, value: str | None) -> str | None:
        return None if value is None else _check_url(value)


class KitchenNoteSummary(BaseModel):
    """A library row."""

    id: int
    title: str
    kind: str
    url: str | None = None
    labels: list[VocabRef] = []
    cover: CoverRef | None = None


class KitchenNoteResponse(BaseModel):
    id: int
    title: str
    kind: str
    url: str | None = None
    body: str | None = None
    labels: list[VocabRef] = []
    images: list[AttachedImage] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None
