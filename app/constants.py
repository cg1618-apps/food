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

# A dish is eaten; a 醬料 - a sauce, a stock, a dough - is cooked to be used
# inside other dishes. The kind is how the libraries file a dish, not a rule:
# a recipe line's sub_dish_id may name a dish of either kind.
DISH_KINDS = {"dish": "料理", "sauce": "醬料"}

# What a kitchen note is: a compilation of many dishes, one technique, or
# something to look up. How the notes library files a note, not a rule.
KITCHEN_NOTE_KINDS = {"compilation": "合輯", "technique": "技巧", "reference": "參考"}

# What one step of a method is. Only a `step` is numbered: an optional step
# may be skipped and a note is advice among the steps, so neither takes a
# number, and the page draws a note differently. The kind changes how a row
# is shown, which is why it is a fixed list rather than a 設定 vocabulary.
STEP_KINDS = {"step": "步驟", "optional": "可省略", "note": "備註"}

# Every closed list the frontend renders, with its display label, served by
# GET /api/vocabularies/fixed so no list is copied into a component.
FIXED_VOCABULARIES = {
    "preservation_methods": [{"value": m, "label": m} for m in PRESERVATION_METHODS],
    "preservation_states": [{"value": k, "label": v} for k, v in PRESERVATION_STATES.items()],
    "ratings": [{"value": r, "label": r} for r in RATINGS],
    "dish_kinds": [{"value": k, "label": v} for k, v in DISH_KINDS.items()],
    "kitchen_note_kinds": [{"value": k, "label": v} for k, v in KITCHEN_NOTE_KINDS.items()],
    "step_kinds": [{"value": k, "label": v} for k, v in STEP_KINDS.items()],
}
