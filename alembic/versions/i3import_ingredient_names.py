"""the starting ingredient list

Revision ID: i3import
Revises: k1notes
Create Date: 2026-10-02

A data migration, and the only one that loads content rather than a
vocabulary: the owner's starting ingredient list, 194 names drawn from their
recipe document, read from `alembic/import/ingredients.csv`. The CSV sits
beside the migrations rather than under `data/` because `.dockerignore`
excludes `data/`, and this file has to reach the image it runs in on the box.

Header `name_cn,name_en,aliases,parent,category`; aliases are `|`-separated;
`parent` names another row of the file; `category` is one of the seeded
top-level categories, or empty for the fallback.

The file is VALIDATED in full before anything is written: a parent not in the
file, an unknown category, two rows sharing a name_cn or a name_en
(casefold), a row with no name, and an alias that repeats or equals a row name
all raise. A malformed file stops the migration; it does not half-load.

Every inserted row is a stub (`needs_detail` true) - names, aliases, category
and parent, nothing else. Written in SQL through the bind and importing
nothing from `app.models`, as every revision here is.

Polite to what is already there. A row is skipped when its name_cn or name_en
matches (casefold) any existing ingredient's name slot or alias - a row the
owner typed by hand, or a second run, never collides with the unique name
indexes, and existing rows are never modified. Parents are resolved after
inserting, by name, so a skipped row's existing twin still becomes its file
children's parent. A link that would point at itself or close a cycle is
skipped.

Downgrade is a deliberate no-op. The rows are ordinary data from the moment
they land, and the owner may have filled them in; deleting them is worse than
leaving them, and identifying "still untouched" would need a marker column
every row carries forever.
"""

import csv
from dataclasses import dataclass, field
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision = "i3import"
down_revision = "k1notes"
branch_labels = None
depends_on = None

CSV_PATH = Path(__file__).resolve().parents[1] / "import" / "ingredients.csv"
HEADER = ["name_cn", "name_en", "aliases", "parent", "category"]

# The top-level categories v1ocabulary seeds. Copied, not imported: a revision
# must not depend on another revision's module.
SEEDED_CATEGORIES = [
    "肉類", "海鮮", "蔬菜", "菇類", "水果", "蛋豆製品", "主食穀物", "調味料", "乳製品", "乾貨",
]


@dataclass
class Row:
    line: int
    name_cn: str | None
    name_en: str | None
    aliases: list[str] = field(default_factory=list)
    parent: str | None = None
    category: str | None = None

    @property
    def names(self) -> list[str]:
        return [name for name in (self.name_cn, self.name_en) if name]

    @property
    def label(self) -> str:
        return f"line {self.line} ({self.name_cn or self.name_en})"


