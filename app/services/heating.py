"""加熱: reading the page, saving one note, and reordering them all.

Every refusal comes before anything is written, so a refused save changes
nothing - the order of the TBD service, which this one mirrors.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import HeatingNote


def listed(db: Session) -> list[HeatingNote]:
    """The page, in the owner's order; a tie falls back to the older note."""
    return db.query(HeatingNote).order_by(HeatingNote.sort_order, HeatingNote.id).all()


def get(db: Session, note_id: int) -> HeatingNote:
    row = db.get(HeatingNote, note_id)
    if row is None:
        raise AppError(404, "No such note.")
    return row


def create(db: Session, payload) -> HeatingNote:
    """A new note goes last on the page."""
    last = db.query(func.max(HeatingNote.sort_order)).scalar()
    note = HeatingNote(
        name=payload.name,
        body=payload.body,
        sort_order=0 if last is None else last + 1,
    )
    db.add(note)
    db.commit()
    return get(db, note.id)


def update(db: Session, note_id: int, payload) -> HeatingNote:
    note = get(db, note_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(note, field, value)
    db.commit()
    return get(db, note_id)


def delete(db: Session, note_id: int) -> None:
    db.delete(get(db, note_id))
    db.commit()


def reorder(db: Session, ids: list[int]) -> list[HeatingNote]:
    """Number the notes 0, 1, 2 ... in the order of `ids`.

    `ids` must be exactly the notes on the page, each once - anything else is
    a client that has lost track of the page, and is refused rather than
    guessed at, as TBD's reorder is.
    """
    rows = {row.id: row for row in db.query(HeatingNote)}
    if len(set(ids)) != len(ids) or set(ids) != set(rows):
        raise AppError(422, "The order must list every note on the page exactly once.")
    for position, note_id in enumerate(ids):
        rows[note_id].sort_order = position
    db.commit()
    return listed(db)
