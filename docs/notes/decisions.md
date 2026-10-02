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
- **An id inside a request body that names no row is 422, everywhere; a
  missing row named by the URL is 404.** Owner decision, 2026-10-02. The URL
  resolved, so the resource exists; it is the payload that is wrong. This
  covers a parent, a label, a cooking method, a course, a version's original,
  a line's ingredient or sub-recipe, and a gallery's `image_id` - the last
  was 404 until recipes added a third case and one convention had to cover
  all of them. The detail names the id. Rejected: 404 for body ids, which
  reads as "the thing you addressed is gone" when the thing addressed is
  fine.

## The skeleton

Copied from `travel`, which is live, rather than designed again. The two apps
share a stack by decision, so the parts that are not about food — the config
object, the session factory, the SPA catch-all, the Alembic wiring, the
dockerfile's three stages, the deploy hook — are travel's, adapted only where
this app's registry entry differs.

What differs, and why:

- **Ports 8001 and 5174.** The uvicorn port is food's entry in the platform's
  `apps.yml`; the Vite port is `5173 + (port - 8000)`, which is the box-wide
  rule that lets all four apps run on one laptop at once. `strictPort` is set
  so a taken port aborts rather than silently moving the dev server somewhere
  the proxy is not pointed.
- **The health path is `/health`, not `/api/health`.** `apps.yml` declares it,
  and the deploy pipeline reads the declaration rather than the code. The
  consequence reaches three files: the SPA catch-all has to refuse `/health/…`
  as well as `/api/…`, or a typo in the probe's path answers 200 with the
  bundle and a dead app is called healthy; Vite proxies `/health` as well as
  `/api`; and the compose healthcheck probes `:8001/health`.
- **Writes are split from reads by path**, as this file required before the
  first route existed: `/api/...` public, `/api/edit/...` behind Cloudflare
  Access. `WRITE_PREFIX` in `app/routing.py` is the single definition,
  `deploy/gated-paths` is generated from it, and the platform's `apps.yml`
  carries `gated_paths` checked against that file in both directions.

Two things the skeleton pins that cost travel a production failure each, kept
deliberately rather than inherited by accident:

- **`deploy/migrations current` answers `base` when there is no
  `alembic_version` table.** That is not an error state; it is every app's
  first deploy, and erroring there refuses the deploy that would create the
  schema. Travel's first deploy died exactly there.
- **`deploy/migrations` is mode `100755` in the commit, and `.gitattributes`
  pins it to LF.** `core.fileMode` is false on both development machines, so
  the bit is never picked up from disk; `git ls-files` reads the index and has
  reported the wrong answer, so CI asserts it with `git ls-tree HEAD`. A CRLF
  in the file fails on the box as `bad interpreter`, naming the shell rather
  than the line endings.

## The catch-all serves real files, the way `media` does

The SPA catch-all inherited from the skeleton answered **every** non-API path
with `index.html`. That is correct for a client route and wrong for a file that
actually exists in the bundle: `/favicon.svg` came back as the SPA's HTML under
`text/html`, and the browser discarded it. Only `/assets` was mounted as
`StaticFiles`, and Vite copies `frontend/public/` to the **root** of the bundle,
not into `assets/` — so nothing served it. Nothing sits in front of this app
either; cloudflared connects straight to uvicorn, so there was no proxy to cover
the gap. The icon shipped in the repository and had never been served.

**The fix is `media`'s resolve-and-confine block, adopted rather than
redesigned**, per the platform's house-style rule that `media` is where a
convention is looked up. The handler resolves `dist / full_path`, and serves it
only when it is inside the dist directory, is not the directory itself, and is a
real file; otherwise it falls back to `index.html`.

Rejected: **special-casing the icon paths** — a list of `/favicon.svg`,
`/favicon.ico`, `/robots.txt` and whatever comes next. It is shorter today and
it is a list somebody has to remember to extend, with the same silent failure
each time a file is added to `frontend/public/`. Rejected: **mounting the whole
dist as `StaticFiles` with `html=True`**, which would serve the files but hand
the client-route fallback to Starlette, and with it the `/api` and `/health`
404 guards this app cannot give up.

