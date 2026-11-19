# An author is a library with pages

- **Per-entity pages** (`/authors`, `/authors/:id`, `/edit/authors/new|:id`),
  food's shape rather than `media`'s add / modify / delete hubs. An author
  has a gallery, links, 備註 and recipes - a page's worth - and every other
  library here is per entity.
- **One place for an author's information.** The recipe library filtered by
  an author is only a filtered list, and a source's author links to the
  author's page; a panel of the author's details above the filtered list would
  be a second rendering of one record, and the two would drift.
- **One editor: the author's form.** 設定's 作者 row is a plain vocabulary row
  whose 編輯 links to the form, which keeps the tab shaped like every other
  tab: the row still renames in place, and only the extra action is new.
- **Still on the vocabulary factory, with a router beside it.** Listing,
  creating, renaming and deleting stay the factory's, so the name rules, the
  order and the in-use 409 stay shared with the other vocabularies. What the
  factory has no shape for - one author read whole, its delete preview, its
  gallery PUT - is `app/routers/author.py`, under the same prefix. Rejected:
  **a second create / update / delete**, since two writers for one table is
  how their rules diverge; **widening the shared schemas** for `notes` and
  `links`, which would let the other vocabularies accept and silently drop
  them. The factory's `Shape` carries the author-only schemas and the
  computed list fields.
- **`recipe_count` beside `usage_count`.** The library shows recipes, and a
  recipe with two sources by one author is one recipe; the delete refusal
  counts sources, because each is a reference that would stop it. Both are
  true.
- **The library searches in the browser.** The author list is small and
  already cached by the recipe form and filter, so a `q` that only one
  vocabulary would use is not added to the factory.
