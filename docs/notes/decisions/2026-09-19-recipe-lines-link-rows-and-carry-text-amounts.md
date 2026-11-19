# A recipe line links a real row and carries its amount as text

Structured links are what make "what can I cook", "what uses this" and the
shopping list possible at all. Free-text amounts are what stop the app
refusing "a splash"; unit normalisation would buy only recipe scaling, which is
not wanted.

Rejected:

- **Fully structured quantity and unit**, which turns every recipe entry into
  a data-entry chore.
- **Free-text lines with no links**, which would delete three of the planned
  modules.

Two things follow, and both are load-bearing:

- **A name typed into a recipe that matches nothing becomes a stub
  ingredient.** Nothing interrupts writing a recipe to demand a preservation
  guide for garlic; the library fills itself in as a by-product of use, and
  `needs_detail` is the to-do list.
- **Ingredients carry aliases.** Stubs are created by typing a name, so
  without aliases `spring onion`, `scallion` and `青蔥` become three rows that
  should be one. With them, merging is a rename.
