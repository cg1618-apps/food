# Frontend

React + Vite, react-router, TanStack Query, Tailwind v4. The conventions are
`media`'s, per the platform's house-style section; what is written here is what
is specific to food.

## Pages

Navigation is 食譜 · 食材 · 筆記 · 設定: a top bar on a desktop, a bar fixed to
the bottom of the screen on a phone (`components/layout/Layout.jsx`). The
section a page belongs to - its edit pages included - is marked with
`aria-current="page"`; `lib/nav.js` holds that match.

| Page | Route | Gate |
| --- | --- | --- |
| Recipe library (the front page; `/` redirects here) | `/recipes` | public |
| Recipe | `/recipes/:id` | public |
| Ingredient library | `/ingredients` | public |
| Ingredient | `/ingredients/:id` | public |
| Kitchen-note library | `/notes` | public |
| Kitchen note | `/notes/:id` | public |
| Add / edit a recipe | `/edit/recipes/new`, `/edit/recipes/:id` | Access |
| Add / edit an ingredient | `/edit/ingredients/new`, `/edit/ingredients/:id` | Access |
| Add / edit a note | `/edit/notes/new`, `/edit/notes/:id` | Access |
| 設定 (`/settings` redirects here) | `/edit/settings` | Access |
| Image library | `/edit/images` | Access |

Any other path is a "page not found" page, not a redirect.

**The first release's paths redirect**, query string included, so bookmarks
survive: `/library/ingredient` → `/ingredients`, `/ingredient/:id` →
`/ingredients/:id`, `/edit/ingredient/...` → `/edit/ingredients/...`,
`/edit/vocabularies` → `/edit/settings`. `routes.test.jsx` pins every route
and every redirect.

Media's detail route is `/<type>/:publicId/:slug?`; the cosmetic slug and the
second id went with the integer-primary-key decision, so ours is
`/ingredients/:id`.

**The detail page is the one this app exists for.** It is what gets opened on a
phone in a shop, signed out: selection notes, the preservation methods with
their durations, where to get the thing. Everything else is a list or a form.

**Every vocabulary shares one page**, 設定, a section each. They are the
same kind of work — maintaining a short list — and a page each would be five
screens with a handful of rows on them.

**There is no route guard, and there must not be one.** The gate is Cloudflare
Access on the path prefix, in front of the box. A guard in the browser would
suggest the gate lives in this application, and the day someone believes that
is the day it moves. For the same reason the edit links are visible to
everyone: hiding them protects nothing.

## Libraries

The three libraries - recipes, ingredients, kitchen notes - are one scaffold,
`components/layout/LibraryLayout.jsx`, with each page supplying its data, its
words and its filters:

- **Title and add button**, then a search box, the 篩選 button (below `lg`
  only), the 封面 / 清單 toggle and a result count.
- **Filters in a sidebar on a desktop and a drawer on a phone.** The sidebar
  is built from `components/layout/FilterPanel.jsx` - `FilterGroup`,
  `FilterOptions` (toggle chips), `FilterSwitch` (a checkbox with a count) and
  `FilterTree` (the category tree). Below `lg` the same controls open in the
  shared `Dialog`, which a phone draws as a bottom sheet; the 篩選 button
  carries the number of filters that are on.
- **Every filter and the search term live in the URL query**
  (`hooks/useUrlFilters.js`, pure parsing in `lib/urlFilters.js`). A library
  declares a spec of URL keys - `single`, `multi` ("any of", the key repeated)
  or `bool` (on, or absent) - each mapped to its API parameter. A filter click
  pushes a history entry, so Back undoes it; typing replaces, debounced by
  300 ms. A switch that is off sends nothing: `needs_detail=false` would be a
  different filter.
- **封面 / 清單 is remembered per library** in `localStorage` under
  `cg1618:food:<library>-view` (`lib/libraryView.js`), every read and write in
  a try/catch, falling back to 封面.
- **The cover view** (`CoverGrid.jsx`): the cover cropped at its focus, or the
  name's first character in the serif when there is no photograph; the name,
  one line of metadata, badges. **The list view** (`LibraryTable.jsx`): the
  name as a link with its badges, then the page's columns.
- **Two empties, two directions**: an empty library offers the add button; a
  filter or search that matches nothing offers 清除搜尋與篩選.
- **A label chip carries its own library's count** - `ingredient_count`,
  `recipe_count` or `note_count` from `GET /api/labels` - not the total.
