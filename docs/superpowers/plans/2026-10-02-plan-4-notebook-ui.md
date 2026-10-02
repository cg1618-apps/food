# Plan 4 — the notebook UI

Working scaffolding: deleted when branch 4 merges. Spec:
`docs/superpowers/specs/2026-10-02-recipes-and-ingredients-v2-design.md`, "UI"
(and "API" for the routes the pages call). Branch `feat/notebook-ui`, cut from
`dev` after branches 2 and 3 merged. Frontend only, except where a task finds a
backend defect (fix it in its owning file, with a test).

## Rulings made before execution

- **media is the reference** (platform `CLAUDE.md`, "House style"); read
  `C:\Users\cgent\Documents\cg1618\media\frontend` and
  `media/docs/frontend/design-system.md` before inventing anything. Copy:
  directory layout (`components/{layout,forms,ui}`, `lib/`, `hooks/`), PascalCase
  components, `// Frontend:`-style header comments explaining *why*, the
  controlled `rows`/`onChange` sub-row editors with **Move up / Move down**
  buttons (no drag library — `media/frontend/src/components/forms/CastEditor.jsx`),
  `FocusPicker` and `focusStyle()` (`media/frontend/src/lib/covers.js`) for
  focus points, the hand-rolled `ConfirmModal` shape (Escape cancels; closes
  only on a press that starts and ends on the backdrop), localStorage keys
  prefixed `cg1618:` with try/catch on read and write (`media/frontend/src/lib/dashboardView.js`),
  and the source-scanning guard tests `lazy-images.test.js` (every `<img>` has
  `loading="lazy"`) and `focus-images.test.js` (every `object-cover` `<img>`
  has `style=` or `data-focus="none"`).
