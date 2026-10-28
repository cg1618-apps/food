"""The universal search: one term, one bucket per kind of thing in the app.

Each bucket is ONE query - filtered, ranked and limited in SQL - plus the
fixed eager loads its rows read (a cover, a category, a dish), so the count
of round trips depends on the code and never on the rows.

What a bucket matches is its library's own rule, read from the service that
owns it (`dishes.matches`, `ingredients.matches`, `recipes.matches`,
`kitchen_notes.matches`), so the search box in the top bar can never find a
row that the library's search box would not, or miss one it would. The three
kinds with no server-side `q` of their own are defined here:

- authors - either name, the rule the author library applies in the browser
  (frontend/src/lib/authors.js `matchesAuthor`);
- 加熱 - the name, or failing that the body: "微波" finds every note that
  says to use the microwave;
- TBD - the name, or any link's label. Not the url: "https" would match the
  whole page. An entry with no name and no labelled link is therefore not
  findable here, and is still on /tbd.

Within a bucket the order is the tier a row first matches - exact, then
prefix, then contains, on any name or alias - and then the display name, so
"雞" puts 雞 above 雞湯 above 炒雞. Kinds that also match a body (notes,
加熱) rank a body-only match after every name match.
"""

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.constants import DISH_KINDS, KITCHEN_NOTE_KINDS
from app.models import (
    Author,
    AuthorImage,
    Dish,
    DishImage,
    HeatingNote,
    Ingredient,
    IngredientImage,
    KitchenNote,
    KitchenNoteImage,
    Recipe,
    RecipeImage,
    RecipeSource,
    TbdEntry,
    TbdLink,
)
from app.services import dishes, images, ingredients, kitchen_notes, recipes
from app.services.search import CONTAINS, EXACT, PREFIX, display_order, rank, term_match

DEFAULT_LIMIT = 10
MAX_LIMIT = 50

# Joins the parts of a secondary line.
SEPARATOR = " · "

TIERS = (EXACT, PREFIX)


@dataclass
class Hit:
    """One result row: what the page links to, its name, a secondary line,
    and a cover where the kind has a gallery."""

    id: int
    display_name: str
    detail: str | None = None
    cover: object | None = None


def _joined(*parts) -> str | None:
    kept = [part for part in parts if part]
    return SEPARATOR.join(kept) if kept else None


def _first_line(text: str | None) -> str | None:
    if not text:
        return None
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return None


def _ranked(db: Session, model, where, tiers, order, limit, options=()):
    """The one query a bucket is: rows matching `where`, best tier first,
    then by `order`, then by id so equal names keep a stable order."""
    return (
        db.query(model)
        .options(*options)
        .filter(where)
        .order_by(rank(tiers), *order, model.id)
        .limit(limit)
        .all()
    )


def _dishes(db: Session, q: str, limit: int) -> list[Hit]:
    rows = _ranked(
        db,
        Dish,
        dishes.matches(q),
        [dishes.matches(q, how) for how in TIERS],
        [display_order(Dish.name_cn, Dish.name_en, Dish.name_alt)],
        limit,
        # The cover falls back to a recipe's, so recipes' galleries load too.
        options=(
            selectinload(Dish.images).selectinload(DishImage.image),
            selectinload(Dish.recipes).selectinload(Recipe.images).selectinload(RecipeImage.image),
        ),
    )
    return [
        Hit(row.id, row.display_name, DISH_KINDS.get(row.kind, row.kind), dishes.cover(row))
        for row in rows
    ]


def _recipe_detail(row: Recipe) -> str | None:
    """Whose recipe it is when it has a name of its own, and its authors."""
    has_own_name = bool(row.name and row.name.strip())
    authors = "、".join(author.display_name for author in recipes.authors(row))
    return _joined(row.dish.display_name if has_own_name else None, authors)


def _recipes(db: Session, q: str, limit: int) -> list[Hit]:
    # A recipe's display name falls back to its dish's, which lives in another
    # table: a correlated subquery gives the dish's name to order by.
    dish_name = (
        select(display_order(Dish.name_cn, Dish.name_en, Dish.name_alt))
        .where(Dish.id == Recipe.dish_id)
        .scalar_subquery()
    )
    own_name = display_order(Recipe.name)
    rows = _ranked(
        db,
        Recipe,
        recipes.matches(q),
        [recipes.matches(q, how) for how in TIERS],
        [func.coalesce(own_name, dish_name)],
        limit,
        options=(
            selectinload(Recipe.dish),
            selectinload(Recipe.sources).selectinload(RecipeSource.author),
            selectinload(Recipe.images).selectinload(RecipeImage.image),
        ),
    )
    return [
        Hit(row.id, row.display_name, _recipe_detail(row), images.cover(row.images))
        for row in rows
    ]


