"""常用食材: reading the structure - 未分組, then the groups - and replacing it
whole."""

from uuid import uuid4

from sqlalchemy.orm import Session, joinedload

from app.errors import AppError
from app.models import CommonIngredient, CommonIngredientGroup, Ingredient
from app.services.lookup import fetch_all


def listed(db: Session) -> tuple[list[CommonIngredient], list[tuple[CommonIngredientGroup, list]]]:
    """(the ungrouped chips, [(group, its chips)]), each in order."""
    groups = (
        db.query(CommonIngredientGroup)
        .order_by(CommonIngredientGroup.sort_order, CommonIngredientGroup.id)
        .all()
    )
    chips = (
        db.query(CommonIngredient)
        .options(joinedload(CommonIngredient.ingredient))
        .order_by(CommonIngredient.sort_order, CommonIngredient.ingredient_id)
        .all()
    )
    by_group: dict[int | None, list[CommonIngredient]] = {}
    for chip in chips:
        by_group.setdefault(chip.group_id, []).append(chip)
    return by_group.get(None, []), [(group, by_group.get(group.id, [])) for group in groups]


def replace(db: Session, payload):
    """Make the structure exactly `payload`: 未分組's chips and each group's
    numbered 0, 1, 2 … in the order sent, the groups too.

    A group sent with an id is that group, renamed and moved; one without is
    created; a stored group not sent is deleted - its chips are wherever the
    payload put them (設定 sends them at the end of 未分組).

    Repeats are refused rather than collapsed: an ingredient named twice
    anywhere, a group id named twice, two groups with one name in any case.
    Each is a client that has lost track of the structure, and quietly keeping
    one would save an arrangement nobody sent. Every refusal comes before
    anything is written.
    """
    every_id = list(payload.ungrouped)
    for group in payload.groups:
        every_id.extend(group.ingredient_ids)
    if len(set(every_id)) != len(every_id):
        raise AppError(422, "An ingredient can be on the list only once.")
    fetch_all(db, Ingredient, every_id, "ingredient")

    group_ids = [group.id for group in payload.groups if group.id is not None]
    if len(set(group_ids)) != len(group_ids):
        raise AppError(422, "A group can be sent only once.")
    names = [group.name.lower() for group in payload.groups]
    if len(set(names)) != len(names):
        raise AppError(422, "Two groups cannot share one name.")
    kept = {row.id: row for row in fetch_all(db, CommonIngredientGroup, group_ids, "group")}

    db.query(CommonIngredient).delete(synchronize_session="fetch")
    db.query(CommonIngredientGroup).filter(
        CommonIngredientGroup.id.notin_(list(kept))
    ).delete(synchronize_session="fetch")
    # The unique index on lower(name) is checked row by row, so two groups
    # swapping names would collide halfway. A renamed group passes through a
    # name nobody can have first.
    renamed = [g for g in payload.groups if g.id is not None and kept[g.id].name != g.name]
    for group in renamed:
        kept[group.id].name = f"~{uuid4()}"
    db.flush()

    for position, group in enumerate(payload.groups):
        row = kept.get(group.id) if group.id is not None else None
        if row is None:
            row = CommonIngredientGroup()
            db.add(row)
        row.name = group.name
        row.sort_order = position
        db.flush()
        db.add_all(
            CommonIngredient(ingredient_id=ingredient_id, group_id=row.id, sort_order=index)
            for index, ingredient_id in enumerate(group.ingredient_ids)
        )
    db.add_all(
        CommonIngredient(ingredient_id=ingredient_id, group_id=None, sort_order=index)
        for index, ingredient_id in enumerate(payload.ungrouped)
    )
    db.commit()
    return listed(db)
