"""Reading and writing recipes. The router does HTTP; this does the work.

Every write validates everything it can BEFORE it changes anything: names,
the course, the status, every source's platform and author, the version rule,
every id in the vocabulary lists, every group's value or name, every line
target and the cycle guard. Only then are stubs and new authors created and
the row touched.

Lines and steps are each a pair on the wire - the ungrouped rows, and the
groups with theirs - and are stored as one recipe-wide list of rows, each
naming its group or none, positioned in the order the page shows them:
ungrouped first, then group by group.
One request is one transaction, and the ordering is what makes a refused save
leave nothing behind even in a session that is never rolled back - the test
session is one such, and an autoflush is all it takes to half-write a row.

There are no reverse relationships from an ingredient or a recipe to the lines
that name them, so "used in" is always an explicit query here.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.errors import AppError
from app.models import (
    Author,
    CookingMethod,
    Equipment,
    Ingredient,
    IngredientAlias,
    IngredientCategory,
    Label,
    LineGroup,
    Recipe,
    RecipeAlias,
    RecipeCourse,
    RecipeEquipment,
    RecipeImage,
    RecipeLabel,
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
from app.services.hierarchy import MAX_DEPTH
from app.services.lookup import fetch_all
from app.services.search import ESCAPE, contains

# The id lists a recipe carries, the relationship each fills, the model it
# names, and the word a 422 uses for it.
_LINKED = {
    "serves_as_ids": ("serves_as", RecipeCourse, "course"),
    "label_ids": ("labels", Label, "label"),
    "method_ids": ("methods", CookingMethod, "cooking method"),
    "equipment_ids": ("equipment", Equipment, "equipment"),
}


def _loaded(query):
    """Every relationship the response needs, in one round trip each."""
    return query.options(
        selectinload(Recipe.course),
        selectinload(Recipe.status),
        selectinload(Recipe.variant_of).selectinload(Recipe.variants),
        selectinload(Recipe.variants),
        selectinload(Recipe.aliases),
        selectinload(Recipe.sources).selectinload(RecipeSource.platform),
        selectinload(Recipe.sources).selectinload(RecipeSource.author),
        selectinload(Recipe.lines).selectinload(RecipeLine.ingredient),
        selectinload(Recipe.lines).selectinload(RecipeLine.sub_recipe),
        selectinload(Recipe.steps),
        selectinload(Recipe.line_groups).selectinload(RecipeLineGroup.group),
        selectinload(Recipe.step_groups).selectinload(RecipeStepGroup.group),
        selectinload(Recipe.images).selectinload(RecipeImage.image),
        selectinload(Recipe.labels),
        selectinload(Recipe.methods),
        selectinload(Recipe.equipment),
        selectinload(Recipe.serves_as),
    )


def _summary_loaded(query):
    """Every relationship a library row reads, in one round trip each.

    Lines and steps are loaded for `written_up`; a list of a few hundred rows
    rendering any of these lazily would issue a query per row.
    """
    return query.options(
        selectinload(Recipe.course),
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


def versions(recipe: Recipe) -> list[Recipe]:
    """The other recipes in this one's version family.

    For an original, its versions; for a version, its original's other
    versions - the original itself is `variant_of`, not one of these.
    """
    family = recipe.variant_of.variants if recipe.variant_of else recipe.variants
    others = [r for r in family if r.id != recipe.id]
    return sorted(others, key=lambda r: r.display_name.casefold())


def used_in(db: Session, recipe_id: int) -> list[Recipe]:
    """Distinct recipes with a line naming this one DIRECTLY.

    Depth zero: a dish using a base that uses this base is not counted. That
    is the same depth "used in" has through sub-recipes for an ingredient.
    """
    rows = (
        db.query(Recipe)
        .filter(
            Recipe.id.in_(
                select(RecipeLine.recipe_id)
                .where(RecipeLine.sub_recipe_id == recipe_id)
                .scalar_subquery()
            )
        )
        .all()
    )
    return sorted(rows, key=lambda r: r.display_name.casefold())


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
    sub-recipes is zero: a line naming a sub-recipe is not a line naming what
    that base uses.
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
    rows = db.query(Recipe).filter(Recipe.id.in_(recipe_ids_using_ingredients(ingredient_ids)))
    return sorted(rows, key=lambda r: r.display_name.casefold())


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
    rows = db.query(Recipe).filter(
        Recipe.id.in_(
            select(RecipeLine.recipe_id)
            .where(RecipeLine.ingredient_id == ingredient_id)
            .scalar_subquery()
        )
    )
    return sorted(rows, key=lambda r: r.display_name.casefold())


def _any_of(link, column, values):
    """Recipes with a `link` row whose `column` is any of `values`."""
    return Recipe.id.in_(select(link.recipe_id).where(column.in_(values)).scalar_subquery())


def search(
    db: Session,
    q: str | None = None,
    course_id: list[int] | None = None,
    status_id: list[int] | None = None,
    kind: list[str] | None = None,
    label_id: list[int] | None = None,
    method_id: list[int] | None = None,
    equipment_id: list[int] | None = None,
    author_id: list[int] | None = None,
    ingredient_id: list[int] | None = None,
    written_up: bool | None = None,
) -> list[Recipe]:
    """The library list. Each multi-valued filter means "any of" its values;
    different filters narrow each other.

    Every filter that reaches through another table is a subquery rather than
    a join, for the reason `ingredients.search` gives: a join returns the
    recipe once per matching row, which only shows on data with several.
    """
    query = _summary_loaded(db.query(Recipe))

    if q:
        term = contains(q)
        alias_match = (
            select(RecipeAlias.recipe_id)
            .where(func.lower(RecipeAlias.value).like(func.lower(term), escape=ESCAPE))
            .scalar_subquery()
        )
        query = query.filter(
            or_(
                Recipe.name_cn.ilike(term, escape=ESCAPE),
                Recipe.name_en.ilike(term, escape=ESCAPE),
                Recipe.name_alt.ilike(term, escape=ESCAPE),
                Recipe.id.in_(alias_match),
            )
        )

    if course_id:
        query = query.filter(Recipe.course_id.in_(course_id))
    if status_id:
        query = query.filter(Recipe.status_id.in_(status_id))
    if kind:
        query = query.filter(Recipe.kind.in_(kind))
    if label_id:
        query = query.filter(_any_of(RecipeLabel, RecipeLabel.label_id, label_id))
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

    rows = query.all()
    rows.sort(key=lambda r: r.display_name.casefold())
    return rows


# --- validation: everything here runs before anything is written -------------


def _check_course(db: Session, course_id: int | None) -> None:
    if course_id is not None:
        fetch_all(db, RecipeCourse, [course_id], "course")


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


def _check_version(db: Session, recipe_id: int | None, variant_of_id: int | None) -> None:
    """Versions are one level deep. `recipe_id` is None when creating."""
    if variant_of_id is None:
        return
    if variant_of_id == recipe_id:
        raise AppError(422, "A recipe cannot be a version of itself.")
    original = db.get(Recipe, variant_of_id)
    if original is None:
        raise AppError(422, f"No such recipe: {variant_of_id}.")
    if original.variant_of_id is not None:
        raise AppError(
            422, "That recipe is itself a version; make this a version of its original."
        )
    if recipe_id is not None:
        has_versions = db.query(Recipe.id).filter(Recipe.variant_of_id == recipe_id).first()
        if has_versions is not None:
            raise AppError(422, "A recipe with versions of its own cannot become a version.")


def _reachable_from(db: Session, start_ids: set[int]) -> set[int]:
    """Every recipe reachable from `start_ids` through sub-recipe lines,
    `start_ids` included. Breadth first, one query per level.

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
            raise AppError(422, "Recipes nest deeper than this app allows.")
        rows = db.execute(
            select(RecipeLine.sub_recipe_id).where(
                RecipeLine.recipe_id.in_(frontier), RecipeLine.sub_recipe_id.isnot(None)
            )
        )
        frontier = {sub_id for (sub_id,) in rows} - seen
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


