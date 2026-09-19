# Decisions

Why food is the way it is. Unlike the rest of `docs/`, this page is allowed to
talk about the past: it records what was chosen, what was rejected, and the
reasoning that is still load-bearing.

## Platform decisions this app inherits

Recorded in `cg1618-apps/platform` rather than here, and summarised only so far
as they bind this app:

- **It is its own repository**, sharing no code with the other applications. The
  platform connects them by configuration, not by git pointers.
- **It shares one PostgreSQL**, with its own database and its own role.
- **It is `public`**, because repository rulesets and environments with required
  reviewers are free only for public repositories, and both gates depend on it.
- **No `pull_request`-triggered job may run on the self-hosted runner.**

## Decisions for this application

- **FastAPI, PostgreSQL, React + Vite, Alembic** — the media tracker's stack.
  Rejected: Django, which would have suited a library-of-entities app well and
  cost far less code per app, but adds a second framework to hold in mind and a
  different deploy shape. Rejected: a server-rendered frontend with htmx, which
  would have removed the build step, the second dev port and the stale-bundle
  failure mode entirely — worth revisiting if the frontend turns out to be
  thin, and the reason it was not chosen is consistency with an app that
  already works rather than a technical defect.
- **Public to read, with writes behind Cloudflare Access on their own path
  prefix.** No accounts and no login: one user, and the reading half is meant to
  be openable on a phone without signing in. The write surface needs a gate
  regardless, and doing it at the edge means no password is stored and no auth
  code is written. This requires the URL layout to separate reads from writes
  from the first route, which is cheap now and invasive later.

## Structure

The application is eight modules, built in this order. Each is a separate piece
of work with its own design pass, done immediately before it is built rather
than now — a spec written months ahead describes a system that was imagined.

| | Module | Owns | Depends on |
| --- | --- | --- | --- |
| 1 | Ingredients | the library, selection and preservation notes | — |
| 2 | Recipes | recipes and general recipes, their lines, the nesting graph | 1 |
| 3 | 零食 | bought snacks, as a product catalogue | — |
| 4 | Kitchen inventory | what is in the house, and "what can I cook" | 1, 2 |
| 5 | Cooking schedule | what to cook when | 2 |
| 6 | Random picker | pick something, with filters | 2 |
| 7 | Shopping list | what to buy, manual and suggested | 1, 3, 4, 5 |
| 8 | Restaurants | the restaurant library | — |

### Entities

- **Ingredient** — names, aliases, selection notes, preservation notes, and a
  `needs_detail` flag set when the row is created as a stub.
- **Recipe** — names, aliases, steps, notes, and a `kind` separating a dish from
  a general base. Also a personal status: want to try, can cook, regular.
- **RecipeLine** — ordered, belongs to a recipe, points at **either an
  ingredient or another recipe**, carries a free-text amount and an optional
  section label ("for the sauce").
- **InventoryItem** — one per ingredient: `in_stock`, `is_staple`, a free-text
  quantity, notes, an optional use-by date.
- **Snack** — names, brand, category, the nutrition printed on the package,
  where it was bought, rating, notes.
- **ScheduledCook** — a date, a recipe, notes.
- **ShoppingItem** — links an ingredient or a snack, or is free text; free-text
  quantity, a `bought` flag, and where the suggestion came from.

### The decisions behind that shape

- **A recipe line links a real ingredient row and carries its amount as text.**
  Structured links are what make "what can I cook", "what uses this" and the
  shopping list possible at all. Free-text amounts are what stop the app
  refusing "a splash" — and unit normalisation buys only recipe scaling, which
  is not wanted. Rejected: fully structured quantity and unit, which turns
  every recipe entry into a data-entry chore; rejected: free-text lines with no
  links, which would delete three of the modules above.
- **An ingredient typed into a recipe that does not exist yet is created as a
  stub.** Nothing interrupts writing a recipe to demand a preservation guide
  for garlic, and the library fills itself in as a by-product of use, rather
  than being a few hundred rows to type before the app is worth opening. The
  `needs_detail` flag is the to-do list.
- **Ingredients carry aliases, and this is load-bearing rather than a nicety.**
  Stubs are created by typing a name, so without aliases `spring onion`,
  `scallion` and `青蔥` become three rows that should be one. With them,
  merging is a rename.
- **One recipe entity, not two.** A general recipe is a recipe whose `kind`
  says so; it can be cooked alone and appear as a line inside others. The graph
  needs a cycle guard, and "what can I cook" resolves *through* a nested recipe
  rather than treating it as an opaque item. Rejected: a separate table for
  bases, which would duplicate ingredients, steps and notes.
- **Inventory is presence, not stock.** `in_stock` with a free-text quantity and
  notes. Rejected: quantities decremented as you cook, which demands that every
  meal, snack and spill be recorded or the numbers silently stop being true —
  the feature most likely to be abandoned, taking the app's credibility with
  it. The accepted consequence: "what can I cook" answers on presence and will
  never say "not enough flour".
- **A row that runs out stays, marked out of stock**, with a `is_staple` marker
  for the things always kept. That is what feeds the shopping list, and it
  preserves the notes written about an item instead of losing them each time
  the jar empties.
- **零食 is a product catalogue, not a kind of recipe.** These are bought:
  what matters is the brand, the nutrition printed on the package and what you
  thought of it. Modelling them as recipes would give every recipe nullable
  nutrition fields that only one kind of row ever uses, and an ingredient list
  nobody can fill in.
- **"What we can cook" is a status on a recipe, not a module.** A separate
  table would be a copy of recipes.
- **"What can I cook" ranks rather than filters** — ordered by how many lines
  are unavailable, so "missing one thing" stays visible. A strict list is
  almost always empty, and an empty screen stops being opened.
- **The shopping list is a real module, not a derived view.** It holds manual
  items, it tracks what has already been picked up, and it absorbs suggestions
  from two places: staples that are out of stock, and ingredients missing from
  what is scheduled.

### Naming, across every entity here

`name_cn`, `name_en`, `aliases[]`, with `name_cn` as the display default, and
search matching all three. This is a platform-wide convention rather than a
food one — `travel` and `art` use it too.

### Out of scope, deliberately

Nutrition on cooked recipes. Cooking history and analytics. Anything
multi-user.

### Image storage

Dishes, ingredients and snack packages all want photographs, and `art` needs
uploads too. That makes it a platform question rather than a food one: a
bind-mounted directory outside the container image, and backup coverage, are
both things the media tracker already has and the platform has not yet
generalised. Recorded in the platform's Step 4 plan; nothing here invents its
own answer.

The constraint worth carrying: a photograph of a dish you cooked cannot be
re-fetched from anywhere, unlike a cover image an API can supply again.
