# A name is a category or an ingredient, never both

The rule of `2026-10-12-a-category-has-its-own-notes.md`, made hard: no
category's `name_cn` or `name_en` equals an ingredient's, trimmed and ignoring
case. Two rows called 雞肉, one in each table, would leave the library unable to
say which it is. No constraint can hold a rule across two tables, so
`app/services/category_clash.py` checks every write that sets a name.
`docs/api.md` and `docs/data-model.md` have the behaviour.

- **An ingredient taking a category's name converts the category, rather than
  being refused.** The clash almost always means the category was the mistake:
  雞肉 was made a category for 雞腿 and 雞胸肉, then turns out to be bought as
  itself. A refusal would leave the owner to re-file every member, re-parent
  each, move the child categories, copy the notes and delete the category,
  across several pages with the tree half-done between. So the save answers 409
  with a preview, and the same save sent back with the preview's fingerprint
  converts in one transaction - the merge's shape, for the merge's reasons.
  `category_clash` in the body is the data to act on, not an error code.
- **A category taking an ingredient's name is refused, with no offer.**
  Converting an ingredient into a category would throw away its storage notes,
  heating rows, pictures, labels and every line naming it. The rare real case
  is a rename of the ingredient first, which loses nothing.
- **Names only, not aliases or `name_alt`.** Neither is a claim about what the
  thing *is*; comparing them would refuse a category named 雞 because some
  ingredient answers to 雞 when typed.
- **Child categories move up, not into the ingredient**: an ingredient has no
  categories under it, and a child category is still a family.
- **One conversion converts exactly one category.** A name two categories
  answer to is refused; converting both would merge two families silently, and
  which is meant is the owner's to say.
- **A recipe line's new stub under a category's name is refused** (422).
  Stubs exist so that writing a recipe never stops for a taxonomy question,
  and a conversion dialog mid-recipe is exactly that question.
- **Only a save changing a name is checked**, so an unrelated save never trips
  over a clash older than the rule, and renaming surfaces it at the moment it
  is cheapest to fix.
