# The weekly schedule is shaped by the owner's sheet

The plan was a `ScheduledCook` row - a date, a recipe, notes. The owner's Plan
sheet is a different thing, and the sheet is what is actually used, so the
tables hold its columns: per day, what to buy, what to take out of the freezer
morning, noon and evening, four meals (早, 中, 下午, 晚), the fruit and a note.

- **A meal is free text plus any number of items**, each a dish and
  optionally one of its recipes. A meal is not always a recipe ("外食",
  "吐司"), and a dinner is often more than one dish. The same dish and recipe
  twice in one meal says nothing new and is refused rather than silently
  merged.
- **The four marks are booleans, shown only when true.** 要買? and the 退冰?
  columns answer yes or no; what to buy or thaw belongs in 備註 or the meal. A
  column of 「否」 would bury the few days that need doing.
- **The columns are not the sheet's order.** The owner asked for the meals
  first - they are what the page is read for - then the fruit, the marks
  together, and the note last; every view follows that one order.
- **Weeks run Saturday to Friday**, as the sheet's do, two to a page. `?week=`
  is the Saturday, so a week is a link.
- **One row per meal slot**, keyed by `(date, slot)`, rather than four column
  groups on the day: the rules about a meal are stated once, and a fifth slot
  is a constant, not a migration.
- **The date is the key**, not a surrogate id: one day per date by
  definition. A date with nothing planned has no row, and a save that empties
  a day deletes it.
- **A recipe implies its dish**, and a recipe of another dish is a 422. The
  edit page picks the dish by search and the recipe from that dish's recipes,
  which cannot produce the mismatch; a search over every recipe would have
  needed the dish filled back in.
- **The dish is `RESTRICT`, the recipe `SET NULL`.** A plan naming a dish
  should not lose it silently; a recipe is one way of making the dish, and
  deleting it leaves the item its dish.
- **A day is written whole**, one PUT replacing it, so clearing a field and
  leaving it out are the same.
- **Saved by a button, not on blur.** A phone does not reliably blur a field
  when the thumb taps elsewhere, and a save that silently did not happen is
  the one failure the page must not have.
- **Dates are local calendar dates, with no zone.** The box and the owner are
  both in Asia/Taipei; the pages send the range from the browser's own date.
