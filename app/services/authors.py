"""What an author has that the other nine vocabularies do not: a remark, links
and a gallery, and a page of its own.

The vocabulary factory (app/routers/vocabulary.py) calls `apply` to write a
create or an update, `load` to read the links and the gallery with the list,
and `extra` for what a list row carries beyond its columns - the recipe count
and the cover the author library shows. The author's page
(app/routers/author.py) reads one author through `get`, and its delete preview
through `cascade_counts`.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError
from app.models import Author, AuthorImage, AuthorLink, RecipeSource
from app.services import images

# The list reads every author's links and gallery in one more query each, not
# one per author.
load = (
    selectinload(Author.links),
    selectinload(Author.images).selectinload(AuthorImage.image),
)


def _links(payload_links) -> list[AuthorLink]:
    """An update is dumped with exclude_unset, which reaches into the links:
    a link sent without a label has no `label` key."""
    return [
        AuthorLink(position=position, url=link["url"], label=link.get("label"))
        for position, link in enumerate(payload_links)
    ]


def apply(row: Author, values: dict) -> None:
    """Write what was sent. `links`, when sent, replaces every link: the old
    rows are orphans and go in the same flush, which is why `position` has no
    unique constraint."""
    for field, value in values.items():
        if field == "links":
            row.links = _links(value)
        else:
            setattr(row, field, value)


def recipe_counts(db: Session) -> dict[int, int]:
    """Distinct recipes per author: a recipe whose two sources both name the
    author counts once. `usage_count` counts the sources instead, because
    those are what would stop a delete."""
    rows = (
        db.query(RecipeSource.author_id, func.count(func.distinct(RecipeSource.recipe_id)))
        .filter(RecipeSource.author_id.isnot(None))
        .group_by(RecipeSource.author_id)
        .all()
    )
    return dict(rows)


def extra(db: Session):
    """What a list row adds to its columns: the recipe count and the cover
    (the first gallery picture). One count query for the whole list."""
    counts = recipe_counts(db)

    def fields(row: Author) -> dict:
        return {"recipe_count": counts.get(row.id, 0), "cover": images.cover(row.images)}

    return fields


def get(db: Session, author_id: int) -> Author:
    row = db.query(Author).options(*load).filter(Author.id == author_id).one_or_none()
    if row is None:
        raise AppError(404, "No such author.")
    return row


def cascade_counts(db: Session, author_id: int) -> dict[str, int]:
    """What would refuse a delete: the `sources` naming the author, and the
    distinct `recipes` they belong to (the number a person recognises).
    Nothing else is counted - the links and the gallery go with the author,
    and the pictures stay in the library."""
    sources = db.query(RecipeSource).filter(RecipeSource.author_id == author_id).count()
    return {"sources": sources, "recipes": recipe_counts(db).get(author_id, 0)}
