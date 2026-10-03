"""Reading and writing recipes. The router does HTTP; this does the work.

Every write validates everything it can BEFORE it changes anything: the dish,
the status, every source's platform and author, every id in the vocabulary
lists, every group's value or name, every line target, the own-dish rule and
the cycle guard. Only then are new dishes, stubs and new authors created and
the row touched.

Lines and steps are each a pair on the wire - the ungrouped rows, and the
groups with theirs - and are stored as one recipe-wide list of rows, each
naming its group or none, positioned in the order the page shows them:
ungrouped first, then group by group.
One request is one transaction, and the ordering is what makes a refused save
leave nothing behind even in a session that is never rolled back - the test
session is one such, and an autoflush is all it takes to half-write a row.

A line names a DISH, not a recipe of it, so the nesting graph is a graph of
dishes: dish A uses dish B when a recipe of A has a line naming B. There are
no reverse relationships from an ingredient or a dish to the lines that name
them, so "used in" is always an explicit query.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.errors import AppError
from app.models import (
    Author,
    CookingMethod,
    Dish,
    DishLabel,
    Equipment,
    Ingredient,
    IngredientAlias,
    IngredientCategory,
    LineGroup,
    Recipe,
    RecipeEquipment,
    RecipeImage,
    RecipeLine,
    RecipeLineGroup,
    RecipeMethod,
    RecipeSource,
    RecipeStatus,
    RecipeStep,
    RecipeStepGroup,
    SourcePlatform,
    StepGroup,
)
from app.schemas.recipe import LIST_FIELDS
from app.services import dishes
from app.services.hierarchy import MAX_DEPTH
from app.services.lookup import fetch_all
from app.services.search import ESCAPE, contains

# The id lists a recipe carries, the relationship each fills, the model it
# names, and the word a 422 uses for it.
_LINKED = {
    "method_ids": ("methods", CookingMethod, "cooking method"),
    "equipment_ids": ("equipment", Equipment, "equipment"),
}


def _loaded(query):
    """Every relationship the response needs, in one round trip each."""
    dish = selectinload(Recipe.dish)
    return query.options(
        dish.selectinload(Dish.course),
        dish.selectinload(Dish.region),
        dish.selectinload(Dish.labels),
        dish.selectinload(Dish.serves_as),
        dish.selectinload(Dish.recipes),
        selectinload(Recipe.status),
        selectinload(Recipe.sources).selectinload(RecipeSource.platform),
        selectinload(Recipe.sources).selectinload(RecipeSource.author),
        selectinload(Recipe.lines).selectinload(RecipeLine.ingredient),
        selectinload(Recipe.lines).selectinload(RecipeLine.sub_dish),
        selectinload(Recipe.steps),
        selectinload(Recipe.line_groups).selectinload(RecipeLineGroup.group),
        selectinload(Recipe.step_groups).selectinload(RecipeStepGroup.group),
        selectinload(Recipe.images).selectinload(RecipeImage.image),
        selectinload(Recipe.methods),
        selectinload(Recipe.equipment),
    )


def _summary_loaded(query):
    """Every relationship a library row reads, in one round trip each.

    Lines and steps are loaded for `written_up`; a list of a few hundred rows
    rendering any of these lazily would issue a query per row.
    """
    return query.options(
        selectinload(Recipe.dish).selectinload(Dish.course),
        selectinload(Recipe.status),
        selectinload(Recipe.methods),
        selectinload(Recipe.sources).selectinload(RecipeSource.author),
        selectinload(Recipe.images).selectinload(RecipeImage.image),
        selectinload(Recipe.lines),
        selectinload(Recipe.steps),
    )


def get(db: Session, recipe_id: int) -> Recipe:
    row = _loaded(db.query(Recipe)).filter(Recipe.id == recipe_id).one_or_none()
    if row is None:
        raise AppError(404, "No such recipe.")
    return row


def written_up(recipe: Recipe) -> bool:
    """At least one line or step. Derived, never stored."""
    return bool(recipe.lines or recipe.steps)


def _by_name(rows) -> list[Recipe]:
    return sorted(rows, key=lambda r: (r.display_name.casefold(), r.id))


def other_recipes(recipe: Recipe) -> list[Recipe]:
    """其他版本: the other recipes of this recipe's dish, by display name."""
    return _by_name(r for r in recipe.dish.recipes if r.id != recipe.id)


