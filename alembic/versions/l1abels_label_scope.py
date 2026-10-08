"""labels: every label belongs to exactly one library

Revision ID: l1abels
Revises: h1eating
Create Date: 2026-10-08

`label` gains `scope`, a NOT NULL String holding one of `LABEL_SCOPES`
(`ingredient`, `dish`, `note`) - validated by the API, not by a Postgres enum,
as every closed list here. `uq_label_name_cn` and `uq_label_name_en` become
unique on `(scope, lower(name))` instead of `lower(name)`, so 辣 may exist once
per library.

The backfill reads the link tables. A label linked only from ingredients
becomes `ingredient`, only from dishes `dish`, only from kitchen notes
`note`. **A label linked from nothing is deleted**: it has no library to
belong to, and the eight `v1ocabulary` seeded (飯 麵 肉 麵包 馬鈴薯 地瓜 沙拉
鍋) are the owner's to recreate in the library that wants them. **A label
linked from more than one library stops the upgrade** with a message naming
it, before anything is changed: which library keeps it, and whether the other
gets a label of its own, is the owner's decision and not one to guess.

Downgrade is lossy, by necessity: it drops `scope` and restores the global
indexes, and a deleted label is not restored. Two labels of one name in
different libraries cannot both survive the global index, so the downgrade
stops naming them rather than choosing one to delete.

Imports nothing from `app.models`, as every revision here.
"""

import sqlalchemy as sa

from alembic import op

revision = "l1abels"
down_revision = "h1eating"
branch_labels = None
depends_on = None

# Each scope, and the link table that carries labels of it.
LINKS = {
    "ingredient": "ingredient_label",
    "dish": "dish_label",
    "note": "kitchen_note_label",
}


def _name(row) -> str:
    return row.name_cn or row.name_en


def upgrade() -> None:
    conn = op.get_bind()
    used_by = " UNION ALL ".join(
        f"SELECT DISTINCT label_id, '{scope}' AS scope FROM {table}"
        for scope, table in LINKS.items()
    )
    shared = conn.execute(
        sa.text(
            "SELECT l.id, l.name_cn, l.name_en, string_agg(u.scope, ', ' ORDER BY u.scope) AS scopes "
            f"FROM label l JOIN ({used_by}) u ON u.label_id = l.id "
            "GROUP BY l.id HAVING count(*) > 1 ORDER BY l.id"
        )
    ).all()
    if shared:
        names = "; ".join(f"{_name(row)} (id {row.id}: {row.scopes})" for row in shared)
        raise RuntimeError(
            "Every label must belong to one library, and these are used by more than one: "
            f"{names}. Remove each from all but one library, then upgrade again."
        )

    op.add_column("label", sa.Column("scope", sa.String(), nullable=True))
    for scope, table in LINKS.items():
        conn.execute(
            sa.text(f"UPDATE label SET scope = :scope WHERE id IN (SELECT label_id FROM {table})"),
            {"scope": scope},
        )
    conn.execute(sa.text("DELETE FROM label WHERE scope IS NULL"))
    op.alter_column("label", "scope", nullable=False)

    op.drop_index("uq_label_name_cn", table_name="label")
    op.drop_index("uq_label_name_en", table_name="label")
    op.create_index(
        "uq_label_name_cn", "label", ["scope", sa.text("lower(name_cn)")], unique=True
    )
    op.create_index(
        "uq_label_name_en", "label", ["scope", sa.text("lower(name_en)")], unique=True
    )


def downgrade() -> None:
    conn = op.get_bind()
    clashes = []
    for column in ("name_cn", "name_en"):
        clashes += conn.execute(
            sa.text(
                f"SELECT min({column}) AS name FROM label WHERE {column} IS NOT NULL "
                f"GROUP BY lower({column}) HAVING count(*) > 1"
            )
        ).scalars().all()
    if clashes:
        raise RuntimeError(
            "Labels of one name in different libraries cannot share the global unique index: "
            f"{', '.join(clashes)}. Rename or delete all but one of each, then downgrade again."
        )

    op.drop_index("uq_label_name_cn", table_name="label")
    op.drop_index("uq_label_name_en", table_name="label")
    op.drop_column("label", "scope")
    op.create_index("uq_label_name_cn", "label", [sa.text("lower(name_cn)")], unique=True)
    op.create_index("uq_label_name_en", "label", [sa.text("lower(name_en)")], unique=True)
