"""TBD on the wire: an entry is an optional name and a list of links.

Inputs are `extra="forbid"` and `TbdEntryUpdate` is applied with
`exclude_unset`, as every other update here. The rule that an entry has a name
or a link is checked by the service, against the entry as it would be saved -
a PATCH that sends only `links: []` is fine or not depending on the name
already stored, which a schema cannot see.
"""

import re

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.ingredient import _check_url
from app.schemas.recipe import _normalise

# A scheme is letters followed by a colon - but not a colon followed by a
# digit, which is a port on a bare host (`localhost:8000`), not a scheme.
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:(?!\d)")


def normalise_link(value):
    """What the owner typed, as a stored link.

    Anything without a scheme is taken as a web address and given `https://`
    - `example.com/x` is how a link is usually typed. One WITH a scheme must
    be http or https: `javascript:` rendered as a link is an XSS.
    """
    if not isinstance(value, str):
        return value
    value = value.strip()
    if not value:
        raise ValueError("A link needs a URL")
    if not _SCHEME.match(value):
        value = f"https://{value}"
    return _check_url(value)


class TbdLinkIn(BaseModel):
    """No position: a link's order is its place in the list."""

    model_config = ConfigDict(extra="forbid")

    url: str
    label: str | None = None

    @field_validator("url", mode="before")
    @classmethod
    def url_is_a_web_address(cls, value):
        return normalise_link(value)

    @field_validator("label", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)


class TbdEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    links: list[TbdLinkIn] = []

    @field_validator("name", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)


class TbdEntryUpdate(BaseModel):
    """Only what was SENT is applied. `links` replaces every link when sent
    and leaves them alone when not; an explicit null is refused - [] clears."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    links: list[TbdLinkIn] | None = None

    @field_validator("name", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)

    @field_validator("links", mode="before")
    @classmethod
    def links_are_a_list(cls, value):
        if value is None:
            raise ValueError("Send [] to remove every link")
        return value


class TbdLinkResponse(BaseModel):
    id: int
    url: str
    label: str | None = None


class TbdEntryResponse(BaseModel):
    id: int
    name: str | None = None
    links: list[TbdLinkResponse] = []
    sort_order: int


class TbdOrderIn(BaseModel):
    """Every entry's id, in the order the page should show them."""

    model_config = ConfigDict(extra="forbid")

    ids: list[int]
