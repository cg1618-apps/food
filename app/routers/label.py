"""Labels: the cross-cutting tags, and the second section of the edit page."""

from fastapi import Depends, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.errors import AppError
from app.models import IngredientLabel, KitchenNoteLabel, Label, RecipeLabel
from app.routing import read_router, write_router

router = read_router("labels", "Labels")
edit = write_router("labels", "Labels")


# Every owner that carries labels, by the response field its count fills.
# A label is one vocabulary across all three, so a count over one link table
# would tell the settings page a label is unused while recipes carry it.
_LINK_TABLES = {
    "ingredient_count": IngredientLabel,
    "recipe_count": RecipeLabel,
    "note_count": KitchenNoteLabel,
}

Counts = dict[str, dict[int, int]]


def _counts(db: Session) -> Counts:
    """Links per label, per owner: one GROUP BY per link table, not per label."""
    return {
        field: dict(db.query(link.label_id, func.count()).group_by(link.label_id).all())
        for field, link in _LINK_TABLES.items()
    }


def _response(label: Label, counts: Counts) -> schemas.LabelResponse:
    per_owner = {field: counts.get(field, {}).get(label.id, 0) for field in _LINK_TABLES}
    return schemas.LabelResponse(
        id=label.id,
        display_name=label.display_name,
        name_cn=label.name_cn,
        name_en=label.name_en,
        usage_count=sum(per_owner.values()),
        **per_owner,
    )


@router.get("", response_model=list[schemas.LabelResponse])
def list_labels(db: Session = Depends(get_db)):
    counts = _counts(db)
    rows = db.query(Label).all()
    rows.sort(key=lambda r: r.display_name.casefold())
    return [_response(row, counts) for row in rows]


@edit.post("", response_model=schemas.LabelResponse, status_code=201)
def create_label(payload: schemas.LabelCreate, db: Session = Depends(get_db)):
    label = Label(name_cn=payload.name_cn, name_en=payload.name_en)
    db.add(label)
    db.commit()
    db.refresh(label)
    return _response(label, {})


@edit.patch("/{label_id}", response_model=schemas.LabelResponse)
def update_label(label_id: int, payload: schemas.LabelUpdate, db: Session = Depends(get_db)):
    label = db.query(Label).filter_by(id=label_id).one_or_none()
    if label is None:
        raise AppError(404, "No such label.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(label, field, value)

    if not any((label.name_cn, label.name_en)):
        raise AppError(422, "A label needs at least one name.")

    db.commit()
    db.refresh(label)
    return _response(label, _counts(db))


@edit.delete("/{label_id}", status_code=204)
def delete_label(
    label_id: int,
    db: Session = Depends(get_db),
):
    """Deleting a label detaches it from every ingredient, recipe and note
    carrying it.

    That is a CASCADE on the link table and it is the right behaviour - a label
    is a tag, and removing the tag from the vocabulary means removing it from
    the things tagged. No count is required here because nothing is lost but
    the links themselves: no ingredient is touched, and re-tagging is typing
    the label again.
    """
    label = db.query(Label).filter_by(id=label_id).one_or_none()
    if label is None:
        raise AppError(404, "No such label.")
    db.delete(label)
    db.commit()
    return Response(status_code=204)
