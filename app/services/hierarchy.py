"""Cycle guards for the two trees, and the tree assembly the API returns.

Both `ingredient.parent_id` and `ingredient_category.parent_id` are
self-references, and neither can be guarded by a CHECK: "no cycles" needs to
walk the graph, which SQL can do only with a recursive query and a trigger.
So the guard lives here, on the write path, and it is the only thing standing
between the app and a subtree that no query can ever terminate over.

The failure a cycle causes is not a wrong answer, it is a hang - so these are
called before every parent change, not only when one looks suspicious.
"""

from sqlalchemy.orm import Session

from app.errors import AppError

# A tree this app builds by hand will never be deep. The limit exists to turn
# an unexpected cycle - one created by a route that forgot to call the guard,
# or by a hand-written UPDATE - into a refusal rather than an endless walk.
MAX_DEPTH = 32


def _walk_to_root(db: Session, model, start_id: int | None):
    """Yield each ancestor id from `start_id` upward, stopping at the root."""
    seen = set()
    current = start_id
    steps = 0
    while current is not None:
        if current in seen or steps > MAX_DEPTH:
            # Already a cycle, or deeper than anything legitimate. The caller
            # decides what to say; this function refuses to loop forever.
            return
        seen.add(current)
        yield current
        steps += 1
        current = db.query(model.parent_id).filter(model.id == current).scalar()


def check_parent(db: Session, model, row_id: int | None, new_parent_id: int | None, what: str):
    """Refuse a parent that would make a cycle, or that does not exist.

    `row_id` is None when creating: a row with no id yet cannot be its own
    ancestor, so only the existence check applies.
    """
    if new_parent_id is None:
        return

    parent = db.query(model).filter(model.id == new_parent_id).one_or_none()
    if parent is None:
        # 422 rather than 404: the missing thing is a value inside the payload,
        # not the resource being addressed. A 404 here would say the
        # ingredient being edited does not exist, which is a different and
        # wrong statement.
        raise AppError(422, f"That parent {what} does not exist.")

    if row_id is None:
        return

    if new_parent_id == row_id:
        raise AppError(422, f"A {what} cannot be its own parent.")

    if row_id in set(_walk_to_root(db, model, new_parent_id)):
        raise AppError(
            422,
            f"That would put the {what} inside one of its own descendants.",
        )


def build_tree(rows, counts: dict[int, int], node_schema):
    """Assemble a flat list of category rows into a nested structure.

    In Python, from one query, because the tree is a few dozen rows. A
    recursive CTE would be correct and would also be the only recursive query
    in the codebase, for a result that fits on a screen.

    Rows whose parent is missing from `rows` become roots rather than
    vanishing. That cannot happen through the API - the foreign key is
    RESTRICT - but a filtered subtree passed in here would otherwise silently
    lose entire branches, and a tree that quietly drops nodes is worse than one
    that shows an orphan.
    """
    nodes = {
        row.id: node_schema(
            id=row.id,
            display_name=row.display_name,
            name_cn=row.name_cn,
            name_en=row.name_en,
            parent_id=row.parent_id,
            sort_order=row.sort_order,
            is_fallback=row.is_fallback,
            children=[],
            ingredient_count=counts.get(row.id, 0),
        )
        for row in rows
    }

    roots = []
    for node in nodes.values():
        parent = nodes.get(node.parent_id) if node.parent_id is not None else None
        if parent is None:
            roots.append(node)
        else:
            parent.children.append(node)

    def sort(level):
        level.sort(key=lambda n: (n.sort_order, n.display_name))
        for node in level:
            sort(node.children)

    sort(roots)
    return roots
