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

# A dish is eaten; a base - a sauce, a stock, a dough - is cooked to be used
# inside other recipes. The kind is how the library files a recipe, not a rule:
# a recipe line's sub_recipe_id may name a recipe of either kind.
RECIPE_KINDS = {"dish": "料理", "base": "基底"}

# What a kitchen note is: a compilation of many dishes, one technique, or
# something to look up. How the notes library files a note, not a rule.
KITCHEN_NOTE_KINDS = {"compilation": "合輯", "technique": "技巧", "reference": "參考"}

# Every closed list the frontend renders, with its display label, served by
# GET /api/vocabularies/fixed so no list is copied into a component.
FIXED_VOCABULARIES = {
    "preservation_methods": [{"value": m, "label": m} for m in PRESERVATION_METHODS],
    "preservation_states": [{"value": k, "label": v} for k, v in PRESERVATION_STATES.items()],
    "ratings": [{"value": r, "label": r} for r in RATINGS],
    "recipe_kinds": [{"value": k, "label": v} for k, v in RECIPE_KINDS.items()],
    "kitchen_note_kinds": [{"value": k, "label": v} for k, v in KITCHEN_NOTE_KINDS.items()],
}
