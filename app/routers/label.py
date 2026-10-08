"""Labels: the cross-cutting tags, and the second section of the edit page.

Each label belongs to one library - ingredient, dish or note - and is listed,
added and moved within it. See `app/models/label.py`.
"""

from fastapi import Depends, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import schemas
from app.constants import LABEL_SCOPES
from app.database import get_db
from app.errors import AppError
from app.models import DishLabel, IngredientLabel, KitchenNoteLabel, Label
from app.routing import read_router, write_router

router = read_router("labels", "Labels")
edit = write_router("labels", "Labels")


# Every owner that carries labels, by the response field its count fills.
# A label is linked only from its own scope's table, but all three are
# counted: the move refusal reads the total, and a count that trusted the
# scope would call a label unused on the strength of the rule it guards.
_LINK_TABLES = {
    "ingredient_count": IngredientLabel,
    "dish_count": DishLabel,
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
        scope=label.scope,
        usage_count=sum(per_owner.values()),
        **per_owner,
    )


@router.get("", response_model=list[schemas.LabelResponse])
def list_labels(
    scope: str | None = Query(None, description="Only the labels of this library"),
    db: Session = Depends(get_db),
):
    query = db.query(Label)
    if scope is not None:
        if scope not in LABEL_SCOPES:
            raise AppError(422, f"A label scope is one of {', '.join(LABEL_SCOPES)}.")
        query = query.filter(Label.scope == scope)
    counts = _counts(db)
    rows = query.all()
    rows.sort(key=lambda r: r.display_name.casefold())
    return [_response(row, counts) for row in rows]


@edit.post("", response_model=schemas.LabelResponse, status_code=201)
def create_label(payload: schemas.LabelCreate, db: Session = Depends(get_db)):
    label = Label(name_cn=payload.name_cn, name_en=payload.name_en, scope=payload.scope)
    db.add(label)
    db.commit()
    db.refresh(label)
    return _response(label, {})


@edit.patch("/{label_id}", response_model=schemas.LabelResponse)
def update_label(label_id: int, payload: schemas.LabelUpdate, db: Session = Depends(get_db)):
    label = db.query(Label).filter_by(id=label_id).one_or_none()
    if label is None:
        raise AppError(404, "No such label.")

    changes = payload.model_dump(exclude_unset=True)
    counts = _counts(db)
    if changes.get("scope", label.scope) != label.scope:
        # Moving a label in use would leave its owners carrying another
        # library's label. Refused as deleting an in-use value is, with the
        # count, so the page can say why.
        in_use = _response(label, counts).usage_count
        if in_use:
            raise AppError(
                409,
                f"{label.display_name} is still used in {in_use} place(s); "
                "remove it from those before moving it to another library.",
                usage_count=in_use,
            )

    for field, value in changes.items():
        setattr(label, field, value)

    if not any((label.name_cn, label.name_en)):
        raise AppError(422, "A label needs at least one name.")

    db.commit()
    db.refresh(label)
    return _response(label, counts)


@edit.delete("/{label_id}", status_code=204)
def delete_label(
    label_id: int,
    db: Session = Depends(get_db),
):
    """Deleting a label detaches it from every ingredient, dish and note
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