def authors(recipe: Recipe) -> list[Author]:
    """The distinct authors of a recipe's sources, in source order."""
    by_id = {s.author.id: s.author for s in recipe.sources if s.author is not None}
    return list(by_id.values())


def _below(ingredient_ids: list[int]):
    """A recursive CTE of `(root_id, ingredient_id)`: each of `ingredient_ids`
    paired with itself and with every ingredient below it, at any depth.

    UNION rather than UNION ALL, so that a cycle in `parent_id` - which the
    write path refuses, but a hand-written UPDATE could make - ends the walk
    instead of hanging it: a pair seen once is never produced again.
    """
    tree = select(
        Ingredient.id.label("root_id"), Ingredient.id.label("ingredient_id")
    ).where(Ingredient.id.in_(ingredient_ids)).cte("ingredient_below", recursive=True)
    child = aliased(Ingredient)
    return tree.union(
        select(tree.c.root_id, child.id).where(child.parent_id == tree.c.ingredient_id)
    )


def _usage(ingredient_ids: list[int]):
    """`(root_id, recipe_id)` for every line naming a root or anything below it.

    THE definition of "uses" for an ingredient. The recipe list's
    `ingredient_id` filter, an ingredient's `used_in` and its `used_in_count`
    all read this and nothing else, so the three cannot disagree. Depth through
    sub-dishes is zero: a line naming a sauce is not a line naming what that
    sauce's recipes use.
    """
    tree = _below(ingredient_ids)
    return (
        select(tree.c.root_id, RecipeLine.recipe_id)
        .join(RecipeLine, RecipeLine.ingredient_id == tree.c.ingredient_id)
        .subquery()
    )


def recipe_ids_using_ingredients(ingredient_ids: list[int]):
    """A subquery of the recipes using any of `ingredient_ids`, as `_usage`
    defines using."""
    return select(_usage(ingredient_ids).c.recipe_id).scalar_subquery()


def recipes_using_ingredient(db: Session, ingredient_ids: list[int]) -> list[Recipe]:
    """Distinct recipes using any of `ingredient_ids` or anything below them."""
    rows = (
        db.query(Recipe)
        .options(selectinload(Recipe.dish))
        .filter(Recipe.id.in_(recipe_ids_using_ingredients(ingredient_ids)))
    )
    return _by_name(rows)


def used_in_counts(db: Session, ingredient_ids: list[int]) -> dict[int, int]:
    """Ingredient id -> how many distinct recipes use it. One query, however
    many ids; an id no recipe uses is absent rather than zero."""
    if not ingredient_ids:
        return {}
    usage = _usage(ingredient_ids)
    rows = db.execute(
        select(usage.c.root_id, func.count(usage.c.recipe_id.distinct())).group_by(
            usage.c.root_id
        )
    )
    return dict(rows.all())


def recipes_naming_ingredient(db: Session, ingredient_id: int) -> list[Recipe]:
    """Distinct recipes with a line naming this ingredient ITSELF.

    Not "used in": this is what the foreign key refuses a delete over, and a
    recipe naming only a child does not block deleting the parent - the child
    does that on its own.
    """
    rows = (
        db.query(Recipe)
        .options(selectinload(Recipe.dish))
        .filter(
            Recipe.id.in_(
                select(RecipeLine.recipe_id)
                .where(RecipeLine.ingredient_id == ingredient_id)
                .scalar_subquery()
            )
        )
    )
    return _by_name(rows)


def _any_of(link, column, values):
    """Recipes with a `link` row whose `column` is any of `values`."""
    return Recipe.id.in_(select(link.recipe_id).where(column.in_(values)).scalar_subquery())


def _dishes_where(*clauses):
    """Recipes whose dish matches every clause - the filters that moved to
    the dish read through it."""
    return Recipe.dish_id.in_(select(Dish.id).where(*clauses).scalar_subquery())


