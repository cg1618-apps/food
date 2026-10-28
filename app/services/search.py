"""The one LIKE pattern every search box builds, and the match tiers the
universal search ranks by.

A search term is text the user typed, not a pattern: `%`, `_` and the escape
character itself are matched literally. Without the escaping, a search for
"%" returns every row and "_" every row with at least one character, and
neither looks wrong on a small test set.

Each library matches its `q` with `contains` - any name slot or alias holding
the term, case-insensitively. The universal search (app/services/universal_search.py)
filters by exactly those clauses and orders by `rank` over the stricter
tiers, so it can never find a row the library's own search would not.
"""

from sqlalchemy import case, func, literal

ESCAPE = "\\"

# How a term is compared with a value, strictest first. `contains` is what
# every library's `q` filters by; `exact` and `prefix` exist to rank by.
EXACT = "exact"
PREFIX = "prefix"
CONTAINS = "contains"


def _escaped(q: str) -> str:
    term = q.strip()
    for char in (ESCAPE, "%", "_"):
        term = term.replace(char, ESCAPE + char)
    return term


def contains(q: str) -> str:
    """A LIKE pattern matching `q` anywhere, its wildcards escaped.

    Pass `escape=ESCAPE` to the `like` / `ilike` it is used in; PostgreSQL's
    default escape is the same backslash, but saying so keeps the pattern and
    the clause from depending on a server setting.
    """
    return f"%{_escaped(q)}%"


def starts_with(q: str) -> str:
    """A LIKE pattern matching a value that begins with `q`, escaped as
    `contains` is."""
    return f"{_escaped(q)}%"


def term_match(column, q: str, how: str = CONTAINS):
    """`column` compared with `q` case-insensitively: equal to it, beginning
    with it, or holding it anywhere."""
    if how == EXACT:
        return func.lower(column) == func.lower(literal(q.strip()))
    pattern = starts_with(q) if how == PREFIX else contains(q)
    return column.ilike(pattern, escape=ESCAPE)


def rank(tiers):
    """0 for a row matching the first clause, 1 the second, and so on; a row
    matching none of them sorts after every tier. Lower is better."""
    return case(*((clause, i) for i, clause in enumerate(tiers)), else_=len(tiers))


def display_order(*columns):
    """The SQL twin of a row's `display_name` sort: the first name column that
    holds something, lower-cased, compared by code point - the order the
    libraries' Python `casefold()` sort gives."""
    first = func.coalesce(*(func.nullif(func.btrim(column), "") for column in columns))
    return func.lower(first).collate("C")