- **Deliberate divergences from media, required by the spec**, each recorded
  in `docs/notes/decisions.md` with its reason: filters and search live in the
  **URL query** (bookmarkable; the detail page's category link has to work);
  a **sidebar on desktop and a drawer on a phone** rather than media's inline
  chip panel; the cover/list choice **is remembered** per library; a **bottom
  bar on a phone** rather than a full-screen drawer; a **multi-image gallery**
  (media's picker holds one image per role); the typeahead searches the
  server (ingredients and recipes) and has arrow-key navigation.
- **No new runtime dependencies** beyond what is installed, unless a task
  cannot be done without one; then say why in the commit.
- **Copy is Chinese-first**, as the data is: navigation 食譜 · 食材 · 筆記 · 設定,
  badges 書籤 / 待補, section headings in Chinese. Keep it consistent.
- **Every page owes loading, error and empty states** (the existing `Loading`,
  `ErrorNote`, `Empty`).
- **After any frontend change run `npm run build`**; `npm run lint` and
  `npm test` stay green; `theme-tokens.test.js` keeps refusing raw colours.
- **Mutations invalidate by resource, not by one URL.** Today ingredient
  mutations invalidate only the list query, so detail pages and category counts
  go stale (an open item). Invalidate every query whose key starts with the
  resource's read prefix (e.g. `/api/ingredients`, `/api/ingredient-categories`)
  and close the open item.
- Commits by exact path, conventional prefixes, **no trailers**. Do not push.

## Task 1 — foundation

- **Tokens and type.** Redefine the semantic tokens in `src/index.css` for the
  notebook direction — warm paper canvas, terracotta brand, ink text — light and
  a warm dark brown (not grey) dark; add the tokens the design needs
  (e.g. `surface-2`, `text-faint`, `border-strong`, `on-brand`, `ok`) and
  `--font-display` / `--font-sans`. Noto Serif TC for headings via Google Fonts
  `<link>` in `index.html` with `display=swap`, falling back to system serif;
  sans for metadata and controls. Load the `frontend-design` skill for the
  visual pass, but the spec's direction is fixed.
- **Primitives** (`src/components/ui.jsx`, or split into `components/ui/` the
  way media does if it grows): `Button` (`kind`, `size`), `Input`, `TextArea`,
  `Select` — **`className` extends the base classes instead of replacing them**
  (known defect); `Chip`/`Badge` (書籤, 待補, rating), `Section` (a titled block
  for the single reading column), `Dialog`/`ConfirmModal`, `Toggle` (封面/清單).
- **Layout.** `components/layout/Layout.jsx`: a top bar on desktop and a fixed
  bottom bar on a phone, links 食譜 (`/recipes`) · 食材 (`/ingredients`) ·
  筆記 (`/notes`) · 設定 (`/settings`), active via `aria-current="page"`; page
  content padded so the bottom bar never covers it. `/` redirects to `/recipes`.
  Old routes (`/library/ingredient`, `/ingredient/:id`, `/edit/vocabularies`)
  redirect to the new ones so bookmarks survive.
- **Routes** (`App.jsx`), all registered now with a placeholder page each so
  later tasks touch only their own files: reads `/recipes`, `/recipes/:id`,
  `/ingredients`, `/ingredients/:id`, `/notes`, `/notes/:id`; writes under
  `/edit/...` (gated by path): `/edit/recipes/new`, `/edit/recipes/:id`,
  `/edit/ingredients/new`, `/edit/ingredients/:id`, `/edit/notes/new`,
  `/edit/notes/:id`, `/edit/settings`, `/edit/images`. 設定 links to
  `/edit/settings`.
- **Endpoints** (`api/endpoints.js`) for every route the pages call — recipes
  (list, detail, cascade, creators, create, update, remove, images),
  ingredients (+ merge preview, merge, images), notes, images (list, detail,
  upload, remove), the three vocabularies, fixed vocabularies — and extend
  `endpoints.test.js` (every write under `/api/edit`).
- **Hooks.** `useApiMutation` invalidation by resource prefix (above);
  `useFixedVocabularies()` reading `/api/vocabularies/fixed` once (staleTime
  Infinity) — the end of `METHODS` duplicated in `IngredientForm.jsx`;
  `useUpload()` for multipart image upload (no Content-Type header; the client
  must not force JSON on FormData).
- **Guard tests**: `lazy-images.test.js`, `focus-images.test.js` (copy media's).
- **Lib**: `lib/images.js` (`focusStyle`, `parseFocus`, tested), `lib/temperature.js`
  (°C→°F, tested).

## Task 2 — the library scaffold and the three libraries

- `hooks/useUrlFilters.js`: read and write filter state from the URL query —
  single and multi-valued keys, booleans, the search term (debounced write,
  replace not push for typing). Pure parse/serialise functions tested.
- `lib/libraryView.js`: remembered 封面/清單 per library, key
  `cg1618:food:<library>-view`, whitelist, try/catch (media's
  `dashboardView.js`), tested including a throwing `localStorage`.
- `components/layout/LibraryLayout.jsx`: title + add button; search; a filter
  sidebar on `lg` and a drawer below it (opened by a 篩選 button showing the
  active-filter count); the view toggle; a result count; loading / error /
  empty (an empty library offers the add button; an empty filter result
  offers clearing the filters). `CoverGrid` (cover image with focus, or a
  placeholder; name; one metadata line; badges) and a table view.
- **Recipes** (`pages/library/RecipeLibrary.jsx`): sidebar course, status,
  kind, method, equipment, creator, label, written-up / bookmark-only; table
  columns course, methods, time, creator, status; badge 書籤 when not written up.
- **Ingredients** (`pages/library/IngredientLibrary.jsx`, rebuilt): category
  tree with counts (`?category=` works — known defect), labels, only stubs
  (with the backlog count), only varieties, rating; table columns category or
  parent, fridge storage, used-in count, rating; badges 待補 and rating.
- **Notes** (`pages/library/NoteLibrary.jsx`): kind, label; table title, kind,
  link host.

## Task 3 — the detail pages

Single reading column each; a section with nothing in it is hidden.

- **Recipe** (`pages/detail/Recipe.jsx`): hero image + thumbnail strip; course
  and names; meta line (servings, time, methods, equipment, storage); a status
  control changeable in place (PATCH `status` only); sources as links; other
  versions; ingredients grouped by section, each line linking to its ingredient
  or sub-recipe, optional lines muted, stub ingredients marked 待補; steps
  grouped by section, numbered; notes; for a base, "used in". Edit link;
  delete via the dialog (Task 4's generic one).
- **Ingredient** (`pages/detail/Ingredient.jsx`, rebuilt): header (image,
  category link to `/ingredients?category=`, names, used-in count, variety
  count, rating); description; 挑選; 品種 (children with rating and where
  bought); 保存 as a state × method grid with ranges; 加熱 with °C and °F;
  links; used in. A stub shows its header and a 待補 note linking to the form.
  **Merge** — 「合併到…」 opens a picker (typeahead over ingredients), shows the
  preview (moves, new aliases, dropped storage rows, prose moved/dropped),
  then merges sending the preview's `fingerprint`; on 409 it shows the fresh
  preview from the body and re-asks; on success it navigates to the target.
- **Note** (`pages/detail/Note.jsx`): title, kind, link, body, labels, images.

## Task 4 — forms, the gallery picker, deletes

- `components/forms/RowEditor` pattern (controlled rows, Move up / Move down,
  remove, add) used by every list below.
- `components/forms/Typeahead.jsx`: server search with debounce, arrow keys +
  Enter + Escape, results from ingredients **and** recipes (names and aliases)
  where asked, and when nothing matches exactly 「新增 'xxx'」.
- `components/forms/GalleryPicker.jsx` (modelled on media's `ImagePicker` +
  `FocusPicker`): upload (several), choose from the library (modal, unused
  first, paged), reorder, set focus, remove; saves with
  `PUT .../{id}/images`. For a new owner, the gallery is saved after the first
  save returns the id.
- **IngredientForm** (rebuilt): names, category (tree select), parent, rating,
  labels, aliases, description / selection / sourcing / preservation notes,
  storage rows (state, method, min–max, notes — the existing `storageDuration`
  helper and its tests stay), heating rows (method, °C with live °F,
  duration, preheat, flip, notes), links, needs-detail, gallery.
- **RecipeForm**: names, kind, course, serves-as, status, servings, time,
  version of (typeahead over recipes), sources (platform, creator with
  suggestions from `/api/recipe-creators`, url, title), lines (typeahead →
  ingredient / recipe / 「新增」 stub shown with 待補 until saved; amount,
  note, optional; section chosen from the recipe's sections or typed), steps
  (row editor plus 「貼上多行」 which splits on newlines and strips leading
  numbering — a pure tested function), labels, methods, equipment,
  description, storage notes, notes, aliases, gallery.
- **NoteForm**: title, kind, url, body, labels, gallery.
- **Delete** through one generic `DeleteDialog` (the existing inline cascade
  dialog generalised): fetch `cascade`, show counts, send them, correct itself
  on a 409 with `field`/`actual`, show the blocking list (`used_in`, children)
  when the delete is refused.
- Reducer / splitter / typeahead pieces get vitest tests.

## Task 5 — 設定 and 圖片

- `/edit/settings`: sections for ingredient categories (tree), labels, courses,
  cooking methods, equipment — add, **rename** inline, reorder (Move up/down →
  `sort_order`), delete; a 409 explanation shown inline with the usage count;
  an error state (known defect: `Vocabularies` showed none). Replaces
  `pages/edit/Vocabularies.jsx`.
- **Backend touch:** `GET /api/labels` counts only ingredients; make each label's
  count include recipes and kitchen notes (and say which in `docs/api.md`), with
  a test whose label is used by all three owners.
- `/edit/images`: the image library grid, an unused filter, owners on each
  image, delete for unused images.

## Task 6 — finish

- `docs/frontend.md` rewritten present-tense for the new pages, layers and
  guard tests; `docs/notes/decisions.md` (the divergences above);
  `docs/open-items.md` (close the stale-cache item; add anything found);
  `CLAUDE.md` status.
- **Done means driven in the running app**: after `npm run build`, against
  `:8001` in Chrome, for every entity (recipe, ingredient, note, category,
  label, course, method, equipment, image) add, edit and delete; a recipe with a
  stub line and a sub-recipe; a merge; a gallery upload with a focus point;
  a phone-width pass (bottom bar, drawer). Clean the dev data up afterwards.
- Full backend suite, frontend lint/test/build, PR into `dev`, merge, delete
  this plan.
