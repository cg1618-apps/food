"""The image library. Reading is public; uploading and deleting sit behind Access."""

from fastapi import Depends, File, Query, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.errors import AppError
from app.models import Image
from app.routing import read_router, write_router
from app.services import images

router = read_router("images", "Images")
edit = write_router("images", "Images")


def _summary(row: Image, counts: dict[int, int]) -> schemas.ImageSummary:
    return schemas.ImageSummary(
        id=row.id,
        url=images.image_url(row.storage_key),
        thumb_url=images.image_url(row.thumb_key),
        width=row.width,
        height=row.height,
        byte_size=row.byte_size,
        original_filename=row.original_filename,
        uploaded_at=row.uploaded_at,
        attachment_count=counts.get(row.id, 0),
    )


def _get(db: Session, image_id: int) -> Image:
    row = db.query(Image).filter(Image.id == image_id).one_or_none()
    if row is None:
        raise AppError(404, "No such image.")
    return row


@router.get("", response_model=list[schemas.ImageSummary])
def list_images(
    unused: bool | None = None,
    limit: int = Query(default=60, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Newest first. `unused` filters in SQL, before the page is cut.

    The filter must not run in Python after limit/offset - that silently
    shortens pages (docs/notes/decisions.md, "a row-hiding filter belongs in
    SQL").
    """
    counts = images.attachment_counts(db)
    query = db.query(Image)
    if unused is not None:
        used_ids = list(counts)
        query = query.filter(~Image.id.in_(used_ids) if unused else Image.id.in_(used_ids))
    rows = query.order_by(Image.uploaded_at.desc(), Image.id.desc()).offset(offset).limit(limit)
    return [_summary(row, counts) for row in rows]


@router.get("/{image_id}", response_model=schemas.ImageDetail)
def get_image(image_id: int, db: Session = Depends(get_db)):
    row = _get(db, image_id)
    attached = images.owners(db, image_id)
    return schemas.ImageDetail(
        **_summary(row, {row.id: len(attached)}).model_dump(), owners=attached
    )


@edit.post("", response_model=schemas.ImageSummary, status_code=201)
def upload_image(file: UploadFile = File(...), db: Session = Depends(get_db)):
    row, created = images.store_upload(db, file)
    body = _summary(row, images.attachment_counts(db)).model_dump(mode="json")
    return JSONResponse(status_code=201 if created else 200, content=body)


@edit.delete("/{image_id}", status_code=204)
def delete_image(image_id: int, db: Session = Depends(get_db)):
    images.delete_image(db, _get(db, image_id))
    return Response(status_code=204)
