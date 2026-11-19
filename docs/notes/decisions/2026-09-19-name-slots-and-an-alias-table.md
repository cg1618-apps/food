# Three name slots plus an alias table

A divergence from `media`, which has four fixed slots (`en`/`cn`/`jp`/`alt`)
and uses a child table only for names from external sources. food's names are
`name_cn`, `name_en` and, where a formal alternative is worth showing,
`name_alt`; everything else anyone might type is an alias, user-typed and
unbounded, which fixed slots cannot hold.

**Aliases are a child table, never an array column.** An array cannot be
indexed, joined or constrained, and `media` records replacing list-in-a-column
with a real table twice as a regret.

**`name_alt` and an alias are different things**, or they end up holding the
same strings: `name_alt` is a formal name in another script or romanisation,
and is shown; an alias is anything you might type to find the row, and is
never shown. `docs/data-model.md` has the columns.
