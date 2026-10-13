"""A name is a category or an ingredient, never both.

A category is a family whose members are bought but which is never bought or
cited itself (雞肉); an ingredient is bought or cited as itself (醬油), its
kinds hanging under it as varieties. "The same name" is an ingredient's
`name_cn` or `name_en` equal to a category's `name_cn` or `name_en`, trimmed
and ignoring case. Names only: an alias is something typed to find a row and
`name_alt` (the ingredient's alone - a category has none) is a catch-all that
two ingredients may share, so neither is a claim about what the thing is.

No constraint can hold this: it spans two tables, and PostgreSQL has no
cross-table unique index. So it is held here, on every write path that sets a
name:

- **Saving an ingredient** (create, or an update changing a name) whose name
  is a category's is refused with 409 and a `category_clash` preview of
  turning that category into this ingredient. The same save sent again with
  `convert_category` (the preview's category id and fingerprint, and a target
  when the category is top-level) does it, in the save's transaction.
- **Saving a category** (create, or a rename) whose name is an ingredient's is
  refused with 409. Turning an ingredient into a category would throw away its
  storage notes, pictures and recipe references, so there is no offer.
- **A recipe save making a stub** whose typed name is a category's is refused
  with 422 (`recipes._resolve_new_ingredients`): a dialog about the category
  tree in the middle of writing a recipe is the interruption stubs exist to
  avoid.

The fallback category is never converted, and a name matching two categories
is refused rather than guessed at.
"""

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import func, or_
from sqlalchemy import update as update_rows
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Ingredient, IngredientCategory
from app.services.hierarchy import ancestor_ids, is_descendant


def _keys(names) -> list[str]:
    return sorted({n.strip().lower() for n in names if n and n.strip()})


def _normalised(column):
    return func.lower(func.btrim(column))


def _ref(row) -> dict:
    return {"id": row.id, "display_name": row.display_name}


def categories_named(db: Session, names) -> list[IngredientCategory]:
    """Every category whose `name_cn` or `name_en` is one of `names`."""
    keys = _keys(names)
    if not keys:
        return []
    return (
        db.query(IngredientCategory)
        .filter(
            or_(
                _normalised(IngredientCategory.name_cn).in_(keys),
                _normalised(IngredientCategory.name_en).in_(keys),
            )
        )
        .order_by(IngredientCategory.id)
        .all()
    )


def ingredient_named(db: Session, names) -> Ingredient | None:
    """The ingredient whose `name_cn` or `name_en` is one of `names`, if any."""
    keys = _keys(names)
    if not keys:
        return None
    return (
        db.query(Ingredient)
        .filter(
            or_(
                _normalised(Ingredient.name_cn).in_(keys),
                _normalised(Ingredient.name_en).in_(keys),
            )
        )
        .order_by(Ingredient.id)
        .first()
    )


# --- saving a category -------------------------------------------------------


def refuse_ingredient_names(db: Session, names) -> None:
    """409 when a name a category is being given is an ingredient's.

    `names` are only the names this save sets: a category renamed in one slot
    is not refused for what the other slot already held.
    """
    ingredient = ingredient_named(db, names)
    if ingredient is None:
        return
    own = {n.strip().lower() for n in (ingredient.name_cn, ingredient.name_en) if n}
    name = next(n.strip() for n in names if n and n.strip().lower() in own)
    raise AppError(
        409, f"「{name}」已是食材，分類不能同名。", ingredient=_ref(ingredient)
    )


# --- saving an ingredient ----------------------------------------------------


@dataclass
class ConversionPlan:
    """Everything turning `category` into the ingredient being saved does.

    The 409's preview reports it and the conversion executes it, and neither
    recomputes anything, so the two cannot disagree - the merge's shape.
    """

    category: IngredientCategory
    # The ingredient's own category is `category`, which is about to go.
    takes_target: bool
    adopted: list[Ingredient]
    varieties: list[Ingredient]
    kept_top_level: list[Ingredient]
    child_categories: list[IngredientCategory]
    # (child that would move up, the category already there with its name)
    blocked_by: list[tuple[IngredientCategory, IngredientCategory]]
    description: str | None

    @property
    def choose_target(self) -> bool:
        """A top-level category has no parent to hand its ingredients to."""
        return self.category.parent_id is None

    def fingerprint(self) -> str:
        """A hash of every row the conversion would change, and how.

        The target the owner picks for a top-level category is not in it: it
        is chosen after the preview, and validated on its own.
        """
        category = self.category
        canonical = {
            "category": [
                category.id,
                category.name_cn,
                category.name_en,
                category.parent_id,
                category.description,
            ],
            "takes_target": self.takes_target,
            "adopted": [row.id for row in self.adopted],
            "varieties": [[row.id, row.parent_id] for row in self.varieties],
            "kept_top_level": [row.id for row in self.kept_top_level],
            "children": [[row.id, row.name_cn] for row in self.child_categories],
            "blocked_by": [[a.id, b.id] for a, b in self.blocked_by],
            "description": self.description,
        }
        text_form = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(text_form.encode("utf-8")).hexdigest()


