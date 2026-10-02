"""Kitchen notes. Reads are public; writes sit behind Access.

The recipe router's shape, without a cascade preview: a delete takes nothing
the user would miss - label links and gallery rows, while the pictures stay in
the library - so there are no counts to show or to echo back.
"""

from fastapi import Depends, Query, Response
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import KitchenNote, KitchenNoteImage
from app.routing import read_router, write_router
from app.services import images, kitchen_notes

router = read_router("kitchen-notes", "Kitchen notes")
edit = write_router("kitchen-notes", "Kitchen notes")


def _labels(row: KitchenNote) -> list[schemas.VocabRef]:
    return [schemas.VocabRef(id=r.id, display_name=r.display_name) for r in row.labels]


def _summary(row: KitchenNote) -> schemas.KitchenNoteSummary:
    return schemas.KitchenNoteSummary(
        id=row.id,
        title=row.title,
        kind=row.kind,
        url=row.url,
        labels=_labels(row),
        cover=images.cover(row.images),
    )


def _response(row: KitchenNote) -> schemas.KitchenNoteResponse:
    return schemas.KitchenNoteResponse(
        id=row.id,
        title=row.title,
        kind=row.kind,
        url=row.url,
        body=row.body,
        labels=_labels(row),
        images=images.attached(row.images),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ==========================================
# PUBLIC READS
# ==========================================


@router.get("", response_model=list[schemas.KitchenNoteSummary])
def list_kitchen_notes(
    q: str | None = Query(default=None, description="Matches the title or the body"),
    kind: list[str] | None = Query(None),
    label_id: list[int] | None = Query(None),
    db: Session = Depends(get_db),
):
    """The library: a bare array, newest first. A repeated parameter means
    "any of" its values."""
    return [_summary(row) for row in kitchen_notes.search(db, q=q, kind=kind, label_id=label_id)]


@router.get("/{note_id}", response_model=schemas.KitchenNoteResponse)
def get_kitchen_note(note_id: int, db: Session = Depends(get_db)):
    return _response(kitchen_notes.get(db, note_id))


# ==========================================
# WRITES - behind Cloudflare Access
# ==========================================


@edit.post("", response_model=schemas.KitchenNoteResponse, status_code=201)
def create_kitchen_note(payload: schemas.KitchenNoteCreate, db: Session = Depends(get_db)):
    return _response(kitchen_notes.create(db, payload))


@edit.patch("/{note_id}", response_model=schemas.KitchenNoteResponse)
def update_kitchen_note(
    note_id: int, payload: schemas.KitchenNoteUpdate, db: Session = Depends(get_db)
):
    return _response(kitchen_notes.update(db, note_id, payload))


@edit.delete("/{note_id}", status_code=204)
def delete_kitchen_note(note_id: int, db: Session = Depends(get_db)):
    """Delete, with no counts to confirm: see the module docstring."""
    db.delete(kitchen_notes.get(db, note_id))
    db.commit()
    return Response(status_code=204)


@edit.put("/{note_id}/images", response_model=schemas.KitchenNoteResponse)
def set_kitchen_note_images(
    note_id: int,
    payload: list[schemas.ImageAttachmentIn],
    db: Session = Depends(get_db),
):
    """Replace the gallery, in order. Position 0 is the cover."""
    note = kitchen_notes.get(db, note_id)
    images.set_images(db, note, "images", KitchenNoteImage, payload)
    return _response(kitchen_notes.get(db, note_id))
