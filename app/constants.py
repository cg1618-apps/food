"""Closed vocabularies, as Python constants rather than Postgres enums.

A `String` column plus a list here, validated in the Pydantic layer, is the
house shape: media carries no `sa.Enum` in any revision, because altering a
Postgres enum type is a migration for what should be a one-line edit. The
database stores whatever it is given; the API is what refuses an unknown value.
"""

PRESERVATION_METHODS = [
    "常溫",  # room temperature
    "冷藏",  # refrigerated
    "冷凍",  # frozen
    "乾燥",  # dried
    "醃漬",  # pickled or cured
    "油封",  # preserved under oil or fat
    "真空",  # vacuum sealed
]

PRESERVATION_STATES = {
    "unused": "未使用",  # bought and not yet opened or cut
    "opened": "已開封",  # opened, cut or partly used
    "cooked": "熟食",  # cooked - the reference sheet's 熟肉 rows
}

# How good one variety is: the Fruit sheet's grades.
RATINGS = ["S", "A", "B", "C", "D"]

# Every closed list the frontend renders, with its display label, served by
# GET /api/vocabularies/fixed so no list is copied into a component. Plan 2
# appends recipe kinds, statuses and source platforms.
FIXED_VOCABULARIES = {
    "preservation_methods": [{"value": m, "label": m} for m in PRESERVATION_METHODS],
    "preservation_states": [{"value": k, "label": v} for k, v in PRESERVATION_STATES.items()],
    "ratings": [{"value": r, "label": r} for r in RATINGS],
}
