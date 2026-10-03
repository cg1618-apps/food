"""TBD: a standalone page of names and links. Reads are public; writes sit
behind Access.

The page is read whole - there is no detail route, because an entry is never
opened on its own - and edited one entry at a time, plus one call that saves
the order of them all after a drag.
"""

from fastapi import Depends, Response
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import TbdEntry
from app.routing import read_router, write_router
from app.services import tbd

router = read_router("tbd", "TBD")
edit = write_router("tbd", "TBD")


def _response(row: TbdEntry) -> schemas.TbdEntryResponse:
    return schemas.TbdEntryResponse(
        id=row.id,
        name=row.name,
        links=[
            schemas.TbdLinkResponse(id=link.id, url=link.url, label=link.label)
            for link in row.links
        ],
        sort_order=row.sort_order,
    )


@router.get("", response_model=list[schemas.TbdEntryResponse])
def list_tbd(db: Session = Depends(get_db)):
    """Every entry, in the owner's order: a bare array."""
    return [_response(row) for row in tbd.listed(db)]


# Registered before the /{entry_id} routes, so "order" is never read as an id.
@edit.put("/order", response_model=list[schemas.TbdEntryResponse])
def reorder_tbd(payload: schemas.TbdOrderIn, db: Session = Depends(get_db)):
    """Save the order after a drag; answers the page. `ids` must be exactly
    the current entries, each once, or it is a 422 and changes nothing."""
    return [_response(row) for row in tbd.reorder(db, payload.ids)]


@edit.post("", response_model=schemas.TbdEntryResponse, status_code=201)
def create_tbd_entry(payload: schemas.TbdEntryCreate, db: Session = Depends(get_db)):
    return _response(tbd.create(db, payload))


@edit.patch("/{entry_id}", response_model=schemas.TbdEntryResponse)
def update_tbd_entry(
    entry_id: int, payload: schemas.TbdEntryUpdate, db: Session = Depends(get_db)
):
    return _response(tbd.update(db, entry_id, payload))


@edit.delete("/{entry_id}", status_code=204)
def delete_tbd_entry(entry_id: int, db: Session = Depends(get_db)):
    tbd.delete(db, entry_id)
    return Response(status_code=204)