def _blank_to_none(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def read_rows(path: Path) -> list[Row]:
    """Parse the file. Shape only - `validate` judges the content."""
    with open(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != HEADER:
            raise ValueError(f"{path.name}: header is {reader.fieldnames}, expected {HEADER}")
        return [
            Row(
                line=reader.line_num,
                name_cn=_blank_to_none(record["name_cn"]),
                name_en=_blank_to_none(record["name_en"]),
                aliases=[a.strip() for a in (record["aliases"] or "").split("|") if a.strip()],
                parent=_blank_to_none(record["parent"]),
                category=_blank_to_none(record["category"]),
            )
            for record in reader
        ]


def validate(rows: list[Row]) -> None:
    """Raise ValueError naming every defect, or return having found none."""
    problems: list[str] = []
    seen: dict[str, dict[str, str]] = {"name_cn": {}, "name_en": {}}
    row_names: set[str] = set()
    for row in rows:
        if not row.names:
            problems.append(f"line {row.line}: a row with no name")
        for slot in ("name_cn", "name_en"):
            value = getattr(row, slot)
            if value is None:
                continue
            key = value.casefold()
            if key in seen[slot]:
                problems.append(f"{row.label}: {slot} {value!r} repeats {seen[slot][key]}")
            else:
                seen[slot][key] = row.label
            row_names.add(key)

    seeded = {name.casefold() for name in SEEDED_CATEGORIES}
    aliases_seen: dict[str, str] = {}
    for row in rows:
        if row.parent is not None and row.parent.casefold() not in row_names:
            problems.append(f"{row.label}: parent {row.parent!r} is not a row of the file")
        if row.category is not None and row.category.casefold() not in seeded:
            problems.append(f"{row.label}: category {row.category!r} is not a seeded category")
        for alias in row.aliases:
            key = alias.casefold()
            if key in row_names:
                problems.append(f"{row.label}: alias {alias!r} is a row name")
            elif key in aliases_seen:
                problems.append(f"{row.label}: alias {alias!r} repeats {aliases_seen[key]}")
            else:
                aliases_seen[key] = row.label

    if problems:
        raise ValueError("ingredients.csv is malformed:\n" + "\n".join(problems))


def _existing_names(bind) -> dict[str, int]:
    """Every existing name slot and alias, casefolded, to its ingredient.

    Name slots win over aliases when one string is both, and the lower id wins
    among equals, so a twin is found the same way on every run.
    """
    names: dict[str, int] = {}
    slots = bind.execute(
        sa.text("SELECT id, name_cn, name_en, name_alt FROM ingredient ORDER BY id")
    ).all()
    for ingredient_id, *values in slots:
        for value in values:
            if value:
                names.setdefault(value.casefold(), ingredient_id)
    aliases = bind.execute(
        sa.text("SELECT ingredient_id, value FROM ingredient_alias ORDER BY ingredient_id")
    ).all()
    for ingredient_id, value in aliases:
        names.setdefault(value.casefold(), ingredient_id)
    return names


def _categories(bind) -> tuple[dict[str, int], int]:
    fallback = bind.execute(
        sa.text("SELECT id FROM ingredient_category WHERE is_fallback")
    ).scalar_one()
    top_level = bind.execute(
        sa.text(
            "SELECT id, name_cn FROM ingredient_category "
            "WHERE parent_id IS NULL AND NOT is_fallback AND name_cn IS NOT NULL ORDER BY id"
        )
    ).all()
    by_name: dict[str, int] = {}
    for category_id, name in top_level:
        by_name.setdefault(name.casefold(), category_id)
    return by_name, fallback


def _would_cycle(bind, child: int, parent: int) -> bool:
    if child == parent:
        return True
    return bool(
        bind.execute(
            sa.text(
                "WITH RECURSIVE up(id) AS ("
                "  SELECT parent_id FROM ingredient WHERE id = :parent"
                "  UNION SELECT i.parent_id FROM ingredient i JOIN up ON i.id = up.id"
                ") SELECT EXISTS (SELECT 1 FROM up WHERE id = :child)"
            ),
            {"parent": parent, "child": child},
        ).scalar()
    )


def load(bind, rows: list[Row]) -> int:
    """Insert the rows not already present; link parents. Returns the count."""
    existing = _existing_names(bind)
    categories, fallback = _categories(bind)

    # Every file name, casefolded, to the ingredient that now answers to it:
    # the new row, or the existing twin a skipped row matched.
    resolved: dict[str, int] = {}
    inserted: list[tuple[Row, int]] = []
    for row in rows:
        twin = next(
            (existing[n.casefold()] for n in row.names if n.casefold() in existing), None
        )
        if twin is None:
            category = categories.get((row.category or "").casefold(), fallback)
            ingredient_id = bind.execute(
                sa.text(
                    "INSERT INTO ingredient "
                    "(name_cn, name_en, category_id, needs_detail, created_at, updated_at) "
                    "VALUES (:cn, :en, :category, true, "
                    "now() AT TIME ZONE 'Asia/Taipei', now() AT TIME ZONE 'Asia/Taipei') "
                    "RETURNING id"
                ),
                {"cn": row.name_cn, "en": row.name_en, "category": category},
            ).scalar_one()
            for alias in row.aliases:
                bind.execute(
                    sa.text(
                        "INSERT INTO ingredient_alias (ingredient_id, value) VALUES (:i, :v)"
                    ),
                    {"i": ingredient_id, "v": alias},
                )
            inserted.append((row, ingredient_id))
        else:
            ingredient_id = twin
        for name in row.names:
            resolved[name.casefold()] = ingredient_id

    for row, ingredient_id in inserted:
        if row.parent is None:
            continue
        parent_id = resolved[row.parent.casefold()]
        if _would_cycle(bind, ingredient_id, parent_id):
            continue
        bind.execute(
            sa.text("UPDATE ingredient SET parent_id = :p WHERE id = :i"),
            {"p": parent_id, "i": ingredient_id},
        )
    return len(inserted)


def upgrade() -> None:
    rows = read_rows(CSV_PATH)
    validate(rows)
    load(op.get_bind(), rows)


def downgrade() -> None:
    # Deliberately nothing - see the docstring. The rows stay.
    pass
