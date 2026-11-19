# A dish and its recipes

**A recipe is one way of making a dish.** In the owner's words, "a recipe will
have its specific recipe item, the dish group which can have multiple specific
recipe belongs to it." 照燒雞腿排 by one author and by another are two recipes
of one dish. So the dish holds what is true whoever cooks it - names and
aliases, kind, course, region, labels, serves-as, a description, a gallery -
and the recipe holds what one way of making it needs. A recipe's own `name` is
optional and says how it differs; its display name falls back to the dish's.

Rejected:

- **Keeping the dish implicit in a shared recipe name**, which gives labels,
  course and search nowhere single to live.
- **A one-level version tree (另一版)**, one recipe the original and the rest
  hanging off it. It is a weaker form of the same grouping, and the family has
  no row of its own to carry what the versions share. A dish's recipes are its
  versions, all equal.

**A sauce is a dish, not a second entity.** One table for 料理 and 醬料, with a
`kind`: they carry the same fields at the same level, and a 醬料 library is a
filter of the same rows, not a migration. A sauce can be cooked alone and
appear inside other recipes, so the nesting graph needs a cycle guard and
"what can I cook" resolves through it. Rejected: a separate table for sauces
or for "general recipes", which would duplicate every name, alias, label,
gallery and step rule and make a line's target two columns. `kind` is how the
library files a dish, not a permission: a line may name a `dish` as well as a
`sauce` (rice under a curry).

**A recipe line names a dish, not a recipe.** You use 照燒醬, however it is
made: which recipe you follow is chosen at the stove. A sauce's recipe can
change, or a better one be added, without touching the recipes that use it,
and deleting a recipe never breaks a line - so nothing refuses a recipe's
delete. A recipe may not name its own dish.

**A dish outlives its last recipe.** A dish with no recipe yet is a real state
- one you mean to find a recipe for - and deleting it is a separate decision.

**Dish names are not unique**: two unrelated dishes may share a name.

**The recipe library has no filter by dish**, at the owner's request: a dish's
own page already lists its recipes. The API's `dish_id` filter stays, since it
costs nothing and the read API is public.
