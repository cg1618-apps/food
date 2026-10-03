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
  covers a parent, a label, a cooking method, a course, a region, a recipe's
  dish, a line's ingredient or dish, and a gallery's `image_id` - the last
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
- **Access gates the edit pages too, and the frontend sends the browser
  through the login itself.** With only `/api/edit` gated, 設定 opened signed
  out and its first save failed as "Failed to fetch": Access answered the
  background request with a redirect to its login on another origin, which a
  fetch cannot follow, so the app never even saw a status. Gating `/edit` puts
  the login in front of a page opened by URL. It cannot cover a page reached
  by a click inside the SPA, which never reaches Access, so the edit pages
  also probe `GET /api/edit/session` with `redirect: 'manual'` and, when
  signed out, navigate the whole window through it — a path Access already
  gates, so this works whether or not `/edit` is. Rejected: making every edit
  link a full document load (scattered across a dozen components, and still
  blind to a session that expires on an open page); reloading the page on a
  failed save (throws away the form being saved). The probe is not a route
  guard and does not contradict that rule: it renders the page whatever
  happens and refuses nothing.

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
- **Dish** — names, aliases, a `kind` separating a dish (料理) from a sauce
  (醬料), a course, a region, labels: what a dish is whoever cooks it. Built;
  see "A dish and its recipes" below.
- **Recipe** — one way of making a dish: steps, notes, sources, and a personal
  status: want to try, can cook, regular.
- **RecipeLine** — ordered, belongs to a recipe, points at **either an
  ingredient or a dish**, carries a free-text amount, and sits in a group or
  none ("for the sauce").
- **InventoryItem** — one per ingredient: `in_stock`, `is_staple`, a free-text
  quantity, notes, an optional use-by date.
- **Snack** — names, brand, category, the nutrition printed on the package,
  where it was bought, rating, notes.
- **Schedule** — built, and not the `ScheduledCook` this list once planned
  (a date, a recipe, notes); see "The weekly schedule" below.
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
- **A general recipe is not a second entity.** It began as a recipe whose
  `kind` was `base`; since `d1ishes` it is a dish whose `kind` is `sauce`, made
  by ordinary recipes, and a line names the dish. Either way one shape serves
  both: it can be cooked alone and appear as a line inside others, the graph
  needs a cycle guard, and "what can I cook" resolves *through* a nested dish
  rather than treating it as an opaque item. Rejected: a separate table for
  sauces, which would duplicate ingredients, steps and notes. A line may name
  a `dish` as well as a `sauce`: `kind` is how the library files it, not a
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

- **Library filters and the search term live in the URL query**, where
  media's `useLibraryState` holds them in component state. The spec needs a
  filtered view to be a link: the ingredient page links to
  `/ingredients?category=<id>`, and the first library ignored the query - a
  known defect that state cannot fix. A filter click pushes (Back undoes it);
  typing replaces, debounced, so a search is one history entry. media also
  filters a fully loaded list in the browser; food sends the filters to the
  list endpoint, which already takes them.
- **Filters in a sidebar on a desktop and a drawer on a phone**, where media
  draws an inline chip panel the list is pushed down by. food's libraries
  have up to eight filter groups and are used on a phone at the shop; a
  permanent column suits the desk, and the drawer (the shared `Dialog`, a
  bottom sheet on a phone) keeps the list on screen until it is asked for.
- **A bar fixed to the bottom of the screen on a phone**, where media's
  navigation folds below `lg` into a menu button that opens a full-screen
  drawer. media has a catalogue of sections and sub-pages to fold away;
  food has a handful of destinations - 料理 · 食譜 · 食材 · 筆記 · 排程 · TBD · 設定 -
  which fit in one row under a thumb, and the app is opened one-handed in a shop or at the
  stove, where a menu button and a drawer are two taps and a screen covered
  for every move. Pages are padded at the bottom so the bar never covers
  content.
