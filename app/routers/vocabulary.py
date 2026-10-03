"""One factory, eight vocabularies. Reads are public; writes sit behind Access.

A delete of a value still in use is refused here with a 409 that carries the
count, before the database is asked. The RESTRICT foreign keys are the
backstop, and through the IntegrityError handler they would only be able to
say "something still refers to this".
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app import schemas
from app.constants import FIXED_VOCABULARIES
from app.database import get_db
from app.errors import AppError
from app.models import (
    Author,
    CookingMethod,
    Equipment,
    LineGroup,
    RecipeCourse,
    RecipeStatus,
    SourcePlatform,
    StepGroup,
)
from app.routing import read_router, write_router
from app.services import vocabularies


def _response(row, counts: dict[int, int]) -> schemas.VocabularyResponse:
    return schemas.VocabularyResponse(
        id=row.id,
        display_name=row.display_name,
        name_cn=row.name_cn,
        name_en=row.name_en,
        sort_order=row.sort_order,
        usage_count=counts.get(row.id, 0),
    )


def build(model, resource: str, tag: str, noun: str) -> tuple[APIRouter, APIRouter]:
    router = read_router(resource, tag)
    edit = write_router(resource, tag)

    def _get(db: Session, row_id: int):
        row = db.query(model).filter(model.id == row_id).one_or_none()
        if row is None:
            raise AppError(404, f"No such {noun}.")
        return row

    @router.get("", response_model=list[schemas.VocabularyResponse])
    def list_values(db: Session = Depends(get_db)):
        counts = vocabularies.usage(db, model)
        rows = db.query(model).all()
        rows.sort(key=lambda r: (r.sort_order, r.display_name.casefold()))
        return [_response(row, counts) for row in rows]

    @edit.post("", response_model=schemas.VocabularyResponse, status_code=201)
    def create_value(payload: schemas.VocabularyCreate, db: Session = Depends(get_db)):
        row = model(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return _response(row, {})

    @edit.patch("/{row_id}", response_model=schemas.VocabularyResponse)
    def update_value(
        row_id: int, payload: schemas.VocabularyUpdate, db: Session = Depends(get_db)
    ):
        row = _get(db, row_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        if not any((row.name_cn, row.name_en)):
            raise AppError(422, f"A {noun} needs at least one name.")
        db.commit()
        db.refresh(row)
        return _response(row, vocabularies.usage(db, model))

    @edit.delete("/{row_id}", status_code=204)
    def delete_value(row_id: int, db: Session = Depends(get_db)):
        row = _get(db, row_id)
        in_use = vocabularies.usage(db, model).get(row.id, 0)
        if in_use:
            raise AppError(
                409,
                f"{row.display_name} is still used in {in_use} place(s); "
                "change those first.",
                usage_count=in_use,
            )
        db.delete(row)
        db.commit()
        return Response(status_code=204)

    return router, edit


course_router, course_edit = build(RecipeCourse, "recipe-courses", "Recipe courses", "course")
status_router, status_edit = build(RecipeStatus, "recipe-statuses", "Recipe statuses", "status")
platform_router, platform_edit = build(
    SourcePlatform, "source-platforms", "Source platforms", "source platform"
)
method_router, method_edit = build(
    CookingMethod, "cooking-methods", "Cooking methods", "cooking method"
)
equipment_router, equipment_edit = build(Equipment, "equipment", "Equipment", "piece of equipment")
# Listed by name: every author has sort_order 0 (app/models/vocabulary.py), so
# the (sort_order, name) order above needs nothing of its own.
author_router, author_edit = build(Author, "authors", "Authors", "author")
# Hand-ordered like courses: the order is the one the recipe form offers them
# in when a group is added.
line_group_router, line_group_edit = build(LineGroup, "line-groups", "Line groups", "line group")
step_group_router, step_group_edit = build(StepGroup, "step-groups", "Step groups", "step group")

fixed_router = read_router("vocabularies", "Vocabularies")


@fixed_router.get("/fixed")
def fixed_vocabularies():
    """Every closed list, with display labels, so no component copies one."""
    return FIXED_VOCABULARIES


ROUTERS = [
    course_router,
    course_edit,
    status_router,
    status_edit,
    platform_router,
    platform_edit,
    method_router,
    method_edit,
    equipment_router,
    equipment_edit,
    author_router,
    author_edit,
    line_group_router,
    line_group_edit,
    step_group_router,
    step_group_edit,
    fixed_router,
]