def search(
    db: Session,
    q: str | None = None,
    dish_id: list[int] | None = None,
    kind: list[str] | None = None,
    course_id: list[int] | None = None,
    region_id: list[int] | None = None,
    label_id: list[int] | None = None,
    status_id: list[int] | None = None,
    method_id: list[int] | None = None,
    equipment_id: list[int] | None = None,
    author_id: list[int] | None = None,
    ingredient_id: list[int] | None = None,
    written_up: bool | None = None,
) -> list[Recipe]:
    """The library list. Each multi-valued filter means "any of" its values;
    different filters narrow each other. Kind, course, region and label are
    the dish's, so they filter through it, and a search term matches the
    recipe's own name or any of its dish's names and aliases.

    Every filter that reaches through another table is a subquery rather than
    a join, for the reason `ingredients.search` gives: a join returns the
    recipe once per matching row, which only shows on data with several.
    """
    query = _summary_loaded(db.query(Recipe))

    if q:
        query = query.filter(
            or_(Recipe.name.ilike(contains(q), escape=ESCAPE), _dishes_where(dishes.matches(q)))
        )
    if dish_id:
        query = query.filter(Recipe.dish_id.in_(dish_id))
    if kind:
        query = query.filter(_dishes_where(Dish.kind.in_(kind)))
    if course_id:
        query = query.filter(_dishes_where(Dish.course_id.in_(course_id)))
    if region_id:
        query = query.filter(_dishes_where(Dish.region_id.in_(region_id)))
    if label_id:
        query = query.filter(
            Recipe.dish_id.in_(
                select(DishLabel.dish_id).where(DishLabel.label_id.in_(label_id)).scalar_subquery()
            )
        )
    if status_id:
        query = query.filter(Recipe.status_id.in_(status_id))
    if method_id:
        query = query.filter(_any_of(RecipeMethod, RecipeMethod.method_id, method_id))
    if equipment_id:
        query = query.filter(_any_of(RecipeEquipment, RecipeEquipment.equipment_id, equipment_id))
    if author_id:
        query = query.filter(_any_of(RecipeSource, RecipeSource.author_id, author_id))
    if ingredient_id:
        query = query.filter(Recipe.id.in_(recipe_ids_using_ingredients(ingredient_id)))
    if written_up is not None:
        has_content = or_(
            Recipe.id.in_(select(RecipeLine.recipe_id).scalar_subquery()),
            Recipe.id.in_(select(RecipeStep.recipe_id).scalar_subquery()),
        )
        query = query.filter(has_content if written_up else ~has_content)

    return _by_name(query.all())


# --- validation: everything here runs before anything is written -------------


def _check_status(db: Session, status_id: int) -> None:
    fetch_all(db, RecipeStatus, [status_id], "status")


def _first_status(db: Session) -> int:
    """The status a recipe saved without one is given: the first in sort
    order, the oldest among equals - the order 設定 lists them in."""
    first = db.query(RecipeStatus.id).order_by(RecipeStatus.sort_order, RecipeStatus.id).first()
    if first is None:
        raise AppError(
            422, "There is no recipe status (狀態) to give this recipe; add one in 設定 first."
        )
    return first[0]


def _check_sources(db: Session, entries) -> None:
    """Every platform and every `author_id` a source names exists."""
    fetch_all(db, SourcePlatform, [e.platform_id for e in entries], "source platform")
    author_ids = [e.author_id for e in entries if e.author_id is not None]
    fetch_all(db, Author, author_ids, "author")


def _reachable_from(db: Session, start_ids: set[int], skip_recipe: int | None) -> set[int]:
    """Every dish reachable from `start_ids` through the lines of their
    recipes, `start_ids` included. Breadth first, one query per level.

    `skip_recipe`'s own lines are left out: they are about to be replaced, and
    a path through them is not one the saved recipe will have.

    The seen-set alone makes this terminate; MAX_DEPTH is the backstop the
    category walk has too, and here it refuses rather than stopping short,
    because a walk that gave up early would let a cycle through.
    """
    seen = set(start_ids)
    frontier = set(start_ids)
    depth = 0
    while frontier:
        depth += 1
        if depth > MAX_DEPTH:
            raise AppError(422, "Dishes nest deeper than this app allows.")
        query = (
            select(RecipeLine.sub_dish_id)
            .join(Recipe, Recipe.id == RecipeLine.recipe_id)
            .where(Recipe.dish_id.in_(frontier), RecipeLine.sub_dish_id.isnot(None))
        )
        if skip_recipe is not None:
            query = query.where(Recipe.id != skip_recipe)
        frontier = {sub_id for (sub_id,) in db.execute(query)} - seen
        seen |= frontier
    return seen


