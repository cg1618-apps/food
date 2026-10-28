"""The universal search's response: one list per kind of thing in the app."""

from pydantic import BaseModel

from app.schemas.image import CoverRef


class SearchHit(BaseModel):
    """One result row. `detail` is the short secondary line - a dish's kind,
    a recipe's dish and authors, an ingredient's category - and `cover` is
    null for a kind with no gallery (加熱, TBD) as for a row without one."""

    id: int
    display_name: str
    detail: str | None = None
    cover: CoverRef | None = None


class SearchBuckets(BaseModel):
    """Every bucket is always present, empty when nothing matched."""

    dishes: list[SearchHit] = []
    recipes: list[SearchHit] = []
    ingredients: list[SearchHit] = []
    notes: list[SearchHit] = []
    authors: list[SearchHit] = []
    heating: list[SearchHit] = []
    tbd: list[SearchHit] = []


class SearchResponse(BaseModel):
    query: str
    results: SearchBuckets