**The `.resolve()` + `is_relative_to()` + `is_file()` guard is load-bearing
security, not tidiness.** `full_path` is user-controlled, and without the
confinement `/..%2F.env` reads the app's own credentials from beside the bundle.
`tests/test_spa_routing.py` asserts both halves — that a real file in the bundle
is served as itself, and that a traversal attempt is not — and the `.env` file
its traversal test writes is load-bearing: `is_file()` is False for a path that
does not exist, so without a real secret to leak the test would pass against an
unguarded handler.

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

- **Ingredient** — built. `docs/data-model.md` is the description, and this
  list does not repeat it: a second copy of a settled claim is the one that
  goes stale, because nobody is looking at it.
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
  bases, which would duplicate ingredients, steps and notes. A line may nest a
  `dish` as well as a `base`: `kind` is how the library files a recipe, not a
  permission, and a dish served inside another (rice under a curry) is real.
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

`name_cn`, `name_en` and — where a formal alternative is worth showing —
`name_alt`, with `name_cn` as the display default and search matching all of
them. `name_cn` leading is a platform-wide convention rather than a food one;
`travel` and `art` use it too.

**Aliases are a child table, not an array column.** This line previously said
`aliases[]`, which was never buildable as written: media carries no
`postgresql.ARRAY` anywhere and records replacing list-in-a-column with a real
table twice as a regret, because such a column cannot be indexed, joined or
constrained. `ingredient_alias` is all three. The *concept* is unchanged — an
unlimited list of things you might type — only its storage.

**`name_alt` and an alias are different things**, and without a rule they end
up holding the same strings. `name_alt` is a formal name in another script or
romanisation, and is shown; an alias is anything you might type to find the
row, and is never shown.

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

## Where food diverges from `media`, and why

The platform's house-style section makes `media` the reference implementation
for conventions, and says a deliberate divergence belongs here with its reason
so a later reader can tell a decision from an accident. These are food's.

- **An integer primary key**, where media has a `system_id` UUID join key plus
  a short `public_id` from a per-table sequence under a deferrable unique
  constraint. That machinery exists to let media's Google Sheets restore
  permute ids inside one transaction. food has no such channel, so it would be
  two ids and a sequence serving nothing.
- **Reads and writes split by path prefix**, where media splits them by a
  comment banner and an auth dependency inside one router file. food has no
  auth code at all: the gate is Cloudflare Access, which is all-or-nothing per
  path, so the split has to be in the URL or there is no gate.
- **Three name slots plus an alias table**, where media has four fixed slots
  (`en`/`cn`/`jp`/`alt`) and uses a child table only for external-source names.
  food's aliases are user-typed and unbounded, which fixed slots cannot hold.
- **`name_cn` leads display, with no per-row override column.** Media's
  catalogue entities lead with English and carry a `display_name_field` naming
  the winner. One user reading Chinese first, and a rule statable in a sentence
  beats a column every row has to fill in.
- **`PATCH` takes an all-optional Pydantic model with `exclude_unset` and
  `extra="forbid"`**, where media takes a raw `dict` through a shared helper
  that ignores unknown keys. Media's shape is load-bearing there for reasons
  that do not exist here — association proxies onto a parent row, and 17
  heterogeneous endpoints — and `extra="forbid"` additionally rejects
  server-owned columns loudly rather than dropping them silently. "Conventional
  beats clever" is the tiebreak.

### The one that is not a divergence but reads like one

**Single-column unique name indexes use Postgres's DEFAULT null handling, not
`NULLS NOT DISTINCT`.** Media's scar is real — `uq_person_name` spans several
name columns, and there a NULL in any of them makes the whole constraint inert,
which shipped duplicates three times. Carrying that fix to a *single-column*
index inverts it: `NULLS NOT DISTINCT` makes NULL equal NULL, so the table may
hold exactly one row with that slot empty. Most ingredients here have only a
Chinese name, so the second one inserted would be refused.

