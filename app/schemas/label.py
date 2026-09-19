"""Label shapes. Two name slots, because a tag has no formal alternative."""

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


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

    @field_validator("name_cn", "name_en", mode="before")
    @classmethod
    def normalise_names(cls, value):
        return _blank_to_none(value)

    @model_validator(mode="after")
    def at_least_one_name(self):
        # Mirrors ck_label_has_a_name.
        if not any((self.name_cn, self.name_en)):
            raise ValueError("A label needs at least one name")
        return self


class LabelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None

    @field_validator("name_cn", "name_en", mode="before")
    @classmethod
    def normalise_names(cls, value):
        return _blank_to_none(value)


class LabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str = ""
    name_cn: str | None = None
    name_en: str | None = None
    ingredient_count: int = 0
