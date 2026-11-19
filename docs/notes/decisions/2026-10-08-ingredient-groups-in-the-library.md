# Ingredient groups in the library: the filter is the API's, the arrangement the page's

- **The group filter is the API's.** Choosing 雞肉 in the tree lists 雞肉 and
  everything below it at any depth - a recursive query over `parent_id`
  (`group_id` on `GET /api/ingredients`) - so the count, the search and the
  other filters compose with it. Sectioning and nesting the result is
  presentation, in `lib/ingredientGroups.js`, so the API's list stays one
  flat, sorted shape that the typeahead also reads.
- **What makes a row a group is read from the whole library**, not the
  result: read from the result, 只看主項 would empty every group.
- **A variety stays in its parent's block**, even when filed in another
  category (乾辣椒 is 乾貨, 辣椒 is 蔬菜), and names its own category there;
  splitting the block across sections would undo it.
- **A category filter includes its sub-categories**, because ingredients are
  filed into sub-categories (肉類 › 雞肉): an exact filter shows a parent as
  empty. The sidebar's count is the subtree total from the same tree, so the
  number and the list cannot disagree. `ingredient_count` on the tree stays
  the node's own, since that is what the delete refusal is about. Every caller
  wants the subtree, so there is no second, exact parameter.
- **品種 is 全部 / 只看主項.** 只看品種 was removed at the owner's request;
  `has_parent=true` stays in the API, since it costs nothing and the read API
  is public.