- The list keeps the previous result on screen while a new filter loads
  (`keepPreviousData`), so the grid does not blank on every click.

| Library | URL keys | Table columns | Badges |
| --- | --- | --- | --- |
| 食譜 `/recipes` | `course`, `status`, `kind`, `method`, `equipment`, `creator`, `label` (all "any of"); `written` = `true` / `false` | 類別, 做法, 時間, 作者, 狀態 | 書籤 when not written up |
| 食材 `/ingredients` | `category`, `label`, `rating` (one each); `stub`, `variety` (switches) | 分類 / 品種, 冷藏, 用於, 評等 | 待補, rating |
| 筆記 `/notes` | `kind`, `label` (both "any of") | 種類, 連結 (host only) | - |

**The ingredient category filter is exact.** Choosing 蔬菜 lists what is filed
under 蔬菜 itself, not under its child categories; that is the API's
`category_id`, the count beside each node is the same number, and it is the
category the ingredient page links to (`/ingredients?category=<id>`). The
tree says so under itself. The stub backlog's count (`只看待補`) shows whether
or not the switch is on, read from the unfiltered list - which also names a
variety's parent when the filtered list does not include it.

## Two things that are not pages

**The `needs_detail` backlog and the uncategorised pile are filters** on the
library, with a count shown next to the filter. Without the count the backlog
is invisible and stubs accumulate forever.