# Per pair: the groups field, the vocabulary its groups name, the id field
# naming it, the rows field inside a group, and the word a 422 uses.
_PAIRS = {
    "lines": ("line_groups", LineGroup, "line_group_id", "lines", "line group (材料分組)"),
    "steps": ("step_groups", StepGroup, "step_group_id", "steps", "step group (步驟分組)"),
}


def _flat(lists: dict, rows_field: str) -> list:
    """Every row of a pair in the order it is stored: the ungrouped rows,
    then each group's. Indexes into this are what stub resolution keys by."""
    groups_field, _, _, inner, _ = _PAIRS[rows_field]
    rows = list(lists.get(rows_field) or [])
    for group in lists.get(groups_field) or []:
        rows.extend(getattr(group, inner))
    return rows


def resolve_groups(db: Session, rows_field: str, entries) -> list[tuple[int | None, str | None]]:
    """`(value id, one-off name)` per group, exactly one of the two set.

    Read-only, so it runs with the checks. Every id sent must exist; a name
    matching a value's name_cn or name_en, trimmed and case-insensitively,
    becomes that value. After that a recipe may not hold one group twice -
    the same value, or the same one-off name in any case - which the uniques
    on the group tables would refuse anyway, but only as "something clashed".

    Public because a recipe template's groups follow the same rules
    (app/services/recipe_templates.py).
    """
    _, model, id_field, _, what = _PAIRS[rows_field]
    ids = [getattr(e, id_field) for e in entries if getattr(e, id_field) is not None]
    fetch_all(db, model, ids, what)
    lowered = [e.name.lower() for e in entries if e.name is not None]
    by_name: dict[str, int] = {}
    if lowered:
        values = (
            db.query(model)
            .filter(or_(func.lower(model.name_cn).in_(lowered), func.lower(model.name_en).in_(lowered)))
            .order_by(model.id)
        )
        for value in values:
            for name in (value.name_cn, value.name_en):
                if name:
                    by_name.setdefault(name.lower(), value.id)

    resolved = []
    seen: set = set()
    for entry in entries:
        value_id, name = getattr(entry, id_field), entry.name
        if value_id is None and name.lower() in by_name:
            value_id, name = by_name[name.lower()], None
        key = ("value", value_id) if value_id is not None else ("name", name.lower())
        if key in seen:
            raise AppError(422, f"A recipe cannot hold the same {what} twice; merge them into one.")
        seen.add(key)
        resolved.append((value_id, name))
    return resolved


def _check_groups(db: Session, lists: dict) -> dict[str, list]:
    """Rows field -> its resolved groups, for every pair that was sent."""
    return {
        rows_field: resolve_groups(db, rows_field, lists[groups_field])
        for rows_field, (groups_field, *_rest) in _PAIRS.items()
        if lists.get(groups_field) is not None
    }


def _names(new) -> set[str]:
    return {n.lower() for n in (new.name_cn, new.name_en) if n}


def _check_dish(db: Session, dish_id: int | None, new_dish) -> int | None:
    """The id of the dish the recipe will belong to, if it exists already:
    `dish_id` checked, or the dish `new_dish` will reuse. None is a dish the
    save will create. Read-only."""
    if dish_id is not None:
        fetch_all(db, Dish, [dish_id], "dish")
        return dish_id
    existing = dishes.by_name(db, list(_names(new_dish)))
    return existing.id if existing else None


def _check_line_targets(
    db: Session, recipe_id: int | None, dish_id: int | None, new_dish, entries
) -> None:
    """Every id a line names exists, no line names the recipe's own dish, and
    no sub-dish makes a cycle.

    `dish_id` is the recipe's dish if it exists - None when the save creates
    it, and then nothing can reach it yet. A line's `new_dish` is checked as
    the dish it will turn out to be: an existing one by name, or - when it is
    the same new name as the recipe's own new dish - the recipe's own dish.
    """
    ingredient_ids = [e.ingredient_id for e in entries if e.ingredient_id is not None]
    fetch_all(db, Ingredient, ingredient_ids, "ingredient")
    sub_ids = [e.sub_dish_id for e in entries if e.sub_dish_id is not None]
    fetch_all(db, Dish, sub_ids, "dish")
    own = "A recipe cannot use its own dish as an ingredient."
    for entry in entries:
        if entry.new_dish is None:
            continue
        existing = dishes.by_name(db, list(_names(entry.new_dish)))
        if existing is not None:
            sub_ids.append(existing.id)
        elif dish_id is None and new_dish is not None and _names(entry.new_dish) & _names(new_dish):
            raise AppError(422, own)
    if dish_id is None or not sub_ids:
        return
    if dish_id in sub_ids:
        raise AppError(422, own)
    if dish_id in _reachable_from(db, set(sub_ids), recipe_id):
        raise AppError(422, "That would make a loop: this dish is already used inside that one.")