It was written that way first and the model tests caught it immediately.
`test_any_number_of_ingredients_may_leave_a_name_slot_empty` is what refuses
the change if someone applies the lesson again.

## Storage ranges, heating, images

What the branch after module 1 chose, and what it turned down.

- **A storage time is a range, which reverses module 1.** Module 1 held one
  typical integer and said a range goes in `notes`, so a future "what is about
  to go off" view would have a number to compute with. The owner's reference
  sheets state a range in almost every row, so a single number would have been
  invented, and a view that computed with it would have been computing with
  something nobody said. Both ends are optional, so "up to 3 days" and "see the
  date" are representable without a sentinel. The cost is that the computable
  number is now a choice the view makes (the maximum, the minimum or the
  midpoint) rather than one the data made. `fridge` on the list summary
  returns both ends and leaves that choice to the caller.
- **Storage gained a state, and the unique key gained it with it.** The sheets
  separate unused from opened, and a cooked row is a different thing again, so
  the key is `(ingredient_id, state, method)`. Rejected: encoding the state in
  `notes`, which is the same mistake as encoding the range there.
- **Heating stores Celsius only.** Fahrenheit is computed in the response. Two
  stored temperatures can disagree and one cannot.
- **A gallery table per owner type, not media's polymorphic table.** Media has
  one attachment table keyed by `owner_type` and `owner_id`, which nothing
  constrains, and records that nothing stops an attachment outliving its owner.
  food has three owner types, so three small tables with real foreign keys
  remove the whole class at the price of one shared module's worth of
  repetition. `images.OWNER_TABLES` is the one list the library's usage counts
  and owner listings read. The owner side cascades and the image side
  restricts, so deleting an owner removes its gallery and never a picture, and
  a picture still shown somewhere cannot be deleted.
- **The upload pipeline is media's, plus two additions.** The re-encode to JPEG
  is media's security control and is kept. Added: the EXIF orientation is
  applied first, because the re-encode drops the tag and portrait phone photos
  would otherwise be stored sideways; and a 50 megapixel ceiling, so a small PNG
  declaring 30000 by 30000 pixels is a 422 and not a worker eating memory. Both
  are tested.
- **`IMAGE_DIR` is a setting, read from `settings` at call time.** Media binds
  its directory at import, which is why patching it in a test does nothing
  there. Reading it at call time is what lets a test point it at a temporary
  directory. The `/images` mount is the exception: it is built with the app, so
  the test client builds the app after the directory is set.
- **The seeds live in a migration, with `ON CONFLICT DO NOTHING`.** A
  production database receives the starting vocabulary on deploy with nobody on
  the box, and a development database gets it from `alembic upgrade head` rather
  than a script someone forgets. `DO NOTHING` is what lets it land on a database
  where the owner already typed 肉類 or 飯, keeping their row as it is.
  Rejected: a separate seed script, which two machines and a box would each have
  to remember to run.
- **The `v1ocabulary` downgrade is best-effort.** It deletes only seeded rows
  that nothing references, identifying them by name, so an unreferenced row the
  owner created with a seeded name goes too. A marker column on every row for a
  downgrade nobody expects to run was the alternative, and was not worth it.
- **The `i2storage` downgrade is lossy, deliberately.** The old key
  `(ingredient_id, method)` cannot hold two states, so rows in any state but
  `unused` are deleted, and the range collapses to its maximum, or its minimum
  when there is no maximum. The alternative was to refuse to downgrade, which
  makes the rollback tooling's contract false. A scratch-database test asserts
  what survives. `m1images` is the opposite case: its downgrade drops the
  tables and leaves the files under `IMAGE_DIR` alone, because a migration has
  no business deleting the only copy of a photograph.
