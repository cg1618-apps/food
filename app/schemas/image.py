"""Image shapes, and the one focus-point rule every gallery shares."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

_FOCUS = re.compile(r"^(\d{1,3}(?:\.\d+)?)% (\d{1,3}(?:\.\d+)?)%$")


def check_focus(value: str | None) -> str | None:
    """'X% Y%' with both in 0..100, or None for centred (media's rule)."""
    if value is None:
        return None
    match = _FOCUS.match(value.strip())
    if not match or any(float(part) > 100 for part in match.groups()):
        raise ValueError("A focus point is 'X% Y%' with both between 0 and 100")
    return value.strip()


class ImageSummary(BaseModel):
    id: int
    url: str
    thumb_url: str
    width: int
    height: int
    byte_size: int
    original_filename: str | None = None
    uploaded_at: datetime | None = None
    attachment_count: int = 0


class ImageOwner(BaseModel):
    type: str
    id: int
    display_name: str


class ImageDetail(ImageSummary):
    owners: list[ImageOwner] = []


class ImageAttachmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_id: int
    focus: str | None = None

    @field_validator("focus")
    @classmethod
    def focus_is_valid(cls, value):
        return check_focus(value)


class AttachedImage(BaseModel):
    image_id: int
    url: str
    thumb_url: str
    width: int
    height: int
    focus: str | None = None


class CoverRef(BaseModel):
    thumb_url: str
    focus: str | None = None
