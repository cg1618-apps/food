"""Shapes shared by the three managed vocabularies."""

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class VocabRef(BaseModel):
    """How another row points at a vocabulary value on the wire."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str = ""


class VocabularyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None
    sort_order: int = 0

    @field_validator("name_cn", "name_en", mode="before")
    @classmethod
    def normalise_names(cls, value):
        return _blank_to_none(value)

    @model_validator(mode="after")
    def at_least_one_name(self):
        if not any((self.name_cn, self.name_en)):
            raise ValueError("A value needs at least one name")
        return self


class VocabularyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None
    sort_order: int | None = None

    @field_validator("name_cn", "name_en", mode="before")
    @classmethod
    def normalise_names(cls, value):
        return _blank_to_none(value)


class VocabularyResponse(BaseModel):
    id: int
    display_name: str = ""
    name_cn: str | None = None
    name_en: str | None = None
    sort_order: int
    usage_count: int
