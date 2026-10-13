"""What an author has that the other eight vocabularies do not: a remark and
links. The vocabulary factory (app/routers/vocabulary.py) calls `apply` to
write a create or an update and `load` to read the links with the list.
"""

from sqlalchemy.orm import selectinload

from app.models import Author, AuthorLink

# The list reads every author's links in one more query, not one per author.
load = (selectinload(Author.links),)


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
