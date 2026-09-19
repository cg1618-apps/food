"""The category tree's shapes.

`CategoryNode` is the recursive one the tree editor and the library filter both
read. The tree is a few dozen rows, so the whole thing is returned in one
response and assembled in Python - no recursive CTE, no lazy expansion, and no
query per level.
"""

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def _blank_to_none(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class CategoryBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None
    parent_id: int | None = None
    sort_order: int = 0

    @field_validator("name_cn", "name_en", mode="before")
    @classmethod
    def normalise_names(cls, value):
        return _blank_to_none(value)

    @model_validator(mode="after")
    def at_least_one_name(self):
        # Mirrors ck_ingredient_category_has_a_name.
        if not any((self.name_cn, self.name_en)):
            raise ValueError("A category needs at least one name")
        return self


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    """All optional; only what was sent is applied.

    `is_fallback` is absent on purpose and cannot be set through the API. There
    is exactly one fallback row, the migration seeds it, and moving it is not
    an edit - it would re-file every stub ever created. The partial unique
    index refuses a second one regardless; leaving the field out means the API
    never even offers the attempt.
    """

    model_config = ConfigDict(extra="forbid")

    name_cn: str | None = None
    name_en: str | None = None
    parent_id: int | None = None
    sort_order: int | None = None

    @field_validator("name_cn", "name_en", mode="before")
    @classmethod
    def normalise_names(cls, value):
        return _blank_to_none(value)


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str = ""
    name_cn: str | None = None
    name_en: str | None = None
    parent_id: int | None = None
    sort_order: int
    is_fallback: bool


class CategoryNode(CategoryResponse):
    """A category with its subtree, and the counts the editor needs.

    `ingredient_count` is this node alone; `descendant_count` includes every
    node beneath it. Both are here because the delete confirmation needs the
    first and the tree display wants the second, and computing either in the
    browser would mean shipping every ingredient to do it.
    """

    children: list["CategoryNode"] = []
    ingredient_count: int = 0
