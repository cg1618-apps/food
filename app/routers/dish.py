"""The dish library. Reads are public; writes sit behind Access.

The recipe router's shape: a read router and a write router from
`app.routing`, a response built explicitly, and a delete that takes the
counts its dialog showed.
"""

from fastapi import Depends, Query, Response
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.errors import AppError, StaleCountError
from app.models import Dish, DishImage
from app.routers.recipe import recipe_ref, summary
from app.routing import read_router, write_router
from app.services import dishes, images, schedule

router = read_router("dishes", "Dishes")
edit = write_router("dishes", "Dishes")


def _ref(value) -> schemas.VocabRef | None:
    return schemas.VocabRef(id=value.id, display_name=value.display_name) if value else None


def _vocab(rows) -> list[schemas.VocabRef]:
    return [schemas.VocabRef(id=r.id, display_name=r.display_name) for r in rows]


def _summary(row: Dish) -> schemas.DishSummary:
    return schemas.DishSummary(
        id=row.id,
        display_name=row.display_name,
        name_cn=row.name_cn,
        name_en=row.name_en,
        name_alt=row.name_alt,
        kind=row.kind,
        course=_ref(row.course),
        region=_ref(row.region),
        labels=_vocab(row.labels),
        recipe_count=len(row.recipes),
        cover=dishes.cover(row),
    )


def _response(db: Session, row: Dish) -> schemas.DishResponse:
    return schemas.DishResponse(
        id=row.id,
        display_name=row.display_name,
        name_cn=row.name_cn,
        name_en=row.name_en,
        name_alt=row.name_alt,
        kind=row.kind,
        course=_ref(row.course),
        region=_ref(row.region),
        description=row.description,
        aliases=sorted(alias.value for alias in row.aliases),
        serves_as=_vocab(row.serves_as),
        labels=_vocab(row.labels),
        images=images.attached(row.images),
        recipes=[
            summary(r) for r in sorted(row.recipes, key=lambda r: (r.display_name.casefold(), r.id))
        ],
        used_in=[recipe_ref(r) for r in dishes.used_in(db, row.id)],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ==========================================
# PUBLIC READS
# ==========================================


@router.get("", response_model=list[schemas.DishSummary])
def list_dishes(
    q: str | None = Query(default=None, description="Matches any name slot or an alias"),
    kind: list[str] | None = Query(None),
    course_id: list[int] | None = Query(None),
    region_id: list[int] | None = Query(None),
    label_id: list[int] | None = Query(None),
    db: Session = Depends(get_db),
):
    """The library: a bare array sorted by display name. A repeated parameter
    means "any of" its values."""
    rows = dishes.search(
        db, q=q, kind=kind, course_id=course_id, region_id=region_id, label_id=label_id
    )
    return [_summary(row) for row in rows]


@router.get("/{dish_id}", response_model=schemas.DishResponse)
def get_dish(dish_id: int, db: Session = Depends(get_db)):
    return _response(db, dishes.get(db, dish_id))


@router.get("/{dish_id}/cascade", response_model=dict)
def cascade_preview(dish_id: int, db: Session = Depends(get_db)):
    """What deleting this would remove (`aliases`), and the three counts that
    refuse it (`recipes`, `used_in`, `meals`). Only `aliases` is echoed on the
    delete."""
    dishes.get(db, dish_id)
    return dishes.cascade_counts(db, dish_id)


# ==========================================
# WRITES - behind Cloudflare Access
# ==========================================


@edit.post("", response_model=schemas.DishResponse, status_code=201)
def create_dish(payload: schemas.DishCreate, db: Session = Depends(get_db)):
    return _response(db, dishes.create(db, payload))


@edit.patch("/{dish_id}", response_model=schemas.DishResponse)
def update_dish(dish_id: int, payload: schemas.DishUpdate, db: Session = Depends(get_db)):
    return _response(db, dishes.update(db, dish_id, payload))


@edit.delete("/{dish_id}", status_code=204)
def delete_dish(
    dish_id: int,
    aliases: int = Query(..., description="Alias count the dialog showed"),
    db: Session = Depends(get_db),
):
    """Delete, with the alias count the user was shown echoed back.

    A dish with recipes, one a recipe's line names, or one a meal on the
    schedule names is refused BEFORE the database is asked, with those recipes
    and the meals' dates on the body - the RESTRICT would refuse too, but
    could only say that something refers to it, not what.
    """
    dish = dishes.get(db, dish_id)
    users = dishes.used_in(db, dish_id)
    meal_dates = schedule.meal_dates(db, dish_id)
    if dish.recipes or users or meal_dates:
        raise AppError(
            409,
            "This dish still has recipes, recipes use it, or the schedule names it,"
            " so it cannot be removed.",
            recipes=[{"id": r.id, "display_name": r.display_name} for r in dish.recipes],
            used_in=[{"id": r.id, "display_name": r.display_name} for r in users],
            meals=[d.isoformat() for d in meal_dates],
        )

    actual = dishes.cascade_counts(db, dish_id)["aliases"]
    if actual != aliases:
        raise StaleCountError("aliases", "aliases", aliases, actual)

    db.delete(dish)
    db.commit()
    return Response(status_code=204)


@edit.put("/{dish_id}/images", response_model=schemas.DishResponse)
def set_dish_images(
    dish_id: int,
    payload: list[schemas.ImageAttachmentIn],
    db: Session = Depends(get_db),
):
    """Replace the gallery, in order. Position 0 is the cover."""
    dish = dishes.get(db, dish_id)
    images.set_images(db, dish, "images", DishImage, payload)
    return _response(db, dishes.get(db, dish_id))