- **A repeated `PATCH` of aliases and storage rows is reconciled, not
  replaced.** Module 1 replaced the collection, and the unit of work `INSERT`s
  before it `DELETE`s, so re-sending a row the ingredient already had collided
  with its own unique key and answered 409. Aliases are now matched by value and storage rows by
  `(state, method)`. Gallery replacement clears and flushes before it assigns,
  for the same reason.

## Recipes

- **Versions are one level deep, and an original's delete leaves them.** A
  version points at its original through `variant_of_id`; a version may not
  have versions, nor point at one, so a family is one original and its
  versions and `versions` on the response is a flat list. The foreign key is
  `SET NULL` rather than `RESTRICT` because each version is a complete recipe
  in its own right - refusing to delete an original until its versions went
  first would make the user destroy what they meant to keep. Rejected: a tree
  of versions, which nothing here would read and which needs a cycle guard of
  its own.
- **"Written up" is derived** - at least one line or step - and never stored.
  A stored flag disagrees with the content the first time somebody forgets to
  tick it.
- **A new ingredient typed into a line reuses an exact match.** Equal to a
  name slot or an alias, ignoring case, means the existing row; anything else
  is a stub in the fallback category with `needs_detail`. Names already
  resolved in the same save count, so one new name in two lines is one stub
  rather than a unique violation. A near match is not guessed at: the
  typeahead shows it before the user chooses "new", which is the one moment a
  person is there to decide.
- **"Used in" for a recipe is depth zero through sub-recipes.** A dish using a
  base that uses this base is not listed; only lines naming this recipe
  directly. An ingredient's "used in" takes the same depth through
  sub-recipes, so the two cannot disagree about what "uses" means.
- **"Used in" for an ingredient goes all the way DOWN its own tree and not at
  all through sub-recipes.** It counts distinct recipes with a line naming the
  ingredient or any ingredient below it, so 生抽 in one line and 老抽 in
  another is one recipe using 醬油. It is a recursive CTE over
  `ingredient.parent_id` (UNION, so a cycle a hand-written UPDATE made ends the
  walk rather than hanging it), and it is the only definition: the recipe
  list's `ingredient_id` filter, `used_in` and `used_in_count` all read it.
  The plan was a Python walk over a fetched parent map for the counts; one
  grouped query over the same CTE is as fixed in cost and leaves no second
  implementation to drift.
- **The delete refusal is direct lines only**, unlike "used in". It is the
  foreign key's question, and a parent whose child a recipe names is already
  refused for having a child.
- **Merge: the target wins.** Whatever only the source has moves - lines,
  children, links, heating, labels it lacked, images it lacked (after its
  own), preservation rows for a `(state, method)` it lacked, prose fields it
  left empty. Whatever collides is the target's and the source's is dropped,
  and the preview lists every drop. The source's name slots become aliases on
  the target, never names: the target's names are what the user chose to
  keep, and a second name_cn has nowhere to go. Category, parent, rating and
  `needs_detail` are not merged at all - each is one value, and the user is
  merging INTO the row whose values they want. The preview and the merge are
  one function's output, so the preview cannot describe a different merge
  from the one that runs. Merging into a descendant is refused, since the
  source's children would move under their own descendant. Moved links,
  heating and preservation rows are numbered after the target's own, so a
  merged list keeps the target's order and appends rather than tying.
- **A merge carries its preview's fingerprint, and a changed plan is a 409.**
  The preview and the merge being one function closes the gap between what
  the code shows and what it runs; it does not close the gap between what the
  user READ and what runs, because the preview can sit in a tab while the
  source is edited elsewhere. That is the stale-tab case `StaleCountError`
  guards on delete, and a merge is the more destructive of the two: it
  deletes a row too, and drops every colliding note and prose field with
  it. Counts were not enough - an edited note moves
  different content under the same count - so the fingerprint is a SHA-256 of
  the canonical JSON of the rows the plan moves and drops. The 409 carries
  the fresh preview so the dialog can redraw without a reload, as the stale
  delete carries `expected` and `actual`. Required rather than optional: an
  optional guard is one a client forgets.
