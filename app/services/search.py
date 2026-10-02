"""The one LIKE pattern every search box builds.

A search term is text the user typed, not a pattern: `%`, `_` and the escape
character itself are matched literally. Without the escaping, a search for
"%" returns every row and "_" every row with at least one character, and
neither looks wrong on a small test set.
"""

ESCAPE = "\\"


def contains(q: str) -> str:
    """A LIKE pattern matching `q` anywhere, its wildcards escaped.

    Pass `escape=ESCAPE` to the `like` / `ilike` it is used in; PostgreSQL's
    default escape is the same backslash, but saying so keeps the pattern and
    the clause from depending on a server setting.
    """
    term = q.strip()
    for char in (ESCAPE, "%", "_"):
        term = term.replace(char, ESCAPE + char)
    return f"%{term}%"
