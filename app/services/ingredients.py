"""Reading, searching and writing ingredients. The router does HTTP; this does
the work.

Search is ILIKE across the three name slots and the alias table, and that is
the whole of it - a few hundred rows, so no trigram, no tsvector, no GIN index.
The same function backs the library page's search box and module 2's typeahead,
because they ask exactly the same question and two implementations of it would
answer differently within a month.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError
from app.models import (
    CookingMethod,
    Ingredient,
    IngredientAlias,
    IngredientHeating,
    IngredientImage,
    IngredientLabel,
    IngredientLink,
    IngredientPreservation,
    Label,
)
from app.services.hierarchy import check_parent


def _loaded(query):
    """Every relationship the response needs, in one round trip each.

    selectinload rather than the default lazy load: a list of 300 ingredients
    rendering its labels would otherwise issue 300 queries, and the count of
    them grows with the data rather than with the code, so nothing in review
    looks wrong.
    """
    return query.options(
        selectinload(Ingredient.category),
        selectinload(Ingredient.parent),
        selectinload(Ingredient.children),
        selectinload(Ingredient.aliases),
        selectinload(Ingredient.preservation),
        selectinload(Ingredient.heating).selectinload(IngredientHeating.method),
        selectinload(Ingredient.links),
        selectinload(Ingredient.images).selectinload(IngredientImage.image),
        selectinload(Ingredient.labels),
    )


def get(db: Session, ingredient_id: int) -> Ingredient:
    row = _loaded(db.query(Ingredient)).filter(Ingredient.id == ingredient_id).one_or_none()
    if row is None:
        raise AppError(404, "No such ingredient.")
    return row


def search(
    db: Session,
    q: str | None = None,
    category_id: int | None = None,
    label_id: int | None = None,
    needs_detail: bool | None = None,
    parent_id: int | None = None,
    rating: str | None = None,
    has_parent: bool | None = None,
) -> list[Ingredient]:
    query = _loaded(db.query(Ingredient))

    if q:
        term = f"%{q.strip()}%"
        # The alias arm is a subquery rather than a join, so that an ingredient
        # matching on two aliases comes back once. A join would duplicate the
        # row per matching alias, and the duplicate only appears for rows with
        # several aliases - which is exactly the data a small test set lacks.
        alias_match = (
            select(IngredientAlias.ingredient_id)
            .where(func.lower(IngredientAlias.value).like(func.lower(term)))
            .scalar_subquery()
        )
        query = query.filter(
            or_(
                Ingredient.name_cn.ilike(term),
                Ingredient.name_en.ilike(term),
                Ingredient.name_alt.ilike(term),
                Ingredient.id.in_(alias_match),
            )
        )

    if category_id is not None:
        query = query.filter(Ingredient.category_id == category_id)
    if parent_id is not None:
        query = query.filter(Ingredient.parent_id == parent_id)
    if needs_detail is not None:
        query = query.filter(Ingredient.needs_detail.is_(needs_detail))
    if rating is not None:
        query = query.filter(Ingredient.rating == rating)
    if has_parent is not None:
        query = query.filter(
            Ingredient.parent_id.isnot(None) if has_parent else Ingredient.parent_id.is_(None)
        )
    if label_id is not None:
        query = query.filter(
            Ingredient.id.in_(
                select(IngredientLabel.ingredient_id)
                .where(IngredientLabel.label_id == label_id)
                .scalar_subquery()
            )
        )

    rows = query.all()
    # Sorted in Python, not SQL: the display name is the first non-empty of
    # three columns, which no single ORDER BY can express. The table is small
    # enough that this costs nothing, and it is the same rule the detail page
    # shows, so the two cannot disagree.
    rows.sort(key=lambda r: r.display_name.casefold())
    return rows


def _apply_labels(db: Session, ingredient: Ingredient, label_ids: list[int]) -> None:
    if not label_ids:
        ingredient.labels = []
        return
    labels = db.query(Label).filter(Label.id.in_(label_ids)).all()
    missing = set(label_ids) - {label.id for label in labels}
    if missing:
        raise AppError(422, f"No such label: {sorted(missing)[0]}.")
    ingredient.labels = labels


def _apply_aliases(ingredient: Ingredient, values: list[str]) -> None:
    """Make the alias rows match `values`, keeping the rows already there.

    Replacing the whole collection looks equivalent and is not: the unit of
    work INSERTs the new rows before it DELETEs the orphaned ones, so re-sending
    an alias the ingredient already has trips uq_ingredient_alias, and a PATCH
    that keeps any existing alias is a 409. Reconciling by value touches only
    what changed.
    """
    wanted = list(dict.fromkeys(values))
    ingredient.aliases = [row for row in ingredient.aliases if row.value in wanted]
    kept = {row.value for row in ingredient.aliases}
    ingredient.aliases.extend(IngredientAlias(value=v) for v in wanted if v not in kept)


def _apply_preservation(ingredient: Ingredient, entries) -> None:
    """Reconcile by (state, method), for the reason `_apply_aliases` gives.

    uq_ingredient_preservation_state_method makes a wholesale replace fail the
    moment a PATCH re-sends a note the ingredient already has.
    """
    existing = {(row.state, row.method): row for row in ingredient.preservation}
    rows = []
    for entry in entries:
        row = existing.get((entry.state, entry.method)) or IngredientPreservation(
            method=entry.method, state=entry.state
        )
        row.duration_min_days = entry.duration_min_days
        row.duration_max_days = entry.duration_max_days
        row.notes = entry.notes
        row.sort_order = entry.sort_order
        rows.append(row)
    ingredient.preservation = rows


def _apply_heating(db: Session, ingredient: Ingredient, entries) -> None:
    method_ids = {entry.method_id for entry in entries}
    found = {
        row.id for row in db.query(CookingMethod.id).filter(CookingMethod.id.in_(method_ids))
    }
    missing = method_ids - found
    if missing:
        raise AppError(422, f"No such cooking method: {sorted(missing)[0]}.")
    ingredient.heating = [
        IngredientHeating(
            method_id=e.method_id,
            temperature_c=e.temperature_c,
            duration=e.duration,
            preheat=e.preheat,
            flip=e.flip,
            notes=e.notes,
            sort_order=position,
        )
        for position, e in enumerate(entries)
    ]


def _apply_links(ingredient: Ingredient, entries) -> None:
    ingredient.links = [
        IngredientLink(url=e.url, title=e.title, sort_order=position)
        for position, e in enumerate(entries)
    ]


def create(db: Session, payload) -> Ingredient:
    check_parent(db, Ingredient, None, payload.parent_id, "ingredient")

    ingredient = Ingredient(
        name_cn=payload.name_cn,
        name_en=payload.name_en,
        name_alt=payload.name_alt,
        category_id=payload.category_id,
        parent_id=payload.parent_id,
        description=payload.description,
        selection_notes=payload.selection_notes,
        sourcing_notes=payload.sourcing_notes,
        preservation_notes=payload.preservation_notes,
        needs_detail=payload.needs_detail,
        rating=payload.rating,
    )
    _apply_aliases(ingredient, payload.aliases)
    _apply_preservation(ingredient, payload.preservation)
    _apply_heating(db, ingredient, payload.heating)
    _apply_links(ingredient, payload.links)
    db.add(ingredient)
    db.flush()
    _apply_labels(db, ingredient, payload.label_ids)
    db.commit()
    return get(db, ingredient.id)


def update(db: Session, ingredient_id: int, payload) -> Ingredient:
    from app import schemas  # deferred: avoids an import cycle

    ingredient = get(db, ingredient_id)
    changes = payload.model_dump(exclude_unset=True)

    if "parent_id" in changes:
        check_parent(db, Ingredient, ingredient.id, changes["parent_id"], "ingredient")

    aliases = changes.pop("aliases", None)
    preservation = changes.pop("preservation", None)
    heating = changes.pop("heating", None)
    links = changes.pop("links", None)
    label_ids = changes.pop("label_ids", None)

    for field, value in changes.items():
        setattr(ingredient, field, value)

    # The at-least-one-name rule cannot be checked on the payload alone: a
    # PATCH clearing name_cn is fine on a row that has an English name and not
    # on one that does not. Checked here against the MERGED row, which is the
    # only place the question has an answer. The CHECK constraint is still the
    # backstop, and answers 422 through the IntegrityError handler if this is
    # ever bypassed.
    if not any((ingredient.name_cn, ingredient.name_en, ingredient.name_alt)):
        raise AppError(422, "An ingredient needs at least one name.")

    if aliases is not None:
        _apply_aliases(ingredient, aliases)
    if preservation is not None:
        _apply_preservation(ingredient, _as_entries(preservation, schemas.PreservationIn))
    if heating is not None:
        _apply_heating(db, ingredient, _as_entries(heating, schemas.HeatingIn))
    if links is not None:
        _apply_links(ingredient, _as_entries(links, schemas.LinkIn))
    if label_ids is not None:
        _apply_labels(db, ingredient, label_ids)

    db.commit()
    return get(db, ingredient_id)


def _as_entries(raw, model):
    """`model_dump` turns the nested models into dicts; put them back.

    Only the top level is re-validated by the router, so the nested entries
    arrive here as plain dicts. Rebuilding them as simple objects keeps the
    `_apply_*` helpers reading one way rather than branching on which caller
    it came from.
    """
    return [model(**entry) if isinstance(entry, dict) else entry for entry in raw]


def child_count(db: Session, ingredient_id: int) -> int:
    return db.query(Ingredient).filter(Ingredient.parent_id == ingredient_id).count()


def cascade_counts(db: Session, ingredient_id: int) -> dict[str, int]:
    """What a delete would take with it, for the confirmation dialog.

    Only the CASCADE relationships are counted. Children are not in here
    because they are not cascaded - they block the delete entirely, which is a
    refusal rather than a number.
    """
    return {
        "aliases": db.query(IngredientAlias)
        .filter(IngredientAlias.ingredient_id == ingredient_id)
        .count(),
        "preservation": db.query(IngredientPreservation)
        .filter(IngredientPreservation.ingredient_id == ingredient_id)
        .count(),
        "heating": db.query(IngredientHeating)
        .filter(IngredientHeating.ingredient_id == ingredient_id)
        .count(),
        "links": db.query(IngredientLink)
        .filter(IngredientLink.ingredient_id == ingredient_id)
        .count(),
        "labels": db.query(IngredientLabel)
        .filter(IngredientLabel.ingredient_id == ingredient_id)
        .count(),
    }


def fridge_range(ingredient: Ingredient) -> dict | None:
    """The unused-and-refrigerated range, for the library's list view."""
    for row in ingredient.preservation:
        if row.state == "unused" and row.method == "冷藏":
            return {"min": row.duration_min_days, "max": row.duration_max_days}
    return None