def _resolve_groups(db: Session, rows_field: str, entries) -> list[tuple[int | None, str | None]]:
    """`(value id, one-off name)` per group, exactly one of the two set.

    Read-only, so it runs with the checks. Every id sent must exist; a name
    matching a value's name_cn or name_en, trimmed and case-insensitively,
    becomes that value. After that a recipe may not hold one group twice -
    the same value, or the same one-off name in any case - which the uniques
    on the group tables would refuse anyway, but only as "something clashed".
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
        rows_field: _resolve_groups(db, rows_field, lists[groups_field])
        for rows_field, (groups_field, *_rest) in _PAIRS.items()
        if lists.get(groups_field) is not None
    }


def _check_line_targets(db: Session, recipe_id: int | None, entries) -> None:
    """Every id a line names exists, and no sub-recipe makes a cycle.

    A new recipe has no id, so nothing can reach it yet and only existence
    applies. On an update the guard runs against the stored graph: this
    recipe's own lines are about to be replaced, and a walk that reaches this
    recipe stops being a question about them.
    """
    ingredient_ids = [e.ingredient_id for e in entries if e.ingredient_id is not None]
    fetch_all(db, Ingredient, ingredient_ids, "ingredient")
    sub_ids = [e.sub_recipe_id for e in entries if e.sub_recipe_id is not None]
    fetch_all(db, Recipe, sub_ids, "recipe")
    if recipe_id is None or not sub_ids:
        return
    if recipe_id in sub_ids:
        raise AppError(422, "A recipe cannot use itself as an ingredient.")
    if recipe_id in _reachable_from(db, set(sub_ids)):
        raise AppError(
            422, "That would make a loop: the recipe is already used inside that one."
        )


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


def _apply_aliases(recipe: Recipe, values: list[str]) -> None:
    """Reconciled by value, as `ingredients._apply_aliases` and for its reason."""
    wanted = list(dict.fromkeys(values))
    recipe.aliases = [row for row in recipe.aliases if row.value in wanted]
    kept = {row.value for row in recipe.aliases}
    recipe.aliases.extend(RecipeAlias(value=v) for v in wanted if v not in kept)


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


def _apply_lines(db: Session, recipe: Recipe, lists: dict, resolved, new_ids: dict[int, int]) -> None:
    """Replace the lines and their groups; a `new_ingredient` line takes its
    resolved id."""

    def line(index, e, group):
        return RecipeLine(
            position=index,
            group=group,
            ingredient_id=new_ids.get(index, e.ingredient_id),
            sub_recipe_id=e.sub_recipe_id,
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


def _check_and_fetch(db: Session, recipe_id: int | None, lists: dict) -> dict:
    """Validate every sent list; return the vocabulary rows to assign."""
    fetched = {}
    for field, (_, model, what) in _LINKED.items():
        if lists.get(field) is not None:
            fetched[field] = fetch_all(db, model, lists[field], what)
    if lists.get("sources") is not None:
        _check_sources(db, lists["sources"])
    if lists.get("lines") is not None:
        _check_line_targets(db, recipe_id, _flat(lists, "lines"))
    return fetched


def _resolve_new(db: Session, lists: dict) -> dict[str, dict[int, int]]:
    """The first write of a save: stubs for new ingredients, rows for new
    authors. Runs only after every check has passed."""
    return {
        "lines": _resolve_new_ingredients(db, _flat(lists, "lines")),
        "sources": _resolve_new_authors(db, lists.get("sources") or []),
    }


def _apply_lists(
    db: Session,
    recipe: Recipe,
    lists: dict,
    fetched: dict,
    groups: dict[str, list],
    new_ids: dict[str, dict[int, int]],
) -> None:
    """Every sent list. A pair is applied when it was sent - the schema has
    already refused one half without the other."""
    if lists.get("aliases") is not None:
        _apply_aliases(recipe, lists["aliases"])
    if lists.get("sources") is not None:
        _apply_sources(recipe, lists["sources"], new_ids["sources"])
    if "lines" in groups:
        _apply_lines(db, recipe, lists, groups["lines"], new_ids["lines"])
    if "steps" in groups:
        _apply_steps(db, recipe, lists, groups["steps"])
    for field, rows in fetched.items():
        setattr(recipe, _LINKED[field][0], rows)


def create(db: Session, payload) -> Recipe:
    lists = {field: getattr(payload, field) for field in LIST_FIELDS}
    _check_course(db, payload.course_id)
    if payload.status_id is None:
        status_id = _first_status(db)
    else:
        status_id = payload.status_id
        _check_status(db, status_id)
    _check_version(db, None, payload.variant_of_id)
    fetched = _check_and_fetch(db, None, lists)
    groups = _check_groups(db, lists)
    new_ids = _resolve_new(db, lists)  # the first write

    scalars = payload.model_dump(exclude=set(LIST_FIELDS))
    scalars["status_id"] = status_id
    # kind is set from the payload (whose default is the server default) so
    # the response needs no refresh to know it.
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
    scalars = {field: getattr(payload, field) for field in sent if field not in LIST_FIELDS}

    # The at-least-one-name rule, against the MERGED row, before anything is
    # assigned: assigning first would let an autoflush write the nameless row.
    merged = [scalars.get(f, getattr(recipe, f)) for f in ("name_cn", "name_en", "name_alt")]
    if not any(merged):
        raise AppError(422, "A recipe needs at least one name.")
    if "course_id" in scalars:
        _check_course(db, scalars["course_id"])
    if "status_id" in scalars:
        _check_status(db, scalars["status_id"])
    if "variant_of_id" in scalars:
        _check_version(db, recipe.id, scalars["variant_of_id"])
    fetched = _check_and_fetch(db, recipe.id, lists)
    groups = _check_groups(db, lists)
    new_ids = _resolve_new(db, lists)  # the first write

    for field, value in scalars.items():
        setattr(recipe, field, value)
    _apply_lists(db, recipe, lists, fetched, groups, new_ids)
    db.commit()
    return get(db, recipe_id)


def cascade_counts(db: Session, recipe_id: int) -> dict[str, int]:
    """What a delete would take with it, for the confirmation dialog.

    Serves-as, label, method and equipment links cascade too but are not
    counted - they remove nothing the user would miss - and neither are gallery
    rows, as for an ingredient: the pictures survive. Nor are the line and
    step groups: the lines and steps inside them are counted, which is what
    the user would miss.
    """
    return {
        "aliases": db.query(RecipeAlias).filter(RecipeAlias.recipe_id == recipe_id).count(),
        "sources": db.query(RecipeSource).filter(RecipeSource.recipe_id == recipe_id).count(),
        "lines": db.query(RecipeLine).filter(RecipeLine.recipe_id == recipe_id).count(),
        "steps": db.query(RecipeStep).filter(RecipeStep.recipe_id == recipe_id).count(),
    }