class _KeptLine:
    """A stored line in the shape `_check_line_targets` reads, for a dish
    move that keeps the lines."""

    new_dish = None

    def __init__(self, line):
        self.ingredient_id = line.ingredient_id
        self.sub_dish_id = line.sub_dish_id


# --- resolution: may write (stubs), so runs only after validation -------------


def _find_by_name(db: Session, names: list[str]) -> Ingredient | None:
    """An ingredient answering to any of `names`, in a name slot or an alias.

    Case-insensitive and exact. A near match is the typeahead's job, before
    the user chooses "new"; here, only an exact one is reused.
    """
    lowered = [n.lower() for n in names]
    alias_match = (
        select(IngredientAlias.ingredient_id)
        .where(func.lower(IngredientAlias.value).in_(lowered))
        .scalar_subquery()
    )
    return (
        db.query(Ingredient)
        .filter(
            or_(
                func.lower(Ingredient.name_cn).in_(lowered),
                func.lower(Ingredient.name_en).in_(lowered),
                func.lower(Ingredient.name_alt).in_(lowered),
                Ingredient.id.in_(alias_match),
            )
        )
        .order_by(Ingredient.id)
        .first()
    )


def _resolve_new_ingredients(db: Session, entries) -> dict[int, int]:
    """Line index -> ingredient id, for every `new_ingredient` line.

    Each typed name reuses an existing ingredient that answers to it exactly,
    or becomes a stub in the fallback category with `needs_detail` set. Names
    resolved earlier in the same save are remembered, so the same new name in
    two lines is one stub rather than a unique violation on the second.
    """
    resolved: dict[int, int] = {}
    seen: dict[str, Ingredient] = {}
    fallback = None
    for index, entry in enumerate(entries):
        new = entry.new_ingredient
        if new is None:
            continue
        names = [n for n in (new.name_cn, new.name_en) if n]
        row = next((seen[n.lower()] for n in names if n.lower() in seen), None)
        if row is None:
            row = _find_by_name(db, names)
        if row is None:
            if fallback is None:
                fallback = db.query(IngredientCategory).filter_by(is_fallback=True).first()
                if fallback is None:
                    raise AppError(409, "There is no fallback category to file a new ingredient in.")
            row = Ingredient(
                name_cn=new.name_cn,
                name_en=new.name_en,
                category_id=fallback.id,
                needs_detail=True,
            )
            db.add(row)
            db.flush()
        for name in names:
            seen.setdefault(name.lower(), row)
        resolved[index] = row.id
    return resolved


def _resolve_new_dishes(db: Session, recipe_new, entries) -> tuple[int | None, dict[int, int]]:
    """The recipe's own new dish, and line index -> dish id for every
    `new_dish` line.

    Each typed name reuses the dish answering to it exactly, or is created
    with the kind it was sent with. Names resolved earlier in the same save
    are remembered - the recipe's own first - so one new name typed twice is
    one dish.
    """
    seen: dict[str, Dish] = {}

    def resolve(new) -> int:
        names = [n for n in (new.name_cn, new.name_en) if n]
        row = next((seen[n.lower()] for n in names if n.lower() in seen), None)
        if row is None:
            row = dishes.by_name(db, names)
        if row is None:
            row = Dish(name_cn=new.name_cn, name_en=new.name_en, kind=new.kind)
            db.add(row)
            db.flush()
        for name in names:
            seen.setdefault(name.lower(), row)
        return row.id

    own = resolve(recipe_new) if recipe_new is not None else None
    lines = {i: resolve(e.new_dish) for i, e in enumerate(entries) if e.new_dish is not None}
    return own, lines