- **A refused recipe save writes nothing**, because the service validates
  every name, id, version and cycle before its first write - the stubs - and
  touches the row only after them. Relying on the request's rollback alone
  would hold in production and not in a session that is never rolled back,
  which is where a half-written row would be noticed last.
- **The cycle guard walks the stored graph breadth first**, one query per
  level, refusing past `MAX_DEPTH` rather than stopping short - a walk that
  gave up early would let a cycle through. A recursive CTE would be one query
  instead of a few, for a graph a person builds by hand.
- **The rule that a body id naming nothing is 422 is one function,
  `services/lookup.fetch_all`.** It began private to the recipe service; kitchen
  notes needed the same rule for `label_ids`, and a second copy is how two
  owners come to word or order the refusal differently.

## Kitchen notes

- **A note has a title, not name slots.** It is a bookmark - a compilation, a
  technique video, a page - not a catalogue entity, and nothing will ever look
  one up by an English name it does not have. The title is not unique, and
  `ck_kitchen_note_has_a_title` refuses one that is blank once trimmed,
  because `NOT NULL` alone accepts "". Its `display_name` is the title, so an
  image's owner list reads it like any other owner.
- **A note delete takes no confirmation counts.** A recipe's delete echoes the
  aliases, sources, lines and steps the dialog showed, because those are
  content the user wrote. A note owns only label links and gallery rows:
  nothing the user would miss, and the pictures survive in the library. A
  count with nothing behind it would be a ritual, not a guard.
- **The list is newest first**, unlike the two name-sorted libraries. A note
  is saved in the moment and found again by when as often as by what; a title
  sort would bury the one just added among similarly-named compilations.
- **Search reads the title and the body.** A note's body is where the
  reason it was kept is written, which is the part worth finding it by.

## Rules with no referent yet

Written down where the next person will look rather than where they were
learned. Each is dormant today and goes live the moment food grows the feature
it is about — which is exactly when nobody will remember it.

- **A row-hiding filter belongs in SQL, not in Python after the page was
  cut.** food hides nothing today. The moment it has a discontinued ingredient
  or an archived recipe, filtering after `limit`/`offset` silently shortens
  pages and starts the next one in the wrong place. Media's version of this
  rule lives inside the function that implements it, so only someone already
  reading the visibility code can find it.
- **Hidden must be indistinguishable from missing** — 404 rather than 403 —
  so the status cannot be used to work out which ids name real rows. There is
  nothing to hide today and the rule would have no referent; it goes in with
  the first hiding flag, not before.
- **Whatever parameter drives filtering gets no default.** Media's own
  documentation says so and its entity routers gave one anyway, producing
  write responses whose counts disagree with a GET of the same object. A
  required parameter fails loudly; an optional one fails as a wrong number
  nobody notices.

## What module 1 hands module 2

- **A recipe line's discriminator resolves three ways** — ingredient, recipe,
  or neither — and "neither" is a 422, by the owner's ruling for module 2 that
  an id inside a body naming no row is 422 everywhere (module 1 handed over
  "404"; the URL resolved, the payload was wrong). The stored type comes from
  the row, never from the payload. Media shipped that corruption three times,
  and there an authorization helper was incidentally the only thing resolving
  a type from an id. food has no such helper, so nothing would catch it.
- **"What uses this ingredient" counts distinct recipes, not lines**, and must
  state its recursion depth explicitly. 生抽 in one line and 老抽 in another is
  one recipe using 醬油; a one-level join and a recursive CTE look equally
  correct in review, and the wrong one under-counts silently.
- **Stub creation files the new row in the fallback category** and sets
  `needs_detail`. Both already exist; module 2 only has to use them.
- **Merge is the fix for a duplicate, not delete.** Every catalogue entity in
  media has one, and deleting a duplicate instead is on its own list of
  mistakes. Module 1 adds nothing that makes merging hard: no name is copied
  into another table.
- **Whether a bought-and-makeable thing is one row or two** — caramel is an
  ingredient you can buy and a general recipe you can make. Module 1 adds no
  link column and assumes nothing either way.