- **The 封面 / 清單 choice is remembered per library**, where media's library
  view resets to the grid on every visit (only its dashboard remembers, in
  `lib/dashboardView.js`, whose shape food's `lib/libraryView.js` copies). The
  ingredient library is read as a table at a desk and as covers on a phone,
  and each device should keep its own.
- **A library table's name cell is a link**, where media makes the whole row
  clickable. A link opens in a new tab and is reached by Tab; a clickable row
  is neither.
- **A gallery, not one image per role.** media's `ImagePicker` holds a
  single picture for an owner's role and attaches it the moment it is picked.
  food's recipes, ingredients and notes each hold an ordered gallery whose
  first picture is the cover, so `GalleryPicker` is a list - several uploads at
  once, reorder, a focus per picture - and it attaches nothing itself: the form
  PUTs the whole gallery with its save, after the first save for a new owner.
  A cancelled form therefore leaves at most an unused picture in the library
  and changes no owner, where media's attach-on-pick changes the owner before
  Save is pressed.
- **The typeahead searches the server and is driven from the keyboard**, where
  media's `ComboBox` filters a list it was handed and handles only Escape and
  Tab. A recipe line may name any ingredient or any recipe, so handing the box
  a list means downloading both libraries for every line; the list endpoints'
  `q` already matches every name slot and alias. Arrow keys and Enter are what
  make filling twenty lines bearable, and Enter must never submit the form, so
  the box owns it. 「新增」 is offered only when nothing matches exactly, where
  media's CastEditor always offers "create new" beside the matches: there a
  create is a plain insert that would split one character into two, here the
  server folds a name it already knows into the existing ingredient, so the
  option is shown only when it can mean something new.
- **One delete dialog for every kind**, configured per kind
  (`lib/deleteTargets.js`), where media has a dialog per page. Every delete
  here has the same contract - cascade counts echoed back, `field`/`actual` on
  a stale 409, `used_in` on a refusal - so the differences are data, not code.
- **設定's tab is in the URL and the bar is ARIA tabs**, where media's admin
  pages hold the active tab in component state and mark it with
  `aria-current`. A tab in the URL can be linked to and survives a reload,
  which state cannot; food's library filters are in the URL for the same
  reason. The tab click **replaces** the history entry where a filter click
  pushes: a filtered list is a result you may want to come back to, a tab is a
  view of one page, and Back should leave 設定 rather than replay every tab
  opened on the way. `role="tablist"`/`"tab"`/`"tabpanel"` with the arrow
  keys is the standard pattern for a tab bar, which `aria-current` (a link in
  a set of links) is not. The look and the wrapping row are media's
  `AdminTabBar`'s.

### Reordering is a drag, as it now is in `media`

Every reorderable list - the form lists, the gallery, the ordered
vocabularies and the category tree - is reordered by dragging a handle, through
`components/ui/Sortable.jsx`, ported from media's. food first copied media's
earlier ▲ / ▼ buttons (◀ / ▶ in the gallery), on media's reasoning that two
buttons work on a phone, with a keyboard and with a screen reader; media then
replaced its own chevrons with drag, and food followed at the owner's request.

- **Drag rather than step buttons.** A button costs one click per place, so
  moving the twentieth step of a recipe to the top was nineteen clicks.
- **dnd-kit's pointer events rather than native HTML5 drag.** A native drag
  does nothing on a touch screen, and this app is used on a phone; it also
  swallows the mouse wheel on Windows, so a row could only be dropped
  somewhere already on screen.
- **The keyboard path stays.** Up / Down on a focused handle moves the row
  one place and focus follows it, so nothing the buttons did needs a pointer.
  It is also what the tests drive.
- **A move that saves at once freezes its list until it settles**, media's
  rule: 設定's reorders build their PATCHes from the order on screen, so a
  second drag sent before the first lands would be computed from a stale
  order.
- **The category tree became nested lists.** A drag needs each sibling group
  contiguous on screen, and dragging a parent should carry its children; the
  flat indented list could do neither.

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
  food has four owner types (ingredients, dishes, recipes, kitchen notes), so four small tables with real foreign keys
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

- **Versions (另一版) were one level deep, and are gone.** A version pointed
  at its original through `variant_of_id`, `SET NULL`, one level deep. Dishes
  replace them: the recipes of one dish are its versions, and `d1ishes`
  turned each version family into one dish ("A dish and its recipes",
  below).
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
- **"Used in" for a dish is depth zero through sub-dishes.** A recipe using a
  sauce whose recipe uses this sauce is not listed; only recipes with a line
  naming this dish directly. An ingredient's "used in" takes the same depth
  through sub-dishes, so the two cannot disagree about what "uses" means.
- **"Used in" for an ingredient goes all the way DOWN its own tree and not at
  all through sub-dishes.** It counts distinct recipes with a line naming the
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
  every id, the own-dish rule and the cycle before its first write - new
  dishes, stubs and authors - and
  touches the row only after them. Relying on the request's rollback alone
  would hold in production and not in a session that is never rolled back,
  which is where a half-written row would be noticed last.
- **The cycle guard walks the stored graph breadth first** - a graph of
  dishes, dish A using dish B when a recipe of A names B - one query per
  level, refusing past `MAX_DEPTH` rather than stopping short - a walk that
  gave up early would let a cycle through. A recursive CTE would be one query
  instead of a few, for a graph a person builds by hand.
- **The rule that a body id naming nothing is 422 is one function,
  `services/lookup.fetch_all`.** It began private to the recipe service; kitchen
  notes needed the same rule for `label_ids`, and a second copy is how two
  owners come to word or order the refusal differently.
- **A recipe's status and a source's platform are managed vocabularies, not
  constants.** They began as closed lists in `app/constants.py` - 想試 / 可煮
  / 常煮 and YouTube / Shorts / 網站 / 書 / 其他 - and the owner wants to edit
  them in 設定 as courses are edited: add 冷凍好 or IG, rename one, reorder.
  Nothing in the app branched on either value, which is the line between a
  closed list (the code's logic depends on it: storage state, dish kind)
  and a vocabulary (only displayed and filtered by). So they became
  `recipe_status` and `source_platform`, factory vocabularies like
  `recipe_course`, and `recipe.status_id` / `recipe_source.platform_id`
  foreign keys, `RESTRICT`, so a value in use refuses its delete with the
  usual 409 and count. `v2ocabulary` seeds both from the old lists in order
  and maps every stored string to its row.
- **A recipe created without a status gets the first in sort order**, the
  oldest among equals, and with no status at all the create is a 422 saying
  so. There is no server default because the first status is the owner's
  data: a column default would name an id that 設定 can reorder or delete.
  Rejected: making the status optional, which would leave every list and the
  status toggle a "none" case for a recipe that has simply not been touched;
  and a fixed "first status" flag, a second ordering beside `sort_order` for
  the owner to keep in step.
- **A platform's usage count is sources, not recipes.** The count is the rows
  that would stop the delete, as everywhere in the factory, so one recipe
  with two sources from one book counts twice.
- **A source's author is a managed vocabulary that grows from the form.**
  `recipe_source.creator` began as free text with a `datalist` of every
  distinct value, and the owner wants authors in 設定: renamed once rather
  than per source, and filtered by as a row rather than by an exact string,
  so 詹姆士 and a mistyped 詹姆斯 stop being two people. But an author, unlike
  a platform, is met while entering a recipe - a new channel is the usual
  case, not the exception - so stopping to visit 設定 first would be the
  friction that pushes the name into the title instead. So the source row
  picks from the list and offers 「新增 'xxx'」, and the save creates the
  author, exactly as a line creates a stub ingredient: `new_author`
  resolved after validation in the same transaction, a name the server
  already knows (either slot, ignoring case) reused rather than duplicated,
  one new name on two sources one author. Rejected: keeping free text with
  a derived author list (renaming would still be per source); and creating
  authors on blur from the form (a save that is then abandoned would leave
  authors nobody used).
- **Authors are listed by name, not by hand.** Every author is created with
  `sort_order` 0 and 設定 shows them as it shows labels, with no drag
  handle: dozens of names have no meaningful order but the alphabet, and the
  factory's (sort_order, name) order already gives it, so the factory needed
  no change. `author_id` is nullable - a source may have no author - and
  `RESTRICT`, so an author in use answers the factory's 409 with the sources
  counted, as a platform does.
- **The author box filters a list in the browser, and it is the Typeahead.**
  The ingredient typeahead asks the server because the libraries are too
  large to download per line; the authors list is small and is already
  fetched for 設定 and the library filter. Rather than a second component,
  the Typeahead takes `items` and filters them locally with the same
  keyboard, 「新增」 rule and `Picked` display, so every pick-one box in
  the app still behaves one way.
- **`a1uthors` files existing creators by the form's rule.** One author per
  distinct trimmed creator, compared lower-cased, the first source's spelling
  kept; a name with Han characters, kana or Hangul in `name_cn`, otherwise
  `name_en` - the rule `lib/recipeLines.js` applies to any typed name, copied
  into the migration because a revision imports nothing from the app.

### Line and step groups

- **Groups are real per-recipe rows, not a label on each row.** The first
  shape was a free-text `section` on every line and step, grouped by the page
  on equal text. That is a label, not a group: an empty group could not
  exist, renaming one meant editing every row, the order of groups was
  whatever order their first rows happened to be in, and 醬汁 and 醬汁 with a
  trailing space were two groups. `recipe_line_group` and
  `recipe_step_group` make the group the thing the rows point at - it has a
  position, may be empty, and is renamed once.
- **A group is a 設定 value or a one-off name, exactly one.** Most recipes
  reuse the same few groups (主料, 調味料 / 備料, 烹飪), which should be one
  tap and one spelling; a few need their own (漢堡醬, 醃料), which should not
  have to be added to 設定 first. One column each, a CHECK that exactly one is
  set, and a name matching a value stored as the value - so "the same group"
  has one representation and the uniques can refuse a recipe holding it
  twice.
- **Two lists, not one.** What groups ingredients (主料, 配料) is rarely what
  groups the method (備料, 烹飪, 醬汁 - where 醬汁 is a stage, not a pile of
  ingredients). One shared list would offer every step group under 材料 and
  every line group under 步驟.
- **A row's `group_id` is `SET NULL`, not `CASCADE`.** The save replaces
  everything anyway, so either would serve it; `SET NULL` says what the form
  says - a group going never takes its rows with it, they become ungrouped -
  so the model and 移除分組 agree, and a group deleted by any other path
  cannot quietly delete steps. `RESTRICT` would have made the save order
  carry the rule.
- **Positions run through the whole recipe, in display order.** Ungrouped
  rows first, then group by group. Keeping the per-recipe unique on position
  means `recipe.lines` and `recipe.steps` are still the whole list in reading
  order for every reader that does not care about groups - "written up", the
  delete counts, used-in, merge. (A step's number was its position plus one
  until step kinds; now only ordinary steps are counted.)
- **The wire keeps `lines` and `steps` as the ungrouped rows**, with
  `line_groups` and `step_groups` beside them carrying their own. Nesting
  every row in a group would have needed a synthetic "no group" group, which
  is a group the owner never made.
- **A PATCH replaces a pair together, and one half alone is a 422.**
  `lines` without `line_groups` would have to guess: keep the stored groups
  and their rows (so the recipe has lines the client did not send), or drop
  them (so a client that never heard of groups deletes rows it never saw).
  Refusing is the only answer that does not guess, and the form always sends
  every list anyway.
- **One drag system, extended.** Rows moving between groups is dnd-kit's
  multiple-containers shape; rather than a second component, `Sortable.jsx`
  grew a `SortableBoard` that the existing `SortableList` joins by naming its
  container, so every handle, its keyboard path and its focus rule stay one
  implementation. The keyboard crossing a group's edge is what makes moving
  between groups possible without a pointer - and what the tests drive.
- **`g1roups` keeps the old sections as groups.** Distinct non-blank sections,
  trimmed and compared lower-cased, in first-use order, become groups; one
  matching a seeded value's name becomes that value. Rows keep their relative
  order and are re-positioned ungrouped-first, which is also how the old page
  showed them.

### Step kinds

- **A step is a 步驟, a 可省略 or a 備註, and only a 步驟 is numbered.** The
  owner wanted an optional step to stand outside the count and a note to
  read differently from a step on the page. The number counts what a cook
  must do; an optional step or a note takes a place in the order and no
  number. So the number is counted where the steps are drawn - the page and
  the form, through every group - and never stored, since storing it would
  have to be renumbered on every reorder and kind change.
- **The kind is a fixed list (`STEP_KINDS`), not a 設定 vocabulary.** Each
  kind changes behaviour - whether the row is numbered, how it is drawn - so
  a kind the owner added in 設定 would have no behaviour to give it. It is a
  `String` validated by the API, as every closed list here is, not a
  Postgres enum.
- **A note is a step row, not a separate list.** A note belongs at a point in
  the method - "the oil should be smoking before this" - so it needs the
  step's position, its group and its drag, all of which a step row already
  has. A separate notes list would need its own position scheme interleaved
  with the steps'. The recipe's own 筆記 (`recipe.notes`) remains for notes
  about the whole dish.
- **`s1tepkinds` guesses nothing.** Every existing step becomes a `step`; a
  note written as a step stays a step until the owner switches it, because
  reading step text to decide what it is would be a guess.

### 常用食材

- **A table of its own, not a flag or a label on the ingredient.** The chips
  are ordered - the owner puts 蒜, 薑, 蔥 first because they are reached for
  first - and an order is a place in one list, not a property of one row. A
  boolean column would need a second column for the order and would scatter
  the list across the ingredient table; a label (常用) has no order at all and
  would also put the chips' list among the tags filtered by. `ingredient_id`
  is the primary key, so the schema itself says an ingredient is listed once.
- **The write replaces the whole list.** Add, remove and reorder are then one
  `PUT` each, carrying the list as it should be, and the server numbers it -
  there is no per-row `sort_order` arithmetic for the client to get wrong, as
  `lib/vocabulary.js`'s `reorderPatches` has to for the vocabularies, and no
  half-applied reorder when one of several PATCHes fails. The list is a dozen
  rows, so sending it whole costs nothing. A duplicate id is refused rather
  than collapsed: a client that sends one ingredient twice has lost track of
  its own list, and keeping the first would save an order nobody sent.
- **An ingredient deleted leaves the list (`CASCADE`), and a merge moves its
  entry.** A chip has no life without its ingredient, so a delete is not
  refused over it. A merge is the fix for a duplicate, so the chip follows the
  surviving row and keeps its place; when the target is already listed the
  source's chip is simply dropped. The move is outside the merge plan and its
  fingerprint: it moves no content the preview would need to warn about.
- **A tapped chip adds to the ungrouped lines and focuses the amount.** The
  chip cannot know which group the owner means, and the ungrouped area is the
  one place every recipe has; the line drags into a group afterwards like any
  other. The focus goes to 份量 because the ingredient is already chosen - the
  amount is the only thing left to type.
- **A used chip stays tappable.** The same ingredient on two lines (garlic in
  the sauce and again on top) is ordinary, so "used" is a mark, not a lock.

## A dish and its recipes

- **A recipe is a specific way of making a dish.** The owner's words: "a
  recipe will have its specific recipe item, the dish group which can have
  multiple specific recipe belongs to it." 照燒雞腿排 by one author and by
  another are two recipes of one dish. So the dish holds what is true of the
  dish whoever cooks it - its names and aliases, kind, course, region,
  labels, serves-as, a description, a gallery - and the recipe holds what one
  way of making it needs: sources, status, servings, time, lines, steps,
  methods, equipment, its own gallery and notes. A recipe's own `name` is
  optional and says how it differs; its display name falls back to the
  dish's. Rejected: keeping the dish implicit in a shared recipe name, which
  is what 另一版 approximated and which gives labels, course and search
  nowhere single to live.
- **One table for dishes and sauces, with a `kind`.** 料理 and 醬料 carry the
  same fields at the same level, and the libraries should be filterable by
  kind now and separable later - a 醬料 library is a filter of the same rows,
  not a migration. Rejected: two tables, which would duplicate every name,
  alias, label and gallery rule, and make a line's target two columns.
- **`kind` is a fixed list; 地區 is a 設定 vocabulary.** The code branches on
  kind - a dish typed into a recipe line is created a `sauce`, one typed as a
  recipe's own dish a `dish`, and a sauce carries a 醬料 chip - so it lives in
  `DISH_KINDS` with the other behavioural lists. Region is only displayed and
  filtered by, and the owner edits it, so it is `region`, a factory
  vocabulary like the course, seeded and hand-ordered.
- **另一版 is removed; dishes replace it.** A one-level version tree was a
  weaker form of the same grouping: one recipe was the original and the rest
  hung off it, and the family had no row of its own to carry what the
  versions shared. The dish's
  recipes are its versions, all equal, and 其他版本 on a recipe's page is the
  dish's other recipes.
- **A recipe line names a dish, not a recipe.** You use 照燒醬, however it is
  made: which recipe of the sauce you follow is a choice made at the stove,
  not part of the dish that uses it. Pointing at the dish means a sauce's
  recipe can change, or a better one be added, without touching the recipes
  that use it, and deleting a recipe never breaks a line - so nothing refuses
  a recipe's delete at all. A dish named by a line, or one with recipes, is
  what refuses its delete (`RESTRICT`, answered first with both lists). A
  recipe may not name its own dish, and the nesting graph is a graph of
  dishes; both rules need the recipe's row, so they are the write path's.
- **A dish outlives its last recipe.** Deleting a recipe never deletes its
  dish: a dish with no recipe yet is a real state - a dish you mean to find a
  recipe for - and deleting it is a separate decision on its own page.
- **A dish typed into a form is found by name before it is made.** The
  recipe form's 料理 picker and a line's 新增料理 send `new_dish`; a dish
  whose name slot or alias equals the typed name, ignoring case, is reused,
  kind and all, and names resolved earlier in the same save count, the
  recipe's own first. It is `new_ingredient`'s and `new_author`'s rule, for
  the same reason: the typeahead offers near matches while a person is there
  to choose, and the save only folds exact ones.
- **Dish names are not unique**, as recipe names were not: two unrelated
  recipes of one name became two dishes of one name in the migration, and a
  unique index would have refused it.
- **The migration groups by the version graph.** `d1ishes` takes each
  connected component of `variant_of_id` as one dish - the graph the owner
  had already drawn by hand. The root (no `variant_of_id`, the lowest id when
  there are several or a cycle) gives the dish its names, aliases, course,
  serves-as, description and kind (`base` renamed `sauce`); the labels are
  the union, since a label on any version was true of the dish. No text is
  lost silently: a version's own display name becomes its `name` when it
  differs from the dish's, and a differing description is appended to its
  notes after 「原簡介：」. What it does not carry - a version's aliases and
  other name slots - and what a downgrade cannot restore are in
  `docs/deployment.md`.
- **The dish form is `/edit/dishes/:id`**, the shape every other edit page
  has. The design named `/edit/dishes/:id/edit`; that path redirects, so a
  link written to the design still lands, and the house convention is the
  one a reader can guess.

## Recipe templates

- **What the owner asked for.** "We should be able to create template for
  recipe", and "when we add a new recipe, we could choose from blank,
  template, or another recipe." A template is for recipes only - it belongs
  to no dish, and starting from one picks no dish.
- **The body is one JSONB column, not tables mirroring the recipe's.** A
  template is a snapshot that is only ever read whole into a form and written
  whole from one: nothing filters, joins, counts or constrains by what is
  inside it. Mirroring `recipe_line`, `recipe_step`, both group tables and two
  link tables would be six tables and a second copy of the recipe write path
  for no query that needs them. This does not reopen the "no list in a
  column" rule (`ingredient_alias` and the media regret it records): that
  rule is about data something searches or joins on, and a template body is
  neither. If a template ever needs to be searched by ingredient, it becomes
  tables then.
- **The body is the recipe payload's own shapes**, validated by the recipe's
  own input models (`LineIn`, `LineGroupIn`, `StepIn`, `StepGroupIn`) and the
  recipe's group rules (`recipes.resolve_groups`), and read back in the recipe
  response's shapes. One vocabulary on the wire, so the form reads a template
  with the code that reads a recipe (`lib/recipeStructure.js`).
- **A template never creates rows.** `new_ingredient` and `new_dish` are a
  422 saying to pick an existing one: a template is applied to a form and
  nothing is saved until the recipe is, so a stub made by saving a template
  would be a row nobody asked for yet. The template form's line typeahead
  offers no 「新增」 for the same reason.
- **No foreign keys into the JSON; stale references are dropped on read and
  counted.** Refusing to delete an ingredient because a template names it
  would make a starting point block real data. The read leaves out a line
  whose ingredient or dish is gone, a method or a piece of equipment that is
  gone, and a group whose value is gone - its rows join the ungrouped ones, as
  removing a group in the form does - and answers `dropped` so the form can
  say so. The stored body is not rewritten on a read; a GET that writes would
  be a surprise, and the next save writes what the form holds anyway.
- **An ingredient merge rewrites template bodies.** A merge is the fix for a
  duplicate, so the duplicate's id must not turn into a dropped line in every
  template. It is not in the merge preview or its fingerprint, as the
  常用食材 move is not: a template is a starting point, not content the merge
  moves. A dish has no merge, so nothing rewrites dish ids.
- **Copying another recipe copies its structure and its notes, not what makes
  it that recipe.** Name, sources, status and pictures stay with the source;
  the copy starts on the first status like any new recipe. Its dish comes
  along - a copy is most often another way of making the same dish - unless
  `?dish=` (a dish page's 「＋ 新增食譜」) names one.
- **The choice is in the URL** (`?blank=1`, `?template=`, `?from=`), so the
  form opened on it survives a reload and Back returns to the question. The
  chooser shows whenever none is given, including from a dish page, whose
  `?dish=` rides along.
- **The 材料, 步驟 and 做法、器材 sections were extracted rather than
  duplicated**, so the template form and the recipe form cannot drift apart;
  the recipe form's behaviour and its tests are unchanged by the move.

## Kitchen notes

- **A note has a title, not name slots.** It is a bookmark - a compilation, a
  technique video, a page - not a catalogue entity, and nothing will ever look
  one up by an English name it does not have. The title is not unique, and
  `ck_kitchen_note_has_a_title` refuses one that is blank once trimmed,
  because `NOT NULL` alone accepts "". Its `display_name` is the title, so an
  image's owner list reads it like any other owner.
- **A note delete takes no confirmation counts.** A recipe's delete echoes the
  sources, lines and steps the dialog showed, because those are
  content the user wrote. A note owns only label links and gallery rows:
  nothing the user would miss, and the pictures survive in the library. A
  count with nothing behind it would be a ritual, not a guard.
- **The list is newest first**, unlike the name-sorted libraries. A note
  is saved in the moment and found again by when as often as by what; a title
  sort would bury the one just added among similarly-named compilations.
- **Search reads the title and the body.** A note's body is where the
  reason it was kept is written, which is the part worth finding it by.

## TBD

- **Standalone, on purpose.** The owner asked for "a page with links or
  text … pure notes", with no integration or relation to the rest of the
  app. So an entry references no ingredient, recipe, label or image, and
  nothing references it: it is somewhere to drop a thing before deciding what
  it is, and the day it becomes something it is re-entered where it belongs.
  A link to a recipe would make TBD a second kitchen-notes module, which
  already exists for keeping things that are not recipes.
- **Not a kitchen note.** A note is a titled bookmark with a kind, a body,
  labels and pictures, and a library with filters. A TBD entry has an
  optional name and several links, in an order the owner sets by hand, and is
  read as one short page. Folding one into the other would make every field
  of each optional for the sake of the other.
- **Name or link, enforced by the service.** A CHECK cannot see the child
  table, and a PATCH that sends only `links: []` is right or wrong depending
  on the stored name, which a schema cannot see either; the service checks
  the entry as it would be saved and answers 422 in the usual shape.
- **A link without a scheme is given `https://`.** A link is usually typed
  as `example.com/x`, and refusing it would be the app being pedantic about
  something it can fix; one that names any other scheme is still refused,
  because a `javascript:` link rendered on a public page is an XSS. A colon
  followed by a digit is a port, not a scheme, so `localhost:8000` is a bare
  host.
- **Saved per entry, reordered in one call.** Each card saves on its own, so
  an edit to one entry never rewrites another; the order is one `PUT` of
  every id, which must be exactly the current entries - a stale tab's order
  is refused rather than merged, as 常用食材's duplicate is.

## The weekly schedule

- **Shaped by the owner's sheet, not by the plan above.** The plan had
  `ScheduledCook`: a date, a recipe, notes. The owner's Plan sheet is a
  different thing - per day, what to buy, what to take out of the freezer in
  the morning, at noon and in the evening, four meals (早, 中, 下午, 晚), the
  fruit and a note - and the sheet is what is actually used, so the tables
  hold its columns. A meal is not always a recipe ("外食", "吐司"), so each
  meal is free text first, with dishes and recipes optional.
- **The four marks are booleans, shown only when true.** In the sheet 要買?
  and the three 退冰? columns held whatever was typed, but what they answer
  is yes or no - is there something to buy, is something to come out of the
  freezer - and what to buy or thaw belongs in 備註 or the meal. So they are
  Boolean NOT NULL, false by default. A false mark carries no information
  worth a glyph, so the read page draws a ✓ for true and nothing for false,
  and the phone card a chip per true mark; a column of 「否」 would bury the
  few days that need doing. `s4chedule` turned every non-blank text true.
- **The columns run 星期幾, 早, 中, 下午, 晚, 水果, 要買?, 早退冰?, 中退冰?,
  晚退冰?, 備註 - deliberately not the sheet's order.** The sheet put 要買? and
  the morning and noon marks before the meals and 晚退冰? after them, a
  layout that grew in the sheet rather than one anybody chose. The owner
  asked for the meals first - they are what the page is read for - then the
  fruit, the marks together, and the note last. The edit card and the phone
  card follow the same order, so a field is found in one place on all three.
- **A meal is free text and any number of items, each a dish and optionally
  one of its recipes.** A dinner is often more than one dish (咖哩 and a
  soup), and text alone ("外食", "配白飯") still has to stand without naming
  anything, so the text stays on the meal and the dishes moved to
  `schedule_meal_item`, ordered by `position`. A dish can be chosen without a
  recipe, or with one; the same dish may appear twice only with two different
  recipes - the same dish and recipe twice in one meal says nothing the first
  did not, and is refused rather than silently merged.
- **Weeks run Saturday to Friday**, because the sheet's do, and a page shows
  two of them - this week and next - as the sheet does. `?week=` is the
  Saturday, so a week is a link.
- **One row per meal slot, not four column groups on the day.** Four meals
  as columns would be four copies of every rule about them on
  `schedule_day`; `schedule_meal` keyed by `(date, slot)` states them once,
  and a fifth slot would be a constant, not a migration.
  The slot is a fixed list (`MEAL_SLOTS`) rather than a 設定 vocabulary: it
  is a column of the schedule, not something the owner files things in.
- **The date is the key**, not a surrogate id: there is one day per date by
  definition, and the PUT addresses a day by it. A date with nothing planned
  has no row, and a save that empties a day deletes it - so the sheet's `-`
  is no row, and the table never fills with blank days.
- **A recipe implies its dish.** An item names a dish ("咖哩") and, when it
  matters, which way of making it; a recipe sent alone takes its dish, and a
  recipe of another dish is a 422. The rule spans two tables, so the service
  enforces it. The edit page picks the dish by search and the recipe from a
  select of that dish's recipes, which cannot produce the mismatch at all; a
  second search over every recipe would have needed the dish filled back in
  and a way to show the two disagreeing.
- **The dish is RESTRICT, the recipe SET NULL.** A plan naming a dish should
  not lose it silently, so deleting a scheduled dish is refused with the
  dates, as a dish with recipes is refused with them; the count is of items,
  the dates each listed once. A recipe is one way of making the dish;
  deleting it leaves the item its dish.
- **A day is written whole.** One PUT per day replaces it, the TBD card's
  shape: a day is small, and replace semantics make "clear this field" and
  "clear this meal" the same as leaving them out.
- **Saved by a button, not on blur.** A phone does not reliably blur a field
  when the thumb taps elsewhere, and a save that silently did not happen is
  the one failure the page must not have. A changed day says 未儲存, the week
  buttons are disabled while any is, and closing the tab asks.
- **Dates are local calendar dates, with no zone.** The box and the owner are
  both in Asia/Taipei, as every timestamp here assumes; the pages send the
  range from the browser's own date, and only a bare `GET` falls back to the
  server's today in Asia/Taipei.

## The starting ingredient list

- **Loaded by a migration, not by a script or the API.** Production receives
  the same starting list on deploy with nobody touching the box, the same
  reason the vocabularies are seeded by `v1ocabulary`. It runs once per
  database, and Alembic's version table is what records that it has.
- **The CSV lives at `alembic/import/ingredients.csv`, not under `data/`.**
  The design first put it at `data/import/`, but `.dockerignore` excludes
  `data/` (and `.gitignore` excludes `data/images/`), so a file there would
  never reach the image the migration runs in on the box — the upgrade would
  pass locally and fail on deploy. Beside the migrations, it ships with them;
  the migration reads it by a path relative to its own file.
- **The file is validated in full before anything is written.** A parent not
  in the file, an unknown category, a repeated name_cn or name_en, a row with
  no name, and an alias that repeats or equals a row name all stop the
  migration. Half a list, with the unknown remainder failing on the box, is
  worse than none.
- **Skipped, not merged, when a name is already taken.** A row matching any
  existing name slot or alias is left out, and the existing row is never
  modified — it is the owner's, and may hold more than the stub would. That
  also makes a second run insert nothing. A file cycle is not refused by
  validation; the load declines the link that would close it, as the write
  path's guard does.
- **Downgrade is a no-op.** The rows become ordinary data on landing. Telling
  "still an untouched stub" from "edited since" would need a marker column
  every ingredient carries forever, for a downgrade nobody expects to run.
- **No ORM.** The migration writes SQL through the bind and copies the seeded
  category names rather than importing them, because a revision must not
  depend on today's models or on another revision's module.

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
