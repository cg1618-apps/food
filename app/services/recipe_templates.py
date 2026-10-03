"""Recipe templates: saving them, reading them back resolved, ordering them,
making one from a recipe, and keeping them right through an ingredient merge.

A body is stored in one canonical form, whatever shape it arrived in:

    {"servings", "time",
     "lines": [{"ingredient_id", "sub_dish_id", "amount", "note", "is_optional"}],
     "line_groups": [{"line_group_id", "name", "lines": [...]}],
     "steps": [{"body", "kind"}],
     "step_groups": [{"step_group_id", "name", "steps": [...]}],
     "method_ids", "equipment_ids"}

Writes check everything a recipe save checks that a template can hold - every
id names a row, every group follows the recipe's group rules - and refuse a
line that would create a row. Every refusal comes before anything is written.

Reads are the other way round. Nothing in the database stops a row a body
names from being deleted, so a read drops whatever is gone and counts it:
a line whose ingredient or dish is gone, a method or a piece of equipment that
is gone, and a group whose 設定 value is gone - that group's rows move to the
end of the ungrouped ones, as removing a group in the form moves them. The
stored body is left as it is; the next save writes what the form then holds.
"""

import copy

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import (
    CookingMethod,
    Dish,
    Equipment,
    Ingredient,
    LineGroup,
    RecipeTemplate,
    StepGroup,
)
from app.services import recipes
from app.services.lookup import fetch_all

NEW_REFUSED = (
    "A template never creates an ingredient or a dish; pick an existing one for every line."
)
NAME_TAKEN = "Another template already has that name."


def _ordered(query):
    return query.order_by(RecipeTemplate.sort_order, func.lower(RecipeTemplate.name), RecipeTemplate.id)


def listed(db: Session) -> list[RecipeTemplate]:
    """Every template, in the owner's order; a tie falls back to the name."""
    return _ordered(db.query(RecipeTemplate)).all()


def get(db: Session, template_id: int) -> RecipeTemplate:
    row = db.get(RecipeTemplate, template_id)
    if row is None:
        raise AppError(404, "No such template.")
    return row


def _all_lines(body: dict) -> list[dict]:
    return [*body["lines"], *(line for group in body["line_groups"] for line in group["lines"])]


def counts(row: RecipeTemplate) -> tuple[int, int]:
    """Lines and steps as stored, grouped or not."""
    body = row.body
    steps = [*body["steps"], *(s for group in body["step_groups"] for s in group["steps"])]
    return len(_all_lines(body)), len(steps)


# --- writing -------------------------------------------------------------------


def _check_name(db: Session, name: str, template_id: int | None = None) -> None:
    query = db.query(RecipeTemplate.id).filter(func.lower(RecipeTemplate.name) == name.lower())
    if template_id is not None:
        query = query.filter(RecipeTemplate.id != template_id)
    if query.first() is not None:
        raise AppError(422, NAME_TAKEN)


def _line(entry) -> dict:
    return {
        "ingredient_id": entry.ingredient_id,
        "sub_dish_id": entry.sub_dish_id,
        "amount": entry.amount,
        "note": entry.note,
        "is_optional": entry.is_optional,
    }


def _step(entry) -> dict:
    return {"body": entry.body, "kind": entry.kind}