def plan(
    db: Session,
    *,
    ingredient_id: int | None,
    names,
    category_id: int,
    parent_id: int | None,
    description: str | None,
) -> ConversionPlan | None:
    """The conversion an ingredient save with these values would need, or
    None when no category has its name.

    `ingredient_id` is None for a new ingredient. The other values are the
    row as it will be saved - the form's category, parent and description.

    Refused here, as no conversion can resolve them: the fallback category
    (422 - every stub is filed there), and a name two categories answer to
    (409 - which one is meant is the owner's to say, by renaming the other).
    """
    clashes = categories_named(db, names)
    if not clashes:
        return None
    fallback = next((row for row in clashes if row.is_fallback), None)
    if fallback is not None:
        raise AppError(
            422,
            f"「{fallback.display_name}」是預設分類，不能轉成食材：請幫食材換個名字。",
            category=_ref(fallback),
        )
    if len(clashes) > 1:
        listed = "、".join(f"「{row.display_name}」" for row in clashes)
        raise AppError(
            409,
            f"這個名字同時是 {listed} 這幾個分類的名字，不知道要轉哪一個：請先把其中一個分類改名。",
            categories=[_ref(row) for row in clashes],
        )

    category = clashes[0]
    # The saved ingredient's ancestors under the parent it is being saved
    # with: a top-level member among them cannot become its variety.
    above = ancestor_ids(db, Ingredient, parent_id)
    members = (
        db.query(Ingredient)
        .filter(Ingredient.category_id == category.id, Ingredient.id != (ingredient_id or 0))
        .order_by(Ingredient.id)
        .all()
    )
    children = (
        db.query(IngredientCategory)
        .filter(IngredientCategory.parent_id == category.id)
        .order_by(IngredientCategory.id)
        .all()
    )
    return ConversionPlan(
        category=category,
        takes_target=category_id == category.id,
        adopted=[m for m in members if m.parent_id is None and m.id not in above],
        varieties=[m for m in members if m.parent_id is not None],
        kept_top_level=[m for m in members if m.parent_id is None and m.id in above],
        child_categories=children,
        blocked_by=_sibling_clashes(db, category, children),
        description=_description_outcome(category.description, description),
    )


def _description_outcome(notes: str | None, own: str | None) -> str | None:
    """The category's notes become the ingredient's description only when it
    has none of its own; otherwise they are dropped."""
    if not notes:
        return None
    return "dropped" if own else "moved"


def _sibling_clashes(db: Session, category: IngredientCategory, children) -> list:
    """Children that cannot move up because their Chinese name is taken there.

    The same test as `uq_ingredient_category_sibling_cn` - the parent with
    NULL as 0, `lower(name_cn)` - so a pair this finds is exactly a pair the
    index would refuse. `category` itself is not a clash: it is deleted.
    """
    pairs = []
    for child in children:
        if child.name_cn is None:
            continue
        sibling = (
            db.query(IngredientCategory)
            .filter(
                func.coalesce(IngredientCategory.parent_id, 0) == (category.parent_id or 0),
                func.lower(IngredientCategory.name_cn) == func.lower(child.name_cn),
                IngredientCategory.id != category.id,
            )
            .first()
        )
        if sibling is not None:
            pairs.append((child, sibling))
    return pairs


def preview(conversion: ConversionPlan) -> dict:
    """The `category_clash` body: the plan in the wire's shape."""
    from app import schemas  # deferred: the schemas import the services' models

    category = conversion.category
    parent = category.parent

    def refs(rows):
        return [_ref(row) for row in rows]

    return schemas.CategoryClashPreview(
        category=_ref(category),
        target=_ref(parent) if parent else None,
        choose_target=conversion.choose_target,
        takes_target=conversion.takes_target,
        adopted=refs(conversion.adopted),
        varieties=refs(conversion.varieties),
        kept_top_level=refs(conversion.kept_top_level),
        child_categories=refs(conversion.child_categories),
        child_parent=_ref(parent) if parent else None,
        blocked_by=[
            {"category": _ref(child), "sibling": _ref(sibling)}
            for child, sibling in conversion.blocked_by
        ],
        description=conversion.description,
        fingerprint=conversion.fingerprint(),
    ).model_dump(mode="json")


