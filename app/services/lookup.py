"""Resolving the ids a request body names.

Shared by every service whose payload carries id lists - a recipe's
methods and lines, an ingredient's, a dish's and a kitchen note's labels - so
the rule is stated once.
"""

from sqlalchemy.orm import Session

from app.constants import LABEL_SCOPES
from app.errors import AppError
from app.models import Label


def fetch_all(db: Session, model, ids: list[int], what: str) -> list:
    """The rows `ids` name, in that order, or 422 naming the first missing id.

    422 rather than 404: the URL resolved; it is the payload that is wrong.
    Repeats collapse to one row, so a list sent with a duplicate id links once.
    """
    wanted = list(dict.fromkeys(ids))
    if not wanted:
        return []
    found = {row.id: row for row in db.query(model).filter(model.id.in_(wanted))}
    missing = [i for i in wanted if i not in found]
    if missing:
        raise AppError(422, f"No such {what}: {missing[0]}.")
    return [found[i] for i in wanted]


def check_label_scope(labels: list, scope: str) -> None:
    """422 naming the first label that belongs to another library.

    422, as for an id naming nothing: the label exists, but the payload asks
    for a link the rules do not allow - an ingredient takes only ingredient
    labels, a dish only dish labels, a note only note labels.
    """
    for label in labels:
        if label.scope != scope:
            raise AppError(
                422,
                f"{label.display_name} is a {LABEL_SCOPES[label.scope]} label, "
                f"not a {LABEL_SCOPES[scope]} label.",
            )


def fetch_labels(db: Session, ids: list[int], scope: str) -> list:
    """`fetch_all` for labels, refusing any of another library."""
    labels = fetch_all(db, Label, ids, "label")
    check_label_scope(labels, scope)
    return labels
