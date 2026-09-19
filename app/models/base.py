"""The display-name rule, in one place, for every named row in this app.

`name_cn` leads. That is food's rule and it is NOT media's - media's catalogue
entities lead with English and carry a per-row `display_name_field` column
naming the winner. Both differences are deliberate and recorded in
`docs/notes/decisions.md`: one user reading Chinese first, and a rule you can
state in a sentence beats a column every row has to fill in.

There is no override column, so display order cannot be varied per row. If that
is ever wanted, it is a column plus a fallback - not a special case here.
"""


class NameFallbackMixin:
    """`display_name` and `all_names` for a row with the name slots.

    `name_alt` is read with `getattr` because not every named table has one -
    a label has two slots, an ingredient has three - and a mixin that demanded
    all three would push an unused column onto the smaller tables purely to
    satisfy this file.
    """

    @property
    def display_name(self) -> str:
        """The first name slot that holds something, in food's fixed order.

        Returns "" rather than None when every slot is empty, so a caller can
        sort and compare without a null check. The database forbids that state
        - `ck_<table>_has_a_name` - but this property also runs against rows
        that have not been flushed yet, where the constraint has not been
        consulted.
        """
        for value in (self.name_cn, self.name_en, getattr(self, "name_alt", None)):
            if value and value.strip():
                return value
        return ""

    def all_names(self) -> list[str]:
        """Every non-empty name slot, for search and duplicate warnings.

        Aliases are deliberately NOT included: they live in their own table and
        a caller that wants them has to join, rather than getting them here by
        accident and issuing a query per row.
        """
        slots = (self.name_cn, self.name_en, getattr(self, "name_alt", None))
        return [v for v in slots if v and v.strip()]
