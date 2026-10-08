"""Reading and writing kitchen notes. The router does HTTP; this does the work.

The recipe service's order, at a smaller scale: every id the body names is
resolved before the row is touched, so a refused save writes nothing.
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError
from app.models import KitchenNote, KitchenNoteImage, KitchenNoteLabel
from app.services.lookup import fetch_labels
from app.services.search import ESCAPE, contains


def _loaded(query):
    """Everything a list row or the full note reads, one round trip each."""
    return query.options(
        selectinload(KitchenNote.labels),
        selectinload(KitchenNote.images).selectinload(KitchenNoteImage.image),
    )


def get(db: Session, note_id: int) -> KitchenNote:
    row = _loaded(db.query(KitchenNote)).filter(KitchenNote.id == note_id).one_or_none()
    if row is None:
        raise AppError(404, "No such kitchen note.")
    return row


def search(
    db: Session,
    q: str | None = None,
    kind: list[str] | None = None,
    label_id: list[int] | None = None,
) -> list[KitchenNote]:
    """The library list, newest first. `kind` and `label_id` each mean "any
    of" their values; different filters narrow each other. The label filter is
    a subquery rather than a join, so a note carrying two of the labels is
    returned once."""
    query = _loaded(db.query(KitchenNote))
    if q:
        term = contains(q)
        query = query.filter(
            or_(
                KitchenNote.title.ilike(term, escape=ESCAPE),
                KitchenNote.body.ilike(term, escape=ESCAPE),
            )
        )
    if kind:
        query = query.filter(KitchenNote.kind.in_(kind))
    if label_id:
        query = query.filter(
            KitchenNote.id.in_(
                select(KitchenNoteLabel.kitchen_note_id)
                .where(KitchenNoteLabel.label_id.in_(label_id))
                .scalar_subquery()
            )
        )
    return query.order_by(KitchenNote.created_at.desc(), KitchenNote.id.desc()).all()


def create(db: Session, payload) -> KitchenNote:
    labels = fetch_labels(db, payload.label_ids, "note")
    note = KitchenNote(**payload.model_dump(exclude={"label_ids"}))
    note.labels = labels
    db.add(note)
    db.commit()
    return get(db, note.id)


def update(db: Session, note_id: int, payload) -> KitchenNote:
    note = get(db, note_id)
    sent = payload.model_dump(exclude_unset=True)
    label_ids = sent.pop("label_ids", None)
    labels = None if label_ids is None else fetch_labels(db, label_ids, "note")

    for field, value in sent.items():
        setattr(note, field, value)
    if labels is not None:
        note.labels = labels
    db.commit()
    return get(db, note_id)
