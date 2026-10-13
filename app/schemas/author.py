"""An author on the wire: the shared vocabulary shape plus a remark and links.

Authors are served by the vocabulary factory (app/routers/vocabulary.py) like
the other eight; these are the schemas it is given for them, so the other
eight keep refusing `notes` and `links` as extra fields.

A link is a TBD link in every rule - `normalise_link` and the blank label -
because it is the same thing: a web address the owner typed, with an optional
name. `links` replaces every link when sent; on an update an explicit null is
refused and [] clears, as on a TBD entry.
"""

from pydantic import BaseModel, field_validator

from app.schemas.recipe import _normalise
from app.schemas.tbd import TbdLinkIn
from app.schemas.vocabulary import VocabularyCreate, VocabularyResponse, VocabularyUpdate


class AuthorLinkIn(TbdLinkIn):
    """A TBD link's rules exactly: no position, a url that must be web."""


class AuthorCreate(VocabularyCreate):
    notes: str | None = None
    links: list[AuthorLinkIn] = []

    @field_validator("notes", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)


class AuthorUpdate(VocabularyUpdate):
    notes: str | None = None
    links: list[AuthorLinkIn] | None = None

    @field_validator("notes", mode="before")
    @classmethod
    def blank_is_absent(cls, value):
        return _normalise(value)

    @field_validator("links", mode="before")
    @classmethod
    def links_are_a_list(cls, value):
        if value is None:
            raise ValueError("Send [] to remove every link")
        return value


class AuthorLinkResponse(BaseModel):
    label: str | None = None
    url: str


class AuthorResponse(VocabularyResponse):
    notes: str | None = None
    links: list[AuthorLinkResponse] = []
