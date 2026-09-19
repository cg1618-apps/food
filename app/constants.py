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
