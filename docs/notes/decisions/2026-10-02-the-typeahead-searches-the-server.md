# The typeahead searches the server and is driven from the keyboard

A divergence from `media`, whose `ComboBox` filters a list it was handed and
handles only Escape and Tab.

- **Server search.** A recipe line may name any ingredient or any dish, so
  handing the box a list would download both libraries for every line; the
  list endpoints' `q` already matches every name slot and alias. A small list
  already loaded for other reasons (authors) is filtered in the browser by the
  same component, through `items`, so every pick-one box still behaves one
  way.
- **The keyboard.** Arrow keys and Enter are what make filling twenty lines
  bearable, and Enter must never submit the form, so the box owns it.
- **「新增」 only when nothing matches exactly**, where media's CastEditor
  always offers "create new". There a create is a plain insert that would
  split one character into two; here the server folds a name it already knows
  into the existing row, so the option is shown only when it can mean
  something new.
