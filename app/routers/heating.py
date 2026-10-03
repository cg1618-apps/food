"""加熱: a standalone page of heating notes. Reads are public; writes sit
behind Access.

Shaped as TBD's: read whole - a note is never opened on its own - edited one
note at a time, plus one call that saves the order of them all after a drag.
"""

from fastapi import Depends, Response
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import HeatingNote
from app.routing import read_router, write_router
from app.services import heating

router = read_router("heating", "加熱")
edit = write_router("heating", "加熱")


def _response(row: HeatingNote) -> schemas.HeatingNoteResponse:
    return schemas.HeatingNoteResponse(
        id=row.id, name=row.name, body=row.body, sort_order=row.sort_order
    )


@router.get("", response_model=list[schemas.HeatingNoteResponse])
def list_heating(db: Session = Depends(get_db)):
    """Every note, in the owner's order: a bare array."""
    return [_response(row) for row in heating.listed(db)]


# Registered before the /{note_id} routes, so "order" is never read as an id.
@edit.put("/order", response_model=list[schemas.HeatingNoteResponse])
def reorder_heating(payload: schemas.HeatingOrderIn, db: Session = Depends(get_db)):
    """Save the order after a drag; answers the page. `ids` must be exactly
    the current notes, each once, or it is a 422 and changes nothing."""
    return [_response(row) for row in heating.reorder(db, payload.ids)]


@edit.post("", response_model=schemas.HeatingNoteResponse, status_code=201)
def create_heating_note(payload: schemas.HeatingNoteCreate, db: Session = Depends(get_db)):
    return _response(heating.create(db, payload))


@edit.patch("/{note_id}", response_model=schemas.HeatingNoteResponse)
def update_heating_note(
    note_id: int, payload: schemas.HeatingNoteUpdate, db: Session = Depends(get_db)
):
    return _response(heating.update(db, note_id, payload))


@edit.delete("/{note_id}", status_code=204)
def delete_heating_note(note_id: int, db: Session = Depends(get_db)):
    heating.delete(db, note_id)
    return Response(status_code=204)