def _ingredients(db: Session, q: str, limit: int) -> list[Hit]:
    rows = _ranked(
        db,
        Ingredient,
        ingredients.matches(q),
        [ingredients.matches(q, how) for how in TIERS],
        [display_order(Ingredient.name_cn, Ingredient.name_en, Ingredient.name_alt)],
        limit,
        options=(
            selectinload(Ingredient.category),
            selectinload(Ingredient.images).selectinload(IngredientImage.image),
        ),
    )
    return [
        Hit(
            row.id,
            row.display_name,
            _joined(row.category.display_name, "待補" if row.needs_detail else None),
            images.cover(row.images),
        )
        for row in rows
    ]


def _notes(db: Session, q: str, limit: int) -> list[Hit]:
    rows = _ranked(
        db,
        KitchenNote,
        kitchen_notes.matches(q),
        [term_match(KitchenNote.title, q, how) for how in (*TIERS, CONTAINS)],
        [display_order(KitchenNote.title)],
        limit,
        options=(selectinload(KitchenNote.images).selectinload(KitchenNoteImage.image),),
    )
    return [
        Hit(row.id, row.title, KITCHEN_NOTE_KINDS.get(row.kind, row.kind), images.cover(row.images))
        for row in rows
    ]


def _author_names(q: str, how: str = CONTAINS):
    return or_(term_match(Author.name_cn, q, how), term_match(Author.name_en, q, how))


def _authors(db: Session, q: str, limit: int) -> list[Hit]:
    rows = _ranked(
        db,
        Author,
        _author_names(q),
        [_author_names(q, how) for how in TIERS],
        [display_order(Author.name_cn, Author.name_en)],
        limit,
        options=(selectinload(Author.images).selectinload(AuthorImage.image),),
    )
    return [
        Hit(
            row.id,
            row.display_name,
            # The other name, as the author library's card subtitle shows it.
            row.name_en if row.name_cn and row.name_en else None,
            images.cover(row.images),
        )
        for row in rows
    ]


def _heating(db: Session, q: str, limit: int) -> list[Hit]:
    rows = _ranked(
        db,
        HeatingNote,
        or_(term_match(HeatingNote.name, q), term_match(HeatingNote.body, q)),
        [term_match(HeatingNote.name, q, how) for how in (*TIERS, CONTAINS)],
        [display_order(HeatingNote.name)],
        limit,
    )
    return [Hit(row.id, row.name, _first_line(row.body)) for row in rows]


def _tbd_names(q: str, how: str = CONTAINS):
    labelled = select(TbdLink.entry_id).where(term_match(TbdLink.label, q, how)).scalar_subquery()
    return or_(term_match(TbdEntry.name, q, how), TbdEntry.id.in_(labelled))


def _tbd_display_name(row: TbdEntry) -> str:
    """The name; else the first link's label; else the first link's url."""
    if row.name:
        return row.name
    for link in row.links:
        if link.label:
            return link.label
    return row.links[0].url if row.links else ""


def _tbd(db: Session, q: str, limit: int) -> list[Hit]:
    rows = _ranked(
        db,
        TbdEntry,
        _tbd_names(q),
        [_tbd_names(q, how) for how in TIERS],
        # Unnamed entries after the named ones, in the owner's order.
        [display_order(TbdEntry.name).nulls_last(), TbdEntry.sort_order],
        limit,
        options=(selectinload(TbdEntry.links),),
    )
    return [
        Hit(row.id, _tbd_display_name(row), f"{len(row.links)} 個連結" if row.links else None)
        for row in rows
    ]


# Bucket key -> the function that fills it, in the order the response and
# the dropdown list them.
BUCKETS = {
    "dishes": _dishes,
    "recipes": _recipes,
    "ingredients": _ingredients,
    "notes": _notes,
    "authors": _authors,
    "heating": _heating,
    "tbd": _tbd,
}


def search(db: Session, q: str, limit: int = DEFAULT_LIMIT) -> dict[str, list[Hit]]:
    """Every bucket for `q`. A blank term finds nothing rather than
    everything: an empty search box is not a request for the whole app."""
    if not q.strip():
        return {key: [] for key in BUCKETS}
    return {key: fill(db, q, limit) for key, fill in BUCKETS.items()}