def settle(db: Session, conversion: ConversionPlan | None, request) -> int | None:
    """Whether the save may go ahead, and where the category's ingredients go.

    None when there is nothing to convert - a `convert_category` sent with a
    name that no longer clashes is moot, and the save simply runs. Otherwise
    the save must carry a conversion of this very category: without one it
    is refused with 409 and the preview. A conversion that cannot run is 422,
    checked before the fingerprint, as a merge's refusals are; one whose
    fingerprint is not the plan's is 409 with the fresh preview.
    """
    if conversion is None:
        return None
    category = conversion.category
    if request is None or request.category_id != category.id:
        raise AppError(
            409,
            f"「{category.display_name}」是分類，食材不能同名。可以把這個分類轉成這個食材。",
            category_clash=preview(conversion),
        )

    if conversion.blocked_by:
        pairs = "、".join(
            f"「{child.display_name}」" for child, _ in conversion.blocked_by
        )
        raise AppError(
            422,
            f"子分類 {pairs} 移上去會和同一層的分類同名：請先改名，再轉換。",
            category_clash=preview(conversion),
        )
    target_id = _target(db, category, request.target_category_id)

    if request.fingerprint != conversion.fingerprint():
        raise AppError(
            409,
            "預覽之後這個分類或它底下的東西改過了，請看過再確認一次。",
            category_clash=preview(conversion),
        )
    return target_id


def _target(db: Session, category: IngredientCategory, chosen: int | None) -> int:
    """The category the clashing one's ingredients are re-filed into.

    Its parent, when it has one - then a different choice is refused rather
    than ignored. A top-level category has none, so the request names one,
    which may be neither the category itself nor anything below it: both go
    with it, or under it, in the conversion.
    """
    if category.parent_id is not None:
        if chosen is not None and chosen != category.parent_id:
            raise AppError(
                422,
                f"「{category.display_name}」的食材會移到它的上層分類，不能另外指定。",
            )
        return category.parent_id
    if chosen is None:
        raise AppError(
            422, f"「{category.display_name}」是最上層的分類：請選一個分類放它的食材。"
        )
    target = db.get(IngredientCategory, chosen)
    if target is None:
        raise AppError(422, f"No such category: {chosen}.")
    if target.id == category.id or is_descendant(db, IngredientCategory, target.id, category.id):
        raise AppError(
            422,
            f"食材不能移到「{category.display_name}」自己或它底下的分類：它們會跟著轉換一起變動。",
        )
    return target.id


def convert(
    db: Session, conversion: ConversionPlan, ingredient: Ingredient, target_id: int
) -> None:
    """Execute a settled plan. The ingredient is flushed (it has an id) and
    filed where it belongs; the caller commits, so the save and the
    conversion are one transaction and a failure leaves nothing changed.

    Rows move by UPDATE, and the category is deleted last, once nothing
    points at it - both of its relationships are RESTRICT.
    """
    category = conversion.category
    if any(
        child.name_cn and category.name_cn and child.name_cn.lower() == category.name_cn.lower()
        for child in conversion.child_categories
    ):
        # A child sharing the category's own Chinese name moves up beside
        # it before it is gone, and the sibling index would refuse the pair
        # for that moment. Only possible when the ingredient matched the
        # English name, so the category keeps one and the CHECK is met.
        db.execute(
            update_rows(IngredientCategory)
            .where(IngredientCategory.id == category.id)
            .values(name_cn=None)
        )

    db.execute(
        update_rows(Ingredient)
        .where(Ingredient.category_id == category.id)
        .values(category_id=target_id)
    )
    db.execute(
        update_rows(Ingredient)
        .where(Ingredient.id.in_([row.id for row in conversion.adopted]))
        .values(parent_id=ingredient.id)
    )
    db.execute(
        update_rows(IngredientCategory)
        .where(IngredientCategory.parent_id == category.id)
        .values(parent_id=category.parent_id)
    )
    if conversion.description == "moved":
        ingredient.description = category.description
    db.flush()
    db.delete(category)
    db.flush()
