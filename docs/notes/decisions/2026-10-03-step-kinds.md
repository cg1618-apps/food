# A step is a 步驟, a 可省略 or a 備註, and only a 步驟 is numbered

The owner wanted an optional step outside the count and a note to read
differently from a step. The number counts what a cook must do.

- **The number is counted where the steps are drawn**, never stored: a stored
  number would have to be renumbered on every reorder and kind change.
- **The kind is a closed list (`STEP_KINDS`)**, because each kind changes
  behaviour; see `2026-10-03-closed-lists-and-vocabularies.md`.
- **A note is a step row, not a separate list.** A note belongs at a point in
  the method - "the oil should be smoking before this" - so it needs the
  step's position, group and drag. A separate list would need its own position
  scheme interleaved with the steps'. `recipe.notes` remains for notes about
  the whole dish.
- **No step's kind is guessed from its text.** Reading step text to decide
  what it is would be a guess; the owner switches it.
