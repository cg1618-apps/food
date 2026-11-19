# "What can I cook" ranks, and the rules it is built on

These bind module 4 (kitchen inventory), which is not built yet. They are
written here because that is where the person building it will look.

- **"What we can cook" is a status on a recipe, not a module.** A separate
  table would be a copy of recipes; the recipe status vocabulary already
  carries it.
- **It ranks rather than filters**, ordered by how many lines are unavailable,
  so "missing one thing" stays visible. A strict list is almost always empty,
  and an empty screen stops being opened.
- **A line is covered when its target or any of its alternatives is
  available**, an ingredient counting as available through its varieties, as
  "used in" reads the tree. An alternative is a way of meeting the line, not a
  requirement of its own, so it never makes a line uncovered.
- **It resolves through a nested dish** rather than treating a sauce as an
  opaque item.
- **An ingredient with a homemade version is available when it is in stock OR
  its `homemade_dish_id` dish is cookable.** Answering on stock alone would
  rank a recipe as missing something the kitchen can make.
