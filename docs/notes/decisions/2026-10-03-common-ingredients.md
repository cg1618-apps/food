# 常用食材 is an ordered list of its own

- **A table of its own, not a flag or a label on the ingredient.** The chips
  are ordered - 蒜, 薑, 蔥 first because they are reached for first - and an
  order is a place in one list, not a property of one row. A boolean column
  would need a second column for the order; a label has no order at all and
  would put the chips among the tags filtered by. `ingredient_id` is the
  primary key, so an ingredient is listed once by schema.
- **The write replaces the whole structure in one `PUT`.** The server
  numbers it, so there is no `sort_order` arithmetic for the client to get
  wrong and no half-applied reorder when one of several PATCHes fails; a drag
  between groups changes two lists at once, which two calls could half-apply.
  The list is a dozen rows. A duplicate ingredient is refused rather than
  collapsed: a client that sends one twice has lost track of its own list.
  A rename passes through a placeholder name first, because the unique index
  on `lower(name)` is checked row by row and two groups swapping names would
  collide with themselves.
- **An ingredient deleted leaves the list (`CASCADE`), and a merge moves its
  chip** to the surviving row, outside the merge plan and its fingerprint: it
  moves no content the preview would need to warn about.
- **Groups of its own, not 材料分組.** The owner chose this. A 材料分組 says
  where a line sits in one recipe; a 常用食材 group only arranges shortcuts.
  Reusing it would tie the lists together - renaming 醬汁 would rename a chip
  heading - for a likeness that is only in the word.
- **未分組 is no group at all** (a null `group_id`), always first, and no
  heading shows until a group exists.
- **`SET NULL` from a group to its chips.** A chip is an ingredient the owner
  picked; the group is only a heading, so deleting it must never delete a
  chip, and `RESTRICT` would make a group with chips undeletable for no gain.
- **A tapped chip adds an ungrouped line and focuses the amount.** The chip
  cannot know which group is meant, and the ungrouped area is the one place
  every recipe has; the ingredient is chosen, so 份量 is the only thing left
  to type. **A used chip stays tappable**: the same ingredient on two lines is
  ordinary, so "used" is a mark, not a lock.
