"""TBD: reading the page, saving one entry, and reordering them all.

Every refusal comes before anything is written, so a refused save changes
nothing - the order of the recipe and kitchen-note services.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError
from app.models import TbdEntry, TbdLink

NEEDS_CONTENT = "An entry needs a name or at least one link."


def listed(db: Session) -> list[TbdEntry]:
    """The page, in the owner's order; a tie falls back to the older entry."""
    return (
        db.query(TbdEntry)
        .options(selectinload(TbdEntry.links))
        .order_by(TbdEntry.sort_order, TbdEntry.id)
        .all()
    )


def get(db: Session, entry_id: int) -> TbdEntry:
    row = (
        db.query(TbdEntry)
        .options(selectinload(TbdEntry.links))
        .filter(TbdEntry.id == entry_id)
        .one_or_none()
    )
    if row is None:
        raise AppError(404, "No such entry.")
    return row


def _links(payload_links) -> list[TbdLink]:
    return [
        TbdLink(position=position, url=link.url, label=link.label)
        for position, link in enumerate(payload_links)
    ]


def _check_content(name: str | None, links: list) -> None:
    if name is None and not links:
        raise AppError(422, NEEDS_CONTENT)


def create(db: Session, payload) -> TbdEntry:
    """A new entry goes last on the page."""
    _check_content(payload.name, payload.links)
    last = db.query(func.max(TbdEntry.sort_order)).scalar()
    entry = TbdEntry(
        name=payload.name,
        sort_order=0 if last is None else last + 1,
        links=_links(payload.links),
    )
    db.add(entry)
    db.commit()
    return get(db, entry.id)


def update(db: Session, entry_id: int, payload) -> TbdEntry:
    entry = get(db, entry_id)
    sent = payload.model_dump(exclude_unset=True)
    name = sent["name"] if "name" in sent else entry.name
    links = payload.links if "links" in sent else entry.links
    _check_content(name, links)

    if "name" in sent:
        entry.name = name
    if "links" in sent:
        # Replaced wholesale: the old rows are orphans and go in this flush.
        entry.links = _links(payload.links)
    db.commit()
    return get(db, entry_id)


def delete(db: Session, entry_id: int) -> None:
    db.delete(get(db, entry_id))
    db.commit()


def reorder(db: Session, ids: list[int]) -> list[TbdEntry]:
    """Number the entries 0, 1, 2 … in the order of `ids`.

    `ids` must be exactly the entries on the page, each once. Anything else
    is a client that has lost track of the page - an entry added or deleted
    in another tab - and saving it would drop or invent a place, so it is
    refused rather than guessed at.
    """
    rows = {row.id: row for row in db.query(TbdEntry)}
    if len(set(ids)) != len(ids) or set(ids) != set(rows):
        raise AppError(422, "The order must list every entry on the page exactly once.")
    for position, entry_id in enumerate(ids):
        rows[entry_id].sort_order = position
    db.commit()
    return listed(db)