**Delete is a dialog, not a page**, and not `window.confirm` — it has to show
counts and to correct itself. One component, `components/forms/DeleteDialog.jsx`,
deletes every kind of row (`<DeleteDialog kind="recipe" | "ingredient" | "note"
id name onClose onDeleted? />`; `onDeleted` defaults to the kind's library), and
`lib/deleteTargets.js` says per kind which `cascade` counts it shows and echoes,
which block, and which reads go stale:

- it fetches `GET .../{id}/cascade` and sends the counts it displayed back as
  the delete's required parameters;
- on a 409 carrying `field` and `actual` it takes the server's number for that
  field, says so, and re-offers the button (「確認刪除」). Asking for a reload is
  what a prose-only error body forces;
- a blocking count (`used_in` on a recipe; `children` and `recipes` on an
  ingredient) is said up front in words, but the button stays: the refusal is
  the server's, and its 409 lists the recipes in `used_in`, shown as links;
- a kitchen note has no cascade, so its dialog is the plain question.

## Detail pages

`/recipes/:id`, `/ingredients/:id` and `/notes/:id` are one reading column
each, built from `components/layout/Detail.jsx`: `DetailStatus` (loading; a
404 as "not found" with a link back to the library; any other error),
`Prose` (written notes with their line breaks, no markdown), `LabelLinks`
(each label a link to its library filtered by it), `RecipeLinks` and
`DetailActions` (編輯, then 刪除 through `DeleteDialog`). Pictures are
`components/ui/Gallery.jsx`: the first image large, the rest a strip of
thumbnails that swap it in place, every one cropped at its focus.

**A section with nothing in it is not drawn** - no heading over an empty
list. A recipe saved only as a bookmark is a short page, not a page of
empties.

- **Recipe**: course (a link to the library filtered by it), 基底 for a
  base, 也可以當作, 書籤 when not written up; names; a meta line of servings,
  time, methods and equipment; the **status, changed in place**; labels;
  description; 來源 (platform, creator and title, linked when there is a URL);
  其他版本 (`lib/versions.js`: the original first, marked 原版, then the
  siblings, never the recipe itself); 材料 and 步驟 grouped by section
  (`lib/sections.js`: one block per section in first-use order, rows keeping
  their order; steps numbered through the whole recipe); 保存; 筆記; 用在
  (the recipes naming a base directly). A line links to its ingredient or
  sub-recipe; an optional line is drawn faint with （可省略）; a stub
  ingredient carries 待補.
- **The status change** is `PATCH /api/edit/recipes/{id}` with `{status}`
  alone. The 想試 / 可煮 / 常煮 toggle shows the chosen value while the
  request runs and the stored one again, with the server's sentence, if it
  fails; success invalidates every recipe read.
- **Ingredient**: category (`/ingredients?category=<id>`) and, for a
  variety, its parent; names, rating, 待補; aliases; how many recipes use it
  and how many varieties it has; labels. A stub adds a 待補 note linking to
  its form. Then 說明, 挑選, 品種 (each child with its rating and where it is
  bought - the full row's children carry `sourcing_notes` for this), 哪裡買,
  保存, 加熱 (°C with the °F beside it, 要預熱, 中途翻面), 參考連結, 用在.
- **保存 is a state x method grid** (`lib/storageGrid.js`): rows are the
  states and columns the methods, both in the fixed vocabularies' order, and
  only those in use - a fridge-only ingredient is one column, not seven. A
  cell is its range (`formatDays`) and its notes; the general preservation
  notes follow the grid.
- **Note**: title, kind, the link shown by its host, labels, body, pictures.

**Merge** is 「合併到…」 on the ingredient page,
`components/modals/MergeDialog.jsx`: pick the target with the Typeahead
(ingredients, never itself); read the preview in words
(`lib/mergePreview.js` - counts that move, names that become aliases, and in
a warning block the storage rows and notes the target already has and so
drops); 合併 posts `{into, fingerprint}`. If either ingredient changed since
the preview, the server's 409 carries a fresh preview: it replaces the one
shown, the dialog says it changed, and the button becomes 確認合併. On
success the reads a merge moves are marked stale and the page goes to the
target - the source no longer exists. The dialog's body keeps room for the
result list, which would otherwise be clipped by the body's scroll.

## Forms

`/edit/recipes/...`, `/edit/ingredients/...` and `/edit/notes/...` are one page
per entity, in sections on the reading column (`Section`), ending in
`components/forms/FormActions.jsx`: the error, then 儲存 / 取消 / 刪除. **The
error sits directly above the save button** with the server's own sentence -
a 409's or a 422's `detail` - because that is where the eye is when a save
did not work. A successful save goes to the detail page.

- **Loading an existing row** sets the form's state during render, keyed on the
  row's id (React's "adjusting state when a prop changes"), so there is no
  flash of the empty form and a background refetch never discards typing.
- **Saving** is `hooks/useOwnerSave.js`: POST or PATCH the row, then PUT the
  gallery to `.../{id}/images` - after the first save for a new row, since
  there is no id before it, and on an edit only when the gallery changed. If
  the row saved and the gallery did not, the new id is kept, so 儲存 again
  PATCHes it rather than creating a second row.
- **Every list is `components/forms/RowEditor.jsx`**: controlled `rows` /
  `onChange`, each row with ▲ / ▼ (上移 / 下移) and ✕, an add button under
  the list, and a render prop for the row's cells (`children(row, { index,
  update })`). The list operations are one pure reducer, `lib/rowList.js`;
  each row carries a browser-only `_key` so a reorder keeps React's state with
  its row, and the payload builders never send it.
- **Choosing from a short vocabulary** - labels, methods, equipment,
  serves-as - is `ChipPicker.jsx`, toggle chips with `aria-pressed`.
- **Aliases are one box**, split on any comma or 、 (`splitAliases`): they are
  unordered and never displayed, so a row editor's ordering would be noise.

**The typeahead** (`components/forms/Typeahead.jsx`) searches the list
endpoints' `q` - every name slot and alias, on the server - 250 ms after the
typing stops: `sources` is `['ingredient']`, `['recipe']` or both, `exclude`
keeps a row out (a recipe is not its own version), and `allowNew` adds
「新增 'xxx'」 when no result's name equals the typed text exactly
(`lib/typeahead.js`). Up / Down move, Enter picks - and never submits the form
around it - Escape closes the list without closing a dialog it sits in. It only
picks: `onSelect(option)` hands the caller `{ type, id, label, needsDetail,
kind }` and the box clears. `Picked`, from the same file, is how every caller
shows the choice in its place, with 待補 for a stub and 更換 to search again.

**Recipe lines** hold a `target` - an ingredient, a recipe, or `{ type: 'new',
label }` - from which `lib/recipeLines.js` builds exactly one of
`ingredient_id`, `sub_recipe_id` or `new_ingredient` per line (a typed name in
Han characters is `name_cn`, otherwise `name_en`). A 新增 line shows 待補 until
the save creates the stub. An entirely blank line is dropped; one with an
amount but nothing chosen is refused by number. Sections are free text with
the recipe's own sections offered (a `datalist` shared by lines and steps); a
new line or step starts in the section of the one above it.

**Steps** take 「貼上多行」 too: a dialog whose text becomes one step per
non-blank line with the leading numbering stripped (`lib/steps.js` -
`1.`, `1)`, `1、`, `(1)`, `①`, `一、`, `第一步`, `Step 1:`, bullets), because the
page numbers steps itself.

**Storage rows** show a min and a max. A row stored as one number (min = max,
the i2storage migration's shape) keeps its min following the max until the
min is edited itself - `pages/edit/storageDuration.js`'s rule, applied live.
**Heating rows** show the °F beside the °C as it is typed (`lib/temperature.js`).

**The gallery** (`components/forms/GalleryPicker.jsx`) is controlled and saves
nothing itself: `value` is `[{ image_id, url, thumb_url, focus }]`, first is
the cover (marked 封面). 上傳圖片 takes several files, uploading one at a time
so a bad file fails alone with its own message; uploading reaches the library
at once, attaching waits for 儲存. 從圖庫選 opens the library in a dialog,
「只看未使用」 on by default, 30 a page; several can be added before 完成, and
one already in the gallery is marked and can be taken out. Each picture has
◀ / ▶, 焦點 (`FocusPicker.jsx`: click or drag, arrow keys nudge 1% / 10%,
previewed as a cover and a thumbnail) and 移除.

## 設定 and 圖片

`/edit/settings` is `pages/edit/Settings.jsx`: 食材分類, 標籤, 類別, 做法 and
器材, top to bottom, each its own query with its own loading, error and empty
state, so one vocabulary failing to load leaves the others usable. Each value
is a `components/settings/NameRow.jsx`:

- **改名** turns the row into its two name slots in place; Enter saves,
  Escape puts the row back. A 409 (a duplicate name) or 422 is said under
  the boxes.
- **▲ / ▼** (上移 / 下移) reorder by `sort_order` (`lib/vocabulary.js`
  `reorderPatches`): when every sibling's number is distinct the two rows
  swap numbers - so up then down restores exactly what was there - and when
  any tie (ordered by name, which a swap cannot change) the siblings are
  renumbered 1..n, sending only the rows that change. **Labels have no
  `sort_order`** and are listed by name, so their rows have no arrows.
- **刪除** asks in `ConfirmModal`, saying the count it knows. A refusal is
  explained **in the row**: for a course, method or piece of equipment with
  the 409's `usage_count` (the server's number, newer than the page's); for a
  category with what is under it - its ingredients and child categories, both
  `RESTRICT`. The button stays even when the page already knows the delete
  will be refused: the refusal is the server's. The fallback category (預設)
  has no delete.
- **Add** is the line under each section (`AddNameForm.jsx`); a new value
  goes after the last one. A category row's ＋子分類 opens the same line
  under that node; renaming a category also offers 上層, its parent (never
  itself or anything beneath it).

Label rows show where each label is used - 食材, 食譜 and 筆記 separately; the
other vocabularies show `usage_count`. A change invalidates the vocabulary
and every owner that shows its names (a label: ingredients, recipes and
notes; a method: recipes and ingredients).

`/edit/images` is `pages/edit/ImageLibrary.jsx`, media's admin image page
without what food lacks: a grid of thumbnails (centred, `data-focus="none"` -
a focus belongs to an owner, not the file), each with its size and either
its owners as links (食材 / 食譜 / 筆記, `lib/imageOwners.js`) or 未使用 and
刪除. **Only an unused image offers delete**, as in media: taking a picture
off a recipe is done on the recipe's form. The owners come from each attached
image's detail, read only for the tiles that have any; the list itself
carries just `attachment_count`. If the server refuses a delete because the
picture was attached since the page loaded, the tile shows the 409's owners.
「只看未使用」 and the page are in the URL (`?unused=1&page=2`); a page is 30,
fetched as 31 so 下一頁 knows whether there is one.

## Layers

- **`api/client.js` is the only file that calls `fetch`.** It joins the array
  FastAPI puts under `detail` for a validation error — the naive version
  renders `[object Object]`, for the one error a malformed body produces — and
  it attaches `status` and `body` to the thrown error so a caller can branch on
  409 without re-implementing fetch.
  It leaves the `Content-Type` alone for a `FormData` body, so the browser
  writes the multipart boundary itself.
  `buildUrl` repeats the key for an array value (`course_id=1&course_id=2`),
  which is how FastAPI reads a `list[int]` query parameter.
- **`api/endpoints.js` is the single source of URL truth.** Each group's
  `list()` doubles as the resource's read prefix. Its test asserts every
  mutation URL sits under `/api/edit` - the invariant the backend asserts over
  its route table, on the side where the URL is chosen - and walks the whole
  object, so a new endpoint must be classified as a read or a write before the
  suite passes.
- **`hooks/useApi.js`** wraps TanStack Query so no component builds a cache key
  by hand. `useApiMutation({ method, invalidate })` invalidates **by
  resource**: `invalidate` is a list of read prefixes, and every cached query
  whose URL sits under one of them (whole path segments) is refreshed - a save
  refreshes the detail page and the cascade counts, not only the list.
  `useFixedVocabularies()` reads every closed list once per page load;
  `useUpload()` posts one image file as multipart.

## Colour and type

**The direction is a kitchen notebook**: warm paper, brown-black ink, one
terracotta accent for the thing a page points at, and a warm-brown dark mode
rather than a grey one. Headings are Noto Serif TC (loaded in `index.html`
with `display=swap`, system serifs behind it); metadata and controls use the
system sans.

**Semantic tokens only** - `canvas`, `surface`, `surface-2`, `border`,
`border-strong`, `text`, `text-muted`, `text-faint`, `brand`, `brand-hover`,
`brand-soft`, `on-brand`, `danger`, `ok`, `warn`, `warn-soft`, `scrim`, plus
`font-display` and `font-sans`. As in media, each Tailwind token points at a
runtime `--c-*` variable and the light and dark palettes in `index.css`
redefine only those. A numbered grey or a raw hex in a component fails
`theme-tokens.test.js`, which is what keeps dark mode from rotting one
component at a time and keeps the four apps looking like one product.

## Primitives

`components/ui/primitives.jsx`: `Button` and `LinkButton` (`kind` primary /
outline / danger / ghost, `size` sm / md), `Field`, `Input`, `TextArea`,
`Select`, `Card`, `Chip` (`tone`), `Badge` (`kind` bookmark 書籤 / stub 待補 /
rating with `value`), `Section` (a titled block on a ruled line) and `Toggle`
(封面 / 清單). **`className` extends the base classes, never replaces them.**
`components/ui/Dialog.jsx` is the modal shell - Escape closes, and the
backdrop closes only on a press that starts and ends on it -
and `components/modals/ConfirmModal.jsx` the yes/no question drawn in it.

## Images

Every `<img>` lazy-loads (`lazy-images.test.js`), and every cropped
(`object-cover`) one applies its focal point with `focusStyle()` from
`lib/images.js` or opts out with `data-focus="none"`
(`focus-images.test.js`). Both guards are media's.

## Loading, error and empty

Three states every list and detail page owes the reader, as named components
in `components/ui/states.jsx`, so that forgetting one is visible rather than rendering a
page that looks broken while it is merely empty.

## How the built bundle is served

**One process serves the API and the bundle, and nothing sits in front of it** —
cloudflared connects straight to uvicorn, so there is no proxy to serve a static
file this app declines to. `app/main.py` is the whole story:

- **`/assets/...`** is mounted as `StaticFiles`, when the build produced an
  `assets/` directory at all. Vite inlines every asset when the bundle is small
  enough, so the mount is conditional.
- **`/api/...` and `/health/...`** are refused by the catch-all with a 404, even
  when unregistered. This app's health path is `/health`, not `/api/health`, so
  a mistyped probe path must not come back as a 200 carrying the bundle.
- **Any other path that names a real file inside the bundle is served as that
  file** — `favicon.svg`, `favicon.ico`, `robots.txt`, anything the build copies
  from `frontend/public/` to the root of `frontend_dist/`. The path is resolved
  and confined to the dist directory first, so `..%2F.env` cannot read a file
  beside the bundle.
- **Everything else is `index.html`**, so client-side routing works.

The order matters and is the same as `media`'s: the API routers are registered
before the catch-all, so it cannot shadow a route that exists.

**A file in `frontend/public/` reaches production only through this handler.**
Before it served real files, `/favicon.svg` answered with `index.html` under
`text/html` and the browser discarded it — the icon was in the repository and in
the bundle, and had never once been shown.

## After any frontend change

```bash
cd frontend && npm run build
```

or `:8001` serves the old bundle while `:5174` serves the new one, and the
difference reads as a bug in whichever you looked at second.
