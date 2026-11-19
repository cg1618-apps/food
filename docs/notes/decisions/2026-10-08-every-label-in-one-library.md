# A label belongs to exactly one library

**Ingredient, dish or note.** What a tag says depends on what it is on: one
shared vocabulary made every form and sidebar offer every label (an ingredient
form offering 下飯) and gave a label three counts meaning different things. So
two libraries wanting 辣 have a 辣 each, and names are unique per scope.
Recipes show their dish's labels rather than being a fourth scope.

- **A `String` scope plus `LABEL_SCOPES`, not an enum and not three tables.**
  Three tables would have the database enforce the split at the cost of three
  copies of every label route, form and editor for one concept.
- **The API, not the database, keeps a link inside its scope.** A composite
  foreign key would make a wrong-scope link unrepresentable, but costs four
  columns and four constraints to guard two code paths. Every write linking a
  label goes through `services/lookup.fetch_labels` or `check_label_scope`, and
  a label in use cannot change scope, so no route can produce one.
- **A move is refused while the label is in use**, rather than detaching it.
  Moving would leave owners carrying another library's label or silently strip
  it; deleting is the explicit way to strip a label, and it says how many
  things it is on first.
