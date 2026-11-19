# To do next

Decided work nobody has started, in the order it is to be built. No status,
no claiming: work starts by cutting a branch, and an item is deleted in the
change that builds it. Each module gets its own design pass immediately before
it is built, not earlier - a spec written months ahead describes a system that
was imagined.

1. **零食** - bought snacks, as a product catalogue: names, brand, category,
   the nutrition printed on the package, where it was bought, rating, notes.
   Depends on nothing. Design:
   `notes/decisions/2026-09-19-snacks-are-a-product-catalogue.md`.
2. **Kitchen inventory** - what is in the house, one row per ingredient
   (`in_stock`, `is_staple`, a free-text quantity, notes, an optional use-by
   date), and "what can I cook". Depends on ingredients and recipes. Design:
   `notes/decisions/2026-09-19-inventory-is-presence-not-stock.md` and
   `notes/decisions/2026-09-19-what-can-i-cook.md`.
3. **Random picker** - pick something to cook, with filters. Depends on
   recipes.
4. **Shopping list** - what to buy, manual and suggested: an item links an
   ingredient or a snack, or is free text, with a free-text quantity, a
   `bought` flag and where the suggestion came from. Depends on ingredients,
   零食, the inventory and the schedule. Design:
   `notes/decisions/2026-09-19-the-shopping-list-is-a-module.md`.
5. **Restaurants** - the restaurant library. Depends on nothing.