def canonical(db: Session, body) -> dict:
    """A validated `TemplateBodyIn` as it is stored. Read-only: refuses with
    a 422 before anything is written, and writes nothing itself."""
    lines = [*body.lines, *(line for group in body.line_groups for line in group.lines)]
    if any(line.new_ingredient is not None or line.new_dish is not None for line in lines):
        raise AppError(422, NEW_REFUSED)
    fetch_all(db, Ingredient, [e.ingredient_id for e in lines if e.ingredient_id is not None], "ingredient")
    fetch_all(db, Dish, [e.sub_dish_id for e in lines if e.sub_dish_id is not None], "dish")
    methods = fetch_all(db, CookingMethod, body.method_ids, "cooking method")
    equipment = fetch_all(db, Equipment, body.equipment_ids, "equipment")
    line_groups = recipes.resolve_groups(db, "lines", body.line_groups)
    step_groups = recipes.resolve_groups(db, "steps", body.step_groups)

    return {
        "servings": body.servings,
        "time": body.time,
        "lines": [_line(e) for e in body.lines],
        "line_groups": [
            {"line_group_id": value_id, "name": name, "lines": [_line(e) for e in group.lines]}
            for group, (value_id, name) in zip(body.line_groups, line_groups, strict=True)
        ],
        "steps": [_step(e) for e in body.steps],
        "step_groups": [
            {"step_group_id": value_id, "name": name, "steps": [_step(e) for e in group.steps]}
            for group, (value_id, name) in zip(body.step_groups, step_groups, strict=True)
        ],
        "method_ids": [row.id for row in methods],
        "equipment_ids": [row.id for row in equipment],
    }


def _next_sort_order(db: Session) -> int:
    last = db.query(func.max(RecipeTemplate.sort_order)).scalar()
    return 0 if last is None else last + 1


def _insert(db: Session, name: str, body: dict) -> RecipeTemplate:
    row = RecipeTemplate(name=name, sort_order=_next_sort_order(db), body=body)
    db.add(row)
    db.commit()
    return get(db, row.id)


def create(db: Session, payload) -> RecipeTemplate:
    """A new template goes last."""
    _check_name(db, payload.name)
    return _insert(db, payload.name, canonical(db, payload.body))


def update(db: Session, template_id: int, payload) -> RecipeTemplate:
    row = get(db, template_id)
    sent = payload.model_fields_set
    if "name" in sent:
        _check_name(db, payload.name, template_id)
    body = canonical(db, payload.body) if "body" in sent else None

    if "name" in sent:
        row.name = payload.name
    if body is not None:
        row.body = body
    db.commit()
    return get(db, template_id)


def delete(db: Session, template_id: int) -> None:
    db.delete(get(db, template_id))
    db.commit()


def reorder(db: Session, ids: list[int]) -> list[RecipeTemplate]:
    """Number the templates 0, 1, 2 … in the order of `ids`, which must be
    exactly the current templates, each once - TBD's rule, for its reason."""
    rows = {row.id: row for row in db.query(RecipeTemplate)}
    if len(set(ids)) != len(ids) or set(ids) != set(rows):
        raise AppError(422, "The order must list every template exactly once.")
    for position, template_id in enumerate(ids):
        rows[template_id].sort_order = position
    db.commit()
    return listed(db)


def from_recipe(db: Session, recipe_id: int, name: str) -> RecipeTemplate:
    """A template of a recipe's structure: its lines and steps in their
    groups, the steps' kinds, its methods and equipment, servings and time.
    Not its dish, name, status, sources, notes or pictures.

    Everything it names exists - the recipe's foreign keys say so - so the
    body is built straight from the rows rather than re-validated.
    """
    recipe = recipes.get(db, recipe_id)
    _check_name(db, name)

    def grouped(rows, groups, build, id_field, inner):
        by_group: dict[int | None, list] = {}
        for item in rows:
            by_group.setdefault(item.group_id, []).append(build(item))
        return by_group.get(None, []), [
            {id_field: getattr(group, id_field), "name": group.name, inner: by_group.get(group.id, [])}
            for group in groups
        ]

    lines, line_groups = grouped(recipe.lines, recipe.line_groups, _line, "line_group_id", "lines")
    steps, step_groups = grouped(recipe.steps, recipe.step_groups, _step, "step_group_id", "steps")
    body = {
        "servings": recipe.servings,
        "time": recipe.time,
        "lines": lines,
        "line_groups": line_groups,
        "steps": steps,
        "step_groups": step_groups,
        "method_ids": [row.id for row in recipe.methods],
        "equipment_ids": [row.id for row in recipe.equipment],
    }
    return _insert(db, name, body)


# --- reading -------------------------------------------------------------------


def _by_id(db: Session, model, ids) -> dict:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    return {row.id: row for row in db.query(model).filter(model.id.in_(wanted))}