def _resolve_new_authors(db: Session, entries) -> dict[int, int]:
    """Source index -> author id, for every `new_author` source.

    A typed name reuses the author answering to it in either slot, exactly
    and case-insensitively; otherwise it is created, with sort_order 0 like
    every author. Names resolved earlier in the same save are remembered, so
    one new name on two sources is one author rather than a unique violation
    on the second.
    """
    resolved: dict[int, int] = {}
    seen: dict[str, Author] = {}
    for index, entry in enumerate(entries):
        new = entry.new_author
        if new is None:
            continue
        lowered = [n.lower() for n in (new.name_cn, new.name_en) if n]
        row = next((seen[n] for n in lowered if n in seen), None)
        if row is None:
            row = (
                db.query(Author)
                .filter(
                    or_(
                        func.lower(Author.name_cn).in_(lowered),
                        func.lower(Author.name_en).in_(lowered),
                    )
                )
                .order_by(Author.id)
                .first()
            )
        if row is None:
            row = Author(name_cn=new.name_cn, name_en=new.name_en)
            db.add(row)
            db.flush()
        for name in lowered:
            seen.setdefault(name, row)
        resolved[index] = row.id
    return resolved


# --- applying ----------------------------------------------------------------


def _apply_sources(recipe: Recipe, entries, author_ids: dict[int, int]) -> None:
    """Replace the sources; a `new_author` source takes its resolved id."""
    recipe.sources = [
        RecipeSource(
            platform_id=e.platform_id,
            author_id=author_ids.get(i, e.author_id),
            url=e.url,
            title=e.title,
            sort_order=i,
        )
        for i, e in enumerate(entries)
    ]


def _apply_pair(db: Session, recipe: Recipe, lists: dict, rows_field: str, resolved, make_row):
    """Replace one pair - the rows and their groups - together.

    Rows are positioned through the whole recipe in display order: the
    ungrouped ones, then each group's. `make_row(index, entry, group)` builds
    one, `index` being its place in `_flat`.

    Each table is cleared and flushed BEFORE the new rows are assigned, rows
    before groups: the unit of work INSERTs before it DELETEs, so re-sending
    the same lines collides with uq_recipe_line_position on position 0
    otherwise, and a group's position likewise.
    """
    groups_field, _, id_field, inner, _ = _PAIRS[rows_field]
    group_model = RecipeLineGroup if rows_field == "lines" else RecipeStepGroup
    setattr(recipe, rows_field, [])
    db.flush()
    setattr(recipe, groups_field, [])
    db.flush()

    rows = [make_row(i, e, None) for i, e in enumerate(lists[rows_field])]
    groups = []
    for position, (entry, (value_id, name)) in enumerate(zip(lists[groups_field], resolved, strict=True)):
        group = group_model(position=position, name=name, **{id_field: value_id})
        groups.append(group)
        rows.extend(make_row(len(rows), e, group) for e in getattr(entry, inner))
    setattr(recipe, groups_field, groups)
    setattr(recipe, rows_field, rows)


def _apply_lines(db: Session, recipe: Recipe, lists: dict, resolved, new_ids: dict) -> None:
    """Replace the lines and their groups; a `new_ingredient` or `new_dish`
    line takes its resolved id."""
    ingredients, sub_dishes = new_ids["lines"], new_ids["line_dishes"]

    def line(index, e, group):
        return RecipeLine(
            position=index,
            group=group,
            ingredient_id=ingredients.get(index, e.ingredient_id),
            sub_dish_id=sub_dishes.get(index, e.sub_dish_id),
            amount=e.amount,
            note=e.note,
            is_optional=e.is_optional,
        )

    _apply_pair(db, recipe, lists, "lines", resolved, line)


def _apply_steps(db: Session, recipe: Recipe, lists: dict, resolved) -> None:
    """Replace the steps and their groups."""

    def step(index, e, group):
        return RecipeStep(position=index, group=group, kind=e.kind, body=e.body)

    _apply_pair(db, recipe, lists, "steps", resolved, step)


def _check_and_fetch(db: Session, lists: dict) -> dict:
    """Validate every sent list but the lines, which need the dish; return
    the vocabulary rows to assign."""
    fetched = {}
    for field, (_, model, what) in _LINKED.items():
        if lists.get(field) is not None:
            fetched[field] = fetch_all(db, model, lists[field], what)
    if lists.get("sources") is not None:
        _check_sources(db, lists["sources"])
    return fetched


def _resolve_new(db: Session, lists: dict, new_dish) -> dict:
    """The first write of a save: new dishes, stubs for new ingredients, rows
    for new authors. Runs only after every check has passed."""
    lines = _flat(lists, "lines")
    dish_id, line_dishes = _resolve_new_dishes(db, new_dish, lines)
    return {
        "dish": dish_id,
        "line_dishes": line_dishes,
        "lines": _resolve_new_ingredients(db, lines),
        "sources": _resolve_new_authors(db, lists.get("sources") or []),
    }


