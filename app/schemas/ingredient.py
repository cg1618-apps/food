"""Request and response shapes for the ingredient library.

Every validator here mirrors a database constraint, so that a bad payload is a
422 from the API rather than a 500 surfacing an IntegrityError. The handler in
`app/errors.py` is the backstop for whatever slips past; this is the mechanism.

`IngredientUpdate` is an all-optional model used with
`model_dump(exclude_unset=True)`, and it sets `extra="forbid"`. Media takes a
raw `dict` through a shared helper instead, which is load-bearing there for
reasons that do not exist here - association proxies onto a parent row, and
seventeen heterogeneous endpoints. `extra="forbid"` additionally means a
payload naming `id` or `created_at` is REFUSED rather than silently dropped,
which is the one place this setup is strictly better than the one it diverges
from.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.constants import PRESERVATION_METHODS


def _clean_aliases(values: list[str]) -> list[str]:
    """Trim, drop the empties, and refuse the same alias twice.

    Mirrors uq_ingredient_alias. Case-insensitive, because "Ginger" and
    "ginger" are one alias and storing both would make the duplicate warning
    fire against the row's own other spelling.
    """
    cleaned = [v.strip() for v in values if v and v.strip()]
    if len({v.casefold() for v in cleaned}) != len(cleaned):
        raise ValueError("The same alias is listed twice")
    return cleaned


def _one_note_per_method(values: list["PreservationIn"]) -> list["PreservationIn"]:
    """Mirrors uq_ingredient_preservation_method."""
    methods = [v.method for v in values]
    if len(set(methods)) != len(methods):
        raise ValueError("The same preservation method is listed twice")
    return values


def _blank_to_none(value: str | None) -> str | None:
    """An empty form field is an absent value, not an empty string.

    Without this, clearing a name in the UI stores "" - which satisfies
    `num_nonnulls` and defeats `ck_ingredient_has_a_name`, so a row with no
    usable name at all commits cleanly.
    """
    if value is None:
        return None
    value = value.strip()
    return value or None


class PreservationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    duration_days: int | None = None
    notes: str | None = None
    sort_order: int = 0

    @field_validator("method")
    @classmethod
    def method_is_known(cls, value: str) -> str:
        if value not in PRESERVATION_METHODS:
            raise ValueError(f"Unknown preservation method: {value}")
        return value

    @field_validator("duration_days")
    @classmethod
    def duration_is_positive(cls, value: int | None) -> int | None:
        # Mirrors ck_ingredient_preservation_duration_positive.
        if value is not None and value <= 0:
            raise ValueError("A preservation time must be a positive number of days")
        return value


class PreservationResponse(PreservationIn):
    model_config = ConfigDict(from_attributes=True)

    id: int


class LabelRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str = ""


class CategoryRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str = ""


class IngredientSummary(BaseModel):
    """What a list row and module 2's typeahead need, and nothing more.

    `needs_detail` is here rather than only on the full response because the
    typeahead shows it: an ingredient that is still a stub is worth marking at
    the moment somebody picks it, which is when they can most cheaply fix it.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str = ""
    name_cn: str | None = None
    name_en: str | None = None
    name_alt: str | None = None
    category_id: int
    parent_id: int | None = None
    needs_detail: bool


class IngredientBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None
    name_alt: str | None = None
    category_id: int
    parent_id: int | None = None
    description: str | None = None
    selection_notes: str | None = None
    sourcing_notes: str | None = None
    preservation_notes: str | None = None
    needs_detail: bool = False
    aliases: list[str] = []
    preservation: list[PreservationIn] = []
    label_ids: list[int] = []

    @field_validator("name_cn", "name_en", "name_alt", mode="before")
    @classmethod
    def normalise_names(cls, value):
        return _blank_to_none(value) if value is None or isinstance(value, str) else value

    @model_validator(mode="after")
    def at_least_one_name(self):
        # Mirrors ck_ingredient_has_a_name.
        if not any((self.name_cn, self.name_en, self.name_alt)):
            raise ValueError("An ingredient needs at least one name")
        return self

    @field_validator("aliases")
    @classmethod
    def clean_aliases(cls, values: list[str]) -> list[str]:
        return _clean_aliases(values)

    @field_validator("preservation")
    @classmethod
    def one_method_each(cls, values: list[PreservationIn]) -> list[PreservationIn]:
        return _one_note_per_method(values)


class IngredientCreate(IngredientBase):
    pass


class IngredientUpdate(BaseModel):
    """Every field optional, and only what was SENT is applied.

    A separate class rather than `IngredientBase` with defaults, because
    "absent" and "explicitly null" have to stay distinguishable: clearing a
    note is `{"description": null}`, and not mentioning it is `{}`.
    `exclude_unset` keeps that difference; a base class with `None` defaults
    would lose it.

    The at-least-one-name rule cannot be checked here - a PATCH that sends only
    `name_cn: null` is valid or not depending on the row it lands on - so the
    router checks it against the merged result, and the CHECK constraint is the
    backstop.
    """

    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None
    name_alt: str | None = None
    category_id: int | None = None
    parent_id: int | None = None
    description: str | None = None
    selection_notes: str | None = None
    sourcing_notes: str | None = None
    preservation_notes: str | None = None
    needs_detail: bool | None = None
    aliases: list[str] | None = None
    preservation: list[PreservationIn] | None = None
    label_ids: list[int] | None = None

    @field_validator("name_cn", "name_en", "name_alt", mode="before")
    @classmethod
    def normalise_names(cls, value):
        return _blank_to_none(value) if value is None or isinstance(value, str) else value

    @field_validator("aliases")
    @classmethod
    def clean_aliases(cls, values: list[str] | None) -> list[str] | None:
        return None if values is None else _clean_aliases(values)

    @field_validator("preservation")
    @classmethod
    def one_method_each(cls, values):
        return None if values is None else _one_note_per_method(values)


class IngredientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str = ""
    name_cn: str | None = None
    name_en: str | None = None
    name_alt: str | None = None

    category: CategoryRef | None = None
    parent: IngredientSummary | None = None
    children: list[IngredientSummary] = []

    description: str | None = None
    selection_notes: str | None = None
    sourcing_notes: str | None = None
    preservation_notes: str | None = None
    needs_detail: bool

    aliases: list[str] = []
    preservation: list[PreservationResponse] = []
    labels: list[LabelRef] = []

    created_at: datetime | None = None
    updated_at: datetime | None = None
