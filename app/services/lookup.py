"""Resolving the ids a request body names.

Shared by every service whose payload carries id lists - a recipe's labels,
methods and lines, a kitchen note's labels - so the rule is stated once.
"""

from sqlalchemy.orm import Session

from app.errors import AppError


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
