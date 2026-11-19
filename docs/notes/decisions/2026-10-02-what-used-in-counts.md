# What "used in" counts, and how deep

"What uses this" counts **distinct recipes, not lines**, and states its depth
explicitly, because a one-level join and a recursive query look equally
correct in review and the wrong one under-counts silently.

- **An ingredient: all the way down its own tree, not at all through
  sub-dishes.** 生抽 in one line and 老抽 in another is one recipe using 醬油.
  It is one recursive CTE over `ingredient.parent_id` (UNION, so a cycle a
  hand-written UPDATE made ends the walk rather than hanging it), and it is
  the only definition: the recipe list's `ingredient_id` filter, `used_in` and
  `used_in_count` all read it. Rejected: a Python walk over a fetched parent
  map for the counts, which would be a second implementation to drift.
- **A dish: depth zero through sub-dishes.** A recipe using a sauce whose
  recipe uses this sauce is not listed. The ingredient takes the same depth
  through sub-dishes, so the two cannot disagree about what "uses" means.
- **An alternative counts.** A recipe that could be made with 雞胸肉 uses
  雞胸肉 - deleting it would take something from that recipe - so "used in",
  the recipe filter and both delete refusals count alternatives, at the same
  depths. `alternative_only` marks a recipe that names the row only that way,
  so the page says 替代 rather than imply the recipe needs it.
- **The delete refusal is direct lines only.** It is the foreign key's
  question, and a parent whose child a recipe names is already refused for
  having a child.