def _apply_lists(
    db: Session,
    recipe: Recipe,
    lists: dict,
    fetched: dict,
    groups: dict[str, list],
    new_ids: dict,
) -> None:
    """Every sent list. A pair is applied when it was sent - the schema has
    already refused one half without the other."""
    if lists.get("sources") is not None:
        _apply_sources(recipe, lists["sources"], new_ids["sources"])
    if "lines" in groups:
        _apply_lines(db, recipe, lists, groups["lines"], new_ids)
    if "steps" in groups:
        _apply_steps(db, recipe, lists, groups["steps"])
    for field, rows in fetched.items():
        setattr(recipe, _LINKED[field][0], rows)


def create(db: Session, payload) -> Recipe:
    lists = {field: getattr(payload, field) for field in LIST_FIELDS}
    dish_id = _check_dish(db, payload.dish_id, payload.new_dish)
    if payload.status_id is None:
        status_id = _first_status(db)
    else:
        status_id = payload.status_id
        _check_status(db, status_id)
    fetched = _check_and_fetch(db, lists)
    _check_line_targets(db, None, dish_id, payload.new_dish, _flat(lists, "lines"))
    groups = _check_groups(db, lists)
    new_ids = _resolve_new(db, lists, payload.new_dish)  # the first write

    scalars = payload.model_dump(exclude={*LIST_FIELDS, "dish_id", "new_dish"})
    scalars["status_id"] = status_id
    scalars["dish_id"] = new_ids["dish"] if new_ids["dish"] is not None else dish_id
    recipe = Recipe(**scalars)
    db.add(recipe)
    db.flush()
    _apply_lists(db, recipe, lists, fetched, groups, new_ids)
    db.commit()
    return get(db, recipe.id)


def update(db: Session, recipe_id: int, payload) -> Recipe:
    recipe = get(db, recipe_id)
    sent = payload.model_fields_set
    lists = {field: getattr(payload, field) for field in LIST_FIELDS if field in sent}
    scalars = {
        field: getattr(payload, field)
        for field in sent
        if field not in LIST_FIELDS and field not in ("dish_id", "new_dish")
    }
    new_dish = payload.new_dish if "new_dish" in sent else None

    moving = "dish_id" in sent or new_dish is not None
    dish_id = _check_dish(db, payload.dish_id, new_dish) if moving else recipe.dish_id
    if "status_id" in scalars:
        _check_status(db, scalars["status_id"])
    fetched = _check_and_fetch(db, lists)
    # The lines are checked when they are sent - and when the dish moves, the
    # lines the recipe keeps, which may name the dish it is moving to.
    if "lines" in lists:
        _check_line_targets(db, recipe.id, dish_id, new_dish, _flat(lists, "lines"))
    elif moving:
        kept = [_KeptLine(line) for line in recipe.lines]
        _check_line_targets(db, recipe.id, dish_id, new_dish, kept)
    groups = _check_groups(db, lists)
    new_ids = _resolve_new(db, lists, new_dish)  # the first write

    if moving:
        recipe.dish_id = new_ids["dish"] if new_ids["dish"] is not None else dish_id
    for field, value in scalars.items():
        setattr(recipe, field, value)
    _apply_lists(db, recipe, lists, fetched, groups, new_ids)
    db.commit()
    # A moved recipe's loaded dish is the old one until the session forgets it.
    db.expire_all()
    return get(db, recipe_id)


def cascade_counts(db: Session, recipe_id: int) -> dict[str, int]:
    """What a delete would take with it, for the confirmation dialog.

    Method and equipment links cascade too but are not counted - they remove
    nothing the user would miss - and neither are gallery rows, as for an
    ingredient: the pictures survive. Nor are the line and step groups: the
    lines and steps inside them are counted, which is what the user would
    miss. The dish is never taken: a dish outlives its last recipe.
    """
    return {
        "sources": db.query(RecipeSource).filter(RecipeSource.recipe_id == recipe_id).count(),
        "lines": db.query(RecipeLine).filter(RecipeLine.recipe_id == recipe_id).count(),
        "steps": db.query(RecipeStep).filter(RecipeStep.recipe_id == recipe_id).count(),
    }