def _ref(row) -> dict:
    return {"id": row.id, "display_name": row.display_name}


def resolve(db: Session, row: RecipeTemplate) -> tuple[dict, int]:
    """The body in the recipe response's shapes, with every reference that
    no longer exists left out, and how many were. One query per table."""
    body = row.body
    lines = _all_lines(body)
    ingredients = _by_id(db, Ingredient, [line["ingredient_id"] for line in lines])
    dishes = _by_id(db, Dish, [line["sub_dish_id"] for line in lines])
    line_values = _by_id(db, LineGroup, [g["line_group_id"] for g in body["line_groups"]])
    step_values = _by_id(db, StepGroup, [g["step_group_id"] for g in body["step_groups"]])
    methods = _by_id(db, CookingMethod, body["method_ids"])
    equipment = _by_id(db, Equipment, body["equipment_ids"])
    dropped = 0

    def resolve_lines(entries) -> list[dict]:
        nonlocal dropped
        out = []
        for entry in entries:
            ingredient = ingredients.get(entry["ingredient_id"])
            dish = dishes.get(entry["sub_dish_id"])
            if ingredient is None and dish is None:
                dropped += 1
                continue
            out.append(
                {
                    "ingredient": {
                        **_ref(ingredient),
                        "needs_detail": ingredient.needs_detail,
                    }
                    if ingredient
                    else None,
                    "sub_dish": {**_ref(dish), "kind": dish.kind} if dish else None,
                    "amount": entry["amount"],
                    "note": entry["note"],
                    "is_optional": entry["is_optional"],
                }
            )
        return out

    def resolve_pair(ungrouped, groups, values, id_field, inner, build):
        """Groups whose value is gone are dropped, their rows appended to the
        ungrouped ones; then every row is built."""
        nonlocal dropped
        rows, kept = list(ungrouped), []
        for group in groups:
            value_id = group[id_field]
            if value_id is not None and value_id not in values:
                dropped += 1
                rows.extend(group[inner])
                continue
            kept.append(group)
        out_groups = []
        for group in kept:
            value = values.get(group[id_field])
            out_groups.append(
                {
                    "group": _ref(value) if value else None,
                    "name": group["name"],
                    "display_name": value.display_name if value else group["name"],
                    inner: build(group[inner]),
                }
            )
        return build(rows), out_groups

    def resolve_steps(entries) -> list[dict]:
        return [{"kind": e["kind"], "body": e["body"]} for e in entries]

    def resolve_refs(ids, found) -> list[dict]:
        nonlocal dropped
        out = [_ref(found[i]) for i in ids if i in found]
        dropped += len(ids) - len(out)
        return out

    resolved_lines, resolved_line_groups = resolve_pair(
        body["lines"], body["line_groups"], line_values, "line_group_id", "lines", resolve_lines
    )
    resolved_steps, resolved_step_groups = resolve_pair(
        body["steps"], body["step_groups"], step_values, "step_group_id", "steps", resolve_steps
    )
    return {
        "servings": body["servings"],
        "time": body["time"],
        "lines": resolved_lines,
        "line_groups": resolved_line_groups,
        "steps": resolved_steps,
        "step_groups": resolved_step_groups,
        "methods": resolve_refs(body["method_ids"], methods),
        "equipment": resolve_refs(body["equipment_ids"], equipment),
    }, dropped


# --- ingredient merge ------------------------------------------------------------


def rewrite_ingredient(db: Session, source_id: int, target_id: int) -> None:
    """Point every template line naming `source_id` at `target_id` - part of
    an ingredient merge, inside its transaction.

    The body is replaced with a changed copy rather than edited in place:
    a JSONB column does not see a mutation inside the dict it holds.
    """
    for row in db.query(RecipeTemplate):
        body = copy.deepcopy(row.body)
        changed = False
        for line in _all_lines(body):
            if line["ingredient_id"] == source_id:
                line["ingredient_id"] = target_id
                changed = True
        if changed:
            row.body = body
    db.flush()
