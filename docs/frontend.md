# Frontend

React + Vite, react-router, TanStack Query, Tailwind v4. The conventions are
`media`'s, per the platform's house-style section; what is written here is what
is specific to food.

## Pages

Navigation is 料理 · 食譜 · 食材 · 筆記 · 排程 · TBD · 設定 - 料理 first, since a dish
is what you look for and its recipes hang off it: a top bar on a desktop, a bar
fixed to the bottom of the screen on a phone (`components/layout/Layout.jsx`).
The section a page belongs to - its edit pages included - is marked with
`aria-current="page"`; `lib/nav.js` holds that match.

**A section is one entry in `SECTIONS` (`lib/nav.js`)** - its label, its
link and the path prefixes it owns, edit pages included. Both bars draw from
that list, and the phone bar gives each entry a column of its own
(`grid-template-columns: repeat(<count>, …)`, set from the list's length), so
adding a section touches nothing else. The labels are kept short - two
characters, or TBD - centred and truncated within their column, which keeps
them readable at 360px with room for more.

| Page | Route | Gate |
| --- | --- | --- |
| Dish library | `/dishes` | public |
| Dish | `/dishes/:id` | public |
| Recipe library (the front page; `/` redirects here) | `/recipes` | public |
| Recipe | `/recipes/:id` | public |
| Ingredient library | `/ingredients` | public |
| Ingredient | `/ingredients/:id` | public |
| Kitchen-note library | `/notes` | public |
| Kitchen note | `/notes/:id` | public |
| 排程, the weekly schedule (`?week=` the first Saturday shown) | `/schedule` | public |
| TBD | `/tbd` | public |
| Add / edit a dish | `/edit/dishes/new`, `/edit/dishes/:id` | Access |
| Add / edit a recipe (a new one first asks how to start; `?dish=<id>` presets the dish) | `/edit/recipes/new`, `/edit/recipes/:id` | Access |
| Add / edit a recipe template | `/edit/templates/new`, `/edit/templates/:id` | Access |
| Add / edit an ingredient | `/edit/ingredients/new`, `/edit/ingredients/:id` | Access |
| Add / edit a note | `/edit/notes/new`, `/edit/notes/:id` | Access |
| 設定 (`/settings` redirects here) | `/edit/settings` | Access |
| Image library | `/edit/images` | Access |
| Edit the schedule (`?week=` as `/schedule`) | `/edit/schedule` | Access |
| Edit TBD | `/edit/tbd` | Access |

Any other path is a "page not found" page, not a redirect.

**The first release's paths redirect**, query string included, so bookmarks
survive: `/library/ingredient` → `/ingredients`, `/ingredient/:id` →
`/ingredients/:id`, `/edit/ingredient/...` → `/edit/ingredients/...`,
`/edit/vocabularies` → `/edit/settings`. `/edit/dishes/:id/edit` - the dish
form's path as its design named it - redirects to `/edit/dishes/:id`, the
shape every other edit page has. `routes.test.jsx` pins every route and every
redirect.

Media's detail route is `/<type>/:publicId/:slug?`; the cosmetic slug and the
second id went with the integer-primary-key decision, so ours is
`/ingredients/:id`.

**The detail page is the one this app exists for.** It is what gets opened on a
phone in a shop, signed out: selection notes, the preservation methods with
their durations, where to get the thing. Everything else is a list or a form.

**Every vocabulary shares one page**, 設定, a tab each. They are the
same kind of work — maintaining a short list — and a page each would be ten
screens with a handful of rows on them.

**There is no route guard, and there must not be one.** The gate is Cloudflare
Access on the path prefix, in front of the box. A guard in the browser would
suggest the gate lives in this application, and the day someone believes that
is the day it moves. For the same reason the edit links are visible to
everyone: hiding them protects nothing.

**The edit pages do send a signed-out browser through the Access login.**
Access only sees document loads, and a click from 食譜 to 設定 is not one, so
the page would open unchallenged and its first save — a background request —
would be the first thing Access saw. A background request cannot follow
Access's redirect to its login on another origin; it failed as a bare "Failed
to fetch". So:

- **`components/layout/EditSignIn.jsx`** wraps every `/edit` route. Each time
  an edit page opens it asks `GET /api/edit/session` (`api/session.js`); when
  Access answers with a redirect, it sends the whole window to
  `/api/edit/session?next=<this page>`, which Access *can* take through the
  login, and which returns it to the page. That happens as the page opens,
  before anything is typed. It renders its page whatever the answer and
  refuses nothing — it is not a guard. A second redirect within a minute of
  the first is skipped, so a sign-in that does not stick cannot loop.
- **`api/client.js`** sends every request under `/api/edit` with
  `redirect: 'manual'`, and turns Access's redirect into an error with status
  401, `signInRequired`, and a message saying the save did not happen and to
  sign in again in another tab. That is the session running out on an open
  page; reloading would throw the form away, so it does not.

## Libraries

The four libraries - dishes, recipes, ingredients, kitchen notes - are one scaffold,
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
  different filter. A key whose API parameter is an integer id is marked
  `id: true` and keeps only whole numbers, so a hand-edited `?category=abc`
  is ignored rather than sent - the API would refuse the whole list with a
  422.
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
  `dish_count` or `note_count` from `GET /api/labels` - not the total. The
  recipe library shows `dish_count`: a recipe's labels are its dish's.
- The list keeps the previous result on screen while a new filter loads
  (`keepPreviousData`), so the grid does not blank on every click.

| Library | URL keys | Table columns | Badges |
| --- | --- | --- | --- |
| 料理 `/dishes` | `kind`, `course`, `region`, `label` (all "any of") | 種類, 類別, 地區, 食譜 (how many) | - |
| 食譜 `/recipes` | `dish` (ids, sent as `dish_id`), `kind`, `course`, `status` (ids, sent as `status_id`), `method`, `equipment`, `author` (ids, sent as `author_id`), `label` (all "any of"); `written` = `true` / `false`. `kind`, `course` and `label` are the dish's | 類別, 做法, 時間, 作者, 狀態 | 書籤 when not written up |
| 食材 `/ingredients` | `category`, `label`, `rating` (one each); `stub`, `variety` (switches) | 分類 / 品種, 冷藏, 用於, 評等 | 待補, rating |
| 筆記 `/notes` | `kind`, `label` (both "any of") | 種類, 連結 (host only) | - |

**A dish card** (`pages/library/DishLibrary.jsx`) is the dish's cover - its
own first picture, else its first recipe's, as the API answers it - its name,
its English name under it when that differs, and a meta line of kind ·
course · region · 「N 份食譜」 (還沒有食譜 for none). Its view is remembered
under `cg1618:food:dishes-view`. **A recipe card** is the recipe's display
name, with its dish's name under it when the two differ - the table view
draws the same subtitle under the name.

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
deletes every kind of row (`<DeleteDialog kind="dish" | "recipe" | "ingredient"
| "note" id name onClose onDeleted? />`; `onDeleted` defaults to the kind's library), and
`lib/deleteTargets.js` says per kind which `cascade` counts it shows and echoes,
which block, and which reads go stale:

- it fetches `GET .../{id}/cascade` and sends the counts it displayed back as
  the delete's required parameters;
- on a 409 carrying `field` and `actual` it takes the server's number for that
  field, says so, and re-offers the button (「確認刪除」). Asking for a reload is
  what a prose-only error body forces;
- a blocking count (`recipes`, `used_in` and `meals` on a dish; `children`
  and `recipes` on an ingredient) is said up front in words, but the button
  stays: the refusal is the server's. Its 409 lists recipes, shown as links -
  under 它的食譜： those in `recipes` (a dish's own) and under 用到它的食譜：
  those in `used_in` - and under 排了它的日子： the dates in `meals`, each
  linked to its week on `/schedule`;
- a recipe's dialog has nothing that blocks: lines name dishes, the dish
  stays, and a meal on the schedule naming the recipe keeps its dish;
- a kitchen note has no cascade, so its dialog is the plain question.

## Detail pages

`/dishes/:id`, `/recipes/:id`, `/ingredients/:id` and `/notes/:id` are one reading column
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

- **Dish** (`pages/detail/Dish.jsx`): its gallery; its kind (醬料 drawn in
  the brand tone), course and region - each a link to the dish library
  filtered by it - and 也可以當作; the name and its other name slots; labels
  (to `/dishes?label=`); the description; then **食譜**, the dish's recipes
  as cover cards (the recipe's own cover, its display name, authors · status,
  書籤 when not written up), with **「＋ 新增食譜」** opening
  `/edit/recipes/new?dish=<id>` - the new-recipe chooser, the dish kept for
  whichever start is chosen - the one section drawn even when empty
  (還沒有食譜。), since its button is how a new dish gets a recipe; and
  **用在**, the recipes whose lines name this dish, which is what a sauce's
  page is mostly for.
- **Recipe**: its **dish, a link**, with the dish's kind (醬料 only), course,
  region and 也可以當作 beside it and the dish's labels under the status -
  shown read-only, since they are the dish's and edited there; 書籤 when not
  written up; the recipe's display name, and 「<dish> 的一份食譜」 under it
  when the recipe has its own name; a meta line of servings, time, methods
  and equipment; the **status, changed in place**; 來源 (platform; author, a
  link to the library filtered by them; title, linked out when there is a
  URL, the URL's host standing in for a missing title); **其他版本**, the
  dish's other recipes (`other_recipes`); 材料 and 步驟 in their groups
  (`lib/recipeGroups.js`: the ungrouped rows first, without a heading, then a
  block per group under its name, in the recipe's group order; an empty group
  is left out; ordinary steps numbered through every group, an optional
  step carrying a 可省略 chip in the number's place with its text muted, a
  備註 drawn as a ruled, tinted callout with no number); 保存; 筆記. A line
  links to its ingredient or to its dish (`/dishes/:id`); an optional line is
  drawn faint with （可省略）; a stub ingredient carries 待補.
- **存成範本**, beside 編輯, makes a recipe template of the recipe's
  structure: a dialog asks for the name (the recipe's display name to start
  with) and says what a template takes - 材料, 步驟, 做法, 器材, 份量, 時間 -
  and what it leaves; `POST /api/edit/recipe-templates/from-recipe/{id}`;
  then it says 「已存成範本「…」」 with links to the template's form. A refused
  name (another template has it) is said in the dialog, which stays open.
- **The status change** is `PATCH /api/edit/recipes/{id}` with `{status_id}`
  alone. The toggle offers the statuses 設定 manages, in their order
  (`GET /api/recipe-statuses`); it shows the chosen value while the
  request runs and the stored one again, with the server's sentence, if it
  fails. On success the recipe the PATCH answers with goes straight into the
  detail read's cache (`useApiMutation`'s `onSaved`), so the new status
  stays on screen even if the refetch after it fails, and every recipe read,
  the statuses' counts and the dish reads (a dish page lists its recipes'
  statuses) are invalidated.
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
drops); 合併 posts `{into, fingerprint}`. Text typed in the picker and not
picked is said under it (從清單選一個), since 合併 stays off until there is a
target. If either ingredient changed since
the preview, the server's 409 carries a fresh preview: it replaces the one
shown, the dialog says it changed, and the button becomes 確認合併. On
success the reads a merge moves are marked stale and the page goes to the
target - the source no longer exists. The dialog's body keeps room for the
result list, which would otherwise be clipped by the body's scroll.

## Forms

`/edit/dishes/...`, `/edit/recipes/...`, `/edit/templates/...`, `/edit/ingredients/...` and `/edit/notes/...` are one page
per entity, in sections on the reading column (`Section`), ending in
`components/forms/FormActions.jsx`: the error, then 儲存 / 取消 / 刪除. **The
error sits directly above the save button** with the server's own sentence -
a 409's or a 422's `detail` - because that is where the eye is when a save
did not work. A successful save goes to the detail page. A form whose
required selects are drawn from a vocabulary passes `ready` false until it
has loaded, and 儲存 reads 載入中… and stays off: the ingredient form waits
for the category tree, the fixed lists and the cooking methods, and says so
if the categories fail to load.

- **Loading an existing row** sets the form's state during render, keyed on the
  row's id (React's "adjusting state when a prop changes"), so there is no
  flash of the empty form and a background refetch never discards typing.
- **Saving** is `hooks/useOwnerSave.js`: POST or PATCH the row, then PUT the
  gallery to `.../{id}/images` - after the first save for a new row, since
  there is no id before it, and on an edit only when the gallery changed. If
  the row saved and the gallery did not, the new id is kept, so 儲存 again
  PATCHes it rather than creating a second row.
- **Each save invalidates every read its write can move**, not only its own:
  a recipe save also marks the dish reads stale (its dish's recipe count,
  cover and 用在; a 新增 dish is a new row), the ingredient library and the
  category tree (a 新增 line files a stub in the fallback category, whose
  count moves), the authors, status, source platform, method, equipment,
  材料分組 and 步驟分組 counts and the image library; a dish save, and a dish
  delete, mark the dish and recipe reads stale (every recipe of it shows its
  name) and the label, course, region and image counts; a recipe delete
  marks the dish reads too; an ingredient save, its delete and a merge move the category
  tree, labels, methods (heating rows), recipes (line names, used-in),
  images and 常用食材 (a renamed, deleted or merged ingredient is a changed
  chip), and a merge the recipe templates too (their lines move to the
  target); a note moves labels and images; a template save moves only the
  template list.
- **Every list is `components/forms/RowEditor.jsx`**: controlled `rows` /
  `onChange`, each row with a drag handle (⠿) and ✕, an add button under
  the list, and a render prop for the row's cells (`children(row, { index,
  number, update })`). Inside a grouped editor (below) a RowEditor is one
  container of a board: `container` names it and `start` is how many rows
  come before it, so rows are numbered - and their controls named, 「材料 3」 -
  through every group. The list operations are one pure reducer, `lib/rowList.js`;
  each row carries a browser-only `_key` so a reorder keeps React's state with
  its row, and the payload builders never send it.
- **Every reorder is a drag**, through `components/ui/Sortable.jsx`
  (`SortableList`, `SortableItem`, `DragHandle`, media's component ported):
  a row is picked up only by its handle, so the inputs inside it stay usable,
  and a press has to travel 4px before it becomes a drag, so a tap does
  nothing. It is dnd-kit's pointer events, so a finger drags as a mouse does
  and the page keeps scrolling under the wheel while a row is held. A focused
  handle moves its row one place with Up / Down (and Left / Right in the
  gallery's grid), and focus follows the row - the keyboard path, and the one
  the tests drive, since jsdom cannot drag. A vertical list's drag is locked
  to the vertical axis.
- **Rows that move between lists** share one `SortableBoard`: it is the one
  drag area, each `SortableList` inside it names its `container` and opens no
  drag area of its own, and `onMoveItem(from, to)` gets `{ container, index }`
  places. `SortableContainers` makes the containers themselves reorderable by
  a `DragHandle` of their own (`onMoveContainer(from, to)`). A dragged row
  meets rows and the drop zone of an empty container; a dragged container
  meets containers. The keyboard path crosses edges: Up on a container's
  first row puts it at the end of the container above, Down on its last at
  the start of the one below (`lib/boardMoves.js`), and focus follows the row
  by its id.
- **Choosing from a short vocabulary** - a dish's labels and serves-as, a
  recipe's methods and equipment - is `ChipPicker.jsx`, toggle chips with `aria-pressed`.
- **Aliases are one box**, split on any comma or 、 (`splitAliases`): they are
  unordered and never displayed, so a row editor's ordering would be noise.

**The typeahead** (`components/forms/Typeahead.jsx`) searches the list
endpoints' `q` - every name slot and alias, on the server - 250 ms after the
typing stops: `sources` is `['ingredient']`, `['dish']` or both (the
default), or `['recipe']` - the new-recipe chooser's search, each recipe
offered by its display name with its dish's beside it when the two differ, `exclude` keeps a row out (a recipe's lines never offer its own
dish), and `allowNew` adds 「新增 'xxx'」 when no result's name equals the
typed text exactly (`lib/typeahead.js`) - and only once the search has
answered, so a quick Enter cannot make a stub named after something the
library already has. `allowNewDish` adds a new-dish option the same way
(type `new-dish`; labelled 「新增料理」 when 「新增」 is offered beside it,
`newDishHint` saying what the save will make). A sauce among the results
carries a 醬料 chip. Handed
`items` instead - a list small enough to hold whole, the authors - it filters
that in the browser (a name slot containing the typed text, ignoring case and
width), asks the server nothing, and offers 「新增」 at once; `newHint` is the
words beside 「新增」 saying what the save will make. Up / Down
move, Enter picks - and never submits the form
around it - Escape closes the list without closing a dialog it sits in. It only
picks: `onSelect(option)` hands the caller `{ type, id, label, needsDetail,
kind }` - `type` one of `ingredient`, `dish`, `recipe`, `item`, `new`, `new-dish` - and
the box clears. `Picked`, from the same file, is how every caller
shows the choice in its place, with 待補 for a stub and 更換 to search again.

**Typed but not picked is never dropped.** `onQueryChange(text)` tells the
caller what is in the box ('' after a pick), and every caller refuses to save
over it: a recipe line holding text is not blank (below); the ingredient's
品種 parent and the recipe's 料理 refuse the save with a sentence naming the
text; the merge picker says it under the box.

**A new recipe asks how to start** (`pages/edit/NewRecipeChooser.jsx`):
`/edit/recipes/new` with none of `blank`, `template` or `from` in its query
string shows three sections instead of the form - **空白** (「空白食譜」),
**從範本** (the templates, in 設定's order, each with its line and step
counts; while there are none, where they come from and a link to 設定's 範本
tab) and **複製另一份食譜** (the typeahead over the recipe library). A choice
is written into the URL (`lib/newRecipe.js`) - `?blank=1`, `?template=<id>`
or `?from=<recipe id>`, pushed, so Back returns to the question - keeping
`?dish=` and nothing else, and the form opens on it. The dish page's
「＋ 新增食譜」 lands here too, the chooser saying which dish the recipe will
be under. The form waits for the template or recipe it was opened on before
it draws, so nothing typed is overwritten, and fills it in once:

- **from a template**: 份量, 時間, 材料 and 步驟 in their groups (steps with
  their kinds), 做法 and 器材. The header says 「從範本「…」開始。」 and, when
  the server left references out, 「範本裡有 n 個項目已不存在，已略過。」.
- **from another recipe**: all of that, and 保存 and 筆記; its dish is chosen
  unless `?dish=` names one. **Not its name, sources, status or pictures**:
  the header says 「複製自「…」」, linking to it, and that those were not
  copied. The new recipe starts on the first status, as any new recipe.

Nothing is written until 儲存, and what it writes is a new recipe. A template
or recipe that cannot be read says so with 「重新選擇」 back to the chooser.

**A recipe's 料理** is the form's first section, with the recipe's optional
**名稱** beside it (blank shows the dish's name) and 狀態, 份量 and 時間 under
them. The dish is picked with the typeahead over the dish library alone;
「新增」 names a dish the save creates - **a 料理 unless 「新料理的種類」, the
toggle shown under a new dish, says 醬料** - and a name the server already
knows is reused instead (`new_dish`). Picked, it shows its kind, or 新料理 /
新醬料 for one the save makes. `?dish=<id>` - the dish page's 「＋ 新增食譜」 -
reads that dish and starts the form with it chosen, once and never over a
dish chosen meanwhile; 取消 then goes back to the dish. With no dish, the save
is refused - 「這份食譜是哪道料理？」. The fields that are the dish's - names,
kind, course, serves-as, labels, description, aliases - are the dish form's,
not this one's.

**材料, 步驟 and 做法、器材 are shared sections**
(`components/forms/RecipeLinesSection.jsx`, `RecipeStepsSection.jsx`,
`RecipeMethodsSection.jsx`), drawn by the recipe form and the template form
alike; `lib/recipeStructure.js` reads a recipe response or a template body
into their state and builds the `lines` / `line_groups` / `steps` /
`step_groups` / `method_ids` / `equipment_ids` payload from it.
`RecipeLinesSection`'s `allowNew` is the one difference: off on the template
form, so a line's typeahead offers only what is already in the libraries.

**The template form** (`pages/edit/TemplateForm.jsx`) is 名稱 (required -
「範本要有名稱。」), 份量, 時間 and those three sections. A saved template
read back with `dropped` says how many items no longer exist and that saving
removes them for good. POST or PATCH sends `{name, body}`, the whole body;
saving and 取消 go to 設定's 範本 tab.

**The dish form** (`pages/edit/DishForm.jsx`) is the names, 種類 (a 料理 /
醬料 toggle), 類別 and 地區 selects, 也可以當作 (never the dish's own course)
and 標籤 chips, 簡介, 別名 and the gallery; saving goes to the dish's page.

**Recipe lines** hold a `target` - an ingredient, a dish, `{ type: 'new',
label }` or `{ type: 'new-dish', label, kind }` - from which
`lib/recipeLines.js` builds exactly one of `ingredient_id`, `sub_dish_id`,
`new_ingredient` or `new_dish` per line (a typed name in Han characters is
`name_cn`, otherwise `name_en`). A line's typeahead searches ingredients and
dishes and offers both 「新增」 (a stub ingredient) and 「新增料理」 (a dish,
**a 醬料** - `SAUCE`, the line default). A 新增 line shows 待補 until the save
creates the stub; a 新增料理 line is tagged 新醬料, and a picked dish its
kind. An entirely blank line is dropped; one with an amount, a note or
typed-but-unpicked text (the row's `pending`, never sent) and nothing chosen
is refused by number - 「第 n 行材料…還沒選食材或料理」.
A blank step is dropped the same way.

**Each step has a kind**, switched by a 步驟 / 可省略 / 備註 `Toggle`
(aria-pressed buttons, the fixed `step_kinds` list) above its text box. A new
row and a pasted one is 步驟. Only a 步驟 shows a number beside it, counted
through every group as the recipe's page counts them (`stepNumbers` in
`lib/steps.js`), so the numbers in the form are the numbers the page will
show; a 備註 row's box sits in the same ruled, tinted frame the page draws a
note in. The rows' accessible names - 「步驟 3」, 「步驟 3 的種類」 - keep the
running index RowEditor gives every row, so each stays unique whatever its
kind. The save sends each step as `{body, kind}`.

**常用 chips** sit above 材料 (`components/forms/CommonIngredientChips.jsx`),
one per 設定 常用食材, in that list's order. A tap appends a line naming that
ingredient to the **ungrouped** lines - whatever groups the recipe has - and
moves the focus to that line's 份量, so the amount is typed next. A chip
whose ingredient is already on a line anywhere in the recipe, grouped or not,
is drawn as used (✓, muted, `data-used`, and named 「加一行「蒜」（已在材料中）」
rather than 「加一行「蒜」」 for a screen reader) and still adds a line: one
ingredient on two lines is a real recipe. While the list is empty there is no
chip row and no hint - nothing at all.

**材料 and 步驟 sit in groups** (`components/forms/GroupedRowEditor.jsx`,
state and operations in `lib/groupedRows.js`). The ungrouped rows come first,
with their own add button; then each group is a box: a header with its drag
handle, its name and 移除分組, its rows, and its own add button
(「＋ 加一行材料到「醬汁」」), so a row added there belongs to it. 「＋ 加分組」
under the boxes offers the 設定 values (材料分組 or 步驟分組) this recipe does
not use yet as one-tap chips, in 設定's order, and a box for a one-off name.
A typed name that is a 設定 value, trimmed and in any case, is that value -
in the add box and in a header's name box alike, which is how a group is
renamed or repicked; one the recipe already has cannot be added again.
**Removing a group keeps its rows**: they move to the end of the ungrouped
rows, as the hint under 「＋ 加分組」 says. Rows drag within a group and
between groups, groups drag by their header handle, and the keyboard path
crosses a group's edge. The save sends `lines` + `line_groups` and `steps` +
`step_groups` (each group `{line_group_id}` or `{name}` with its rows); a
group left without a name is refused by its place - 「第 n 個材料分組還沒有名稱」.

**A source's 作者** is the typeahead over `GET /api/authors`, fetched once and
filtered in the browser. Picking one sends `author_id`; 「新增 'xxx'」 shows
the name with 新作者 and sends `new_author` (`name_cn` or `name_en` by the
lines' rule), which the save creates - or folds into an author already
answering to that name. Leaving it empty sends `author_id: null`.
`lib/recipeSources.js` builds the payload: a row with no author, title, URL
or typed text is dropped, and one whose author was typed and never picked
(`pendingAuthor`) is refused by number - 「第 n 個來源的作者打了…還沒選」.

**The recipe's 狀態 and a source's 平台** are selects over the managed
vocabularies (`GET /api/recipe-statuses`, `GET /api/source-platforms`). A new
recipe starts on the first status and a new source row on the first platform:
the form holds '' until one is chosen and shows, and sends, the first in its
place, so a row added before the list has loaded still lands on the first.
With no status at all the form leaves `status_id` out and the server's 422
says why.

**Steps** take 「貼上多行」 too: a dialog whose text becomes one step per
non-blank line with the leading numbering stripped (`lib/steps.js` -
`1.`, `1)`, `1、`, `(1)`, `①`, `一、`, `第一步`, `Step 1:`, bullets), because the
page numbers steps itself. 「加到」 picks where they go: 不分組 (the default)
or one of the recipe's step groups, at its end. Every pasted step is an
ordinary 步驟.

**Storage rows** show a min and a max. A row stored as one number (min = max,
the i2storage migration's shape) keeps its min following the max until the
min is edited itself - `pages/edit/storageDuration.js`'s rule, applied live.
**Heating rows** show the °F beside the °C as it is typed (`lib/temperature.js`).
Days and °C are whole numbers on the server: the inputs step by 1 and the
payload reads them with `integerOrNull` (`lib/rowList.js`).

**The gallery** (`components/forms/GalleryPicker.jsx`) is controlled and saves
nothing itself: `value` is `[{ image_id, url, thumb_url, focus }]`, first is
the cover (marked 封面). 上傳圖片 takes several files, uploading one at a time
so a bad file fails alone with its own message; uploading reaches the library
at once, attaching waits for 儲存. 從圖庫選 opens the library in a dialog,
「只看未使用」 on by default, 30 a page; several can be added before 完成, and
one already in the gallery is marked and can be taken out. Each picture has
a drag handle - the tiles drag in both directions, as a grid - 焦點
(`FocusPicker.jsx`: click or drag, arrow keys nudge 1% / 10%, previewed as a
cover and a thumbnail) and 移除.

## 設定 and 圖片

`/edit/settings` is `pages/edit/Settings.jsx`: a tab each for 食材分類,
常用食材, 範本, 標籤, 類別, 地區, 狀態, 來源, 作者, 材料分組, 步驟分組, 做法 and 器材, with 圖片庫 - the way
into `/edit/images` - beside the heading. 類別 and 地區 file a dish (地區 is
台式, 中式, 日式 …, hand-ordered, the order the dish form and filters offer);
renaming either marks the dish and recipe reads stale. 狀態 is the recipe statuses (想試,
可煮, 常煮 …; the first is what a new recipe starts on), 來源 the source
platforms (YouTube, 網站, 書 …), 作者 the sources' authors, and 材料分組 /
步驟分組 the groups a recipe's lines and steps are picked from (主料, 配料,
調味料 / 備料, 烹飪, 醬汁 …), hand-ordered - the recipe form offers them in
that order - and counted by the recipe groups using them; renaming any of
them marks every recipe read stale, as a course does. 作者 is listed by name, as 標籤 is, so it has no
drag handle and a new author is added without a `sort_order`.

- **The tab is in the URL**, `?tab=` with `categories`, `common-ingredients`,
  `templates`, `labels`, `courses`, `regions`,
  `statuses`, `platforms`, `authors`, `line-groups`, `step-groups`, `methods` or
  `equipment` (`hooks/useUrlTab.js`), so a tab can be linked to
  and survives a reload. A missing or unknown tab is the first, 食材分類, and
  the URL is left as it is. Choosing a tab **replaces** the history entry
  rather than pushing one: Back leaves 設定 instead of walking back through
  the tabs looked at on the way.
- **The bar is the `Tabs` primitive** (`components/ui/primitives.jsx`), the
  WAI-ARIA tabs pattern: a `tablist` of `tab`s, each `aria-controls` its
  `tabpanel`; only the selected tab is in the Tab order, and ←/→ (wrapping at
  the ends), Home and End move between tabs and select as they go. The row
  wraps on a phone rather than scrolling sideways, as media's `AdminTabBar`
  does, so no tab is off-screen.
- **Only the selected tab's editor is mounted**, so only its query runs. Each
  has its own loading, error and empty state, and one vocabulary failing to
  load leaves every other tab usable. Switching tabs drops an editor's local
  state - an open rename, a half-typed add.
- **A new vocabulary is one entry in `TABS`** in `Settings.jsx`: its id, its
  label and what its panel renders.

Each value is a `components/settings/NameRow.jsx`:

- **改名** turns the row into its two name slots in place; Enter saves,
  Escape puts the row back. A 409 (a duplicate name) or 422 is said under
  the boxes.
- **The drag handle** reorders by `sort_order` (`lib/vocabulary.js`
  `reorderPatches`): when every sibling's number is distinct the siblings
  keep the same set of numbers, handed out again in the new order - a
  one-place move is a swap, and a move and back restores exactly what was
  there - and when any tie (ordered by name, which no reassignment of equal
  values can change) the siblings are renumbered 1..n. Either way only the
  rows whose number changes are sent. The move saves at once
  (`hooks/useSortOrderMove.js`): the new order shows immediately, the list's
  handles are off until every PATCH has landed and the list has been read
  again - a second drag computed from an order still being written would undo
  the first - and a failure puts the stored order back with the server's
  sentence above the list. **Labels have no `sort_order`** and are listed by
  name, so their rows have no handle. **The category tree is nested lists**,
  one `SortableList` per sibling group: a category drags only among its
  siblings, and carries its children with it; moving it under another parent
  is 改名's 上層.
- **刪除** asks in `ConfirmModal`, saying the count it knows. A refusal is
  explained **in the row**: for a course, region, status, source platform,
  method or piece of equipment with the 409's `usage_count` (the server's number, newer than the page's); for a
  category with what is under it - its ingredients and child categories, both
  `RESTRICT`. The button stays even when the page already knows the delete
  will be refused: the refusal is the server's. The fallback category (預設)
  has no delete.
- **Add** is the line under each vocabulary (`AddNameForm.jsx`); a new value
  goes after the last one. A category row's ＋子分類 opens the same line
  under that node; renaming a category also offers 上層, its parent (never
  itself or anything beneath it).

**常用食材** (`components/settings/CommonIngredientsEditor.jsx`) is not a
vocabulary but an ordered pick of ingredients: the chips the recipe form
offers above its 材料. Each row is the ingredient's name (with 待補 for a
stub), a drag handle and ✕; under the list, an ingredient typeahead adds one
at the end - existing ingredients only, no 「新增」, and one already listed is
never offered. Every change - a drag (or Up / Down on the handle), a ✕, a
pick - `PUT`s the whole list (`{ingredient_ids}`) at once, by the rule a
vocabulary's move follows: the new list shows immediately, the handles and
✕ are off until the `PUT` has landed and the list has been read again, and a
failure puts the stored list back with the server's sentence above it. A
change makes only `GET /api/common-ingredients` stale - which is what the
recipe form's chips read.

**範本** (`components/settings/TemplatesEditor.jsx`) is the recipe templates,
in the order the new-recipe chooser offers them. Each row is the template's
name - a link to its form - with 材料 n · 步驟 m, a drag handle, 改名 (one
name box in place; Enter saves, Escape puts the row back, a taken name is
said in the row) and 刪除 after asking in `ConfirmModal`. 「＋ 新增範本」 opens
an empty form. A drag `PUT`s the whole order (`{ids}`) at once, by the same
rule: shown immediately, the handles off until it has landed and the list has
been read again, the stored order back with the server's sentence on a
refusal.

Label rows show where each label is used - 食材, 料理 and 筆記 separately; the
other vocabularies show `usage_count`. A change invalidates the vocabulary
and every owner that shows its names (a label: ingredients, dishes, recipes -
which show their dish's - and notes; a course or region: dishes and recipes;
a method: recipes and ingredients).

`/edit/images` is `pages/edit/ImageLibrary.jsx`, media's admin image page
without what food lacks: a grid of thumbnails (centred, `data-focus="none"` -
a focus belongs to an owner, not the file), each with its size and either
its owners as links (食材 / 料理 / 食譜 / 筆記, `lib/imageOwners.js`) or 未使用 and
刪除. **Only an unused image offers delete**, as in media: taking a picture
off a recipe is done on the recipe's form. The owners come from each attached
image's detail, read only for the tiles that have any; the list itself
carries just `attachment_count`. If the server refuses a delete because the
picture was attached since the page loaded, the tile shows the 409's owners.
「只看未使用」 and the page are in the URL (`?unused=1&page=2`); a page is 30,
fetched as 31 so 下一頁 knows whether there is one.

## TBD

A standalone page of loose notes, related to nothing else in the app: each
entry is an optional name and any number of links, in the owner's order.

**`/tbd`** (`pages/library/Tbd.jsx`) is one list, read whole: each entry's
name, if it has one, and its links under it. A link shows its label, or else
its host and path without the scheme, `www.`, query or trailing slash, cut to
40 characters (`lib/format.js` `linkText`); it opens in a new tab
(`rel="noopener noreferrer"`). 編輯 goes to `/edit/tbd`, and the empty state
offers the same link.

**`/edit/tbd`** (`pages/edit/TbdForm.jsx`) is the same list, editable in
place. Every entry is a card - 名稱, and its links in a `RowEditor` (網址 and
an optional 顯示文字 per row) - with its own 儲存 and 刪除:

- **儲存 sends the card as it stands**: `PATCH` with the name and every link,
  which replace the stored ones. An empty link row is left out. A card with
  neither a name nor a link says so in place and sends nothing; a refusal
  shows the server's sentence on the card. A card keeps what is typed in its
  own state, so another card's save never throws it away.
- **刪除 asks first**, in the shared `ConfirmModal` - there is nothing to
  count, so it is not the `DeleteDialog`.
- **「＋ 新增」 puts an unsaved card at the end.** Its 儲存 creates the entry
  (`POST`, which also puts it last) and its 取消 drops it without asking,
  since nothing was stored. It has no drag handle until it is saved.
- **Entries are reordered by their drag handle** (or Up / Down on it), saved
  at once with `PUT /api/edit/tbd/order`: the new order shows immediately,
  the list is frozen until the save has landed and the list has been read
  again, and a refusal puts the stored order back with the server's
  sentence - the rule `hooks/useSortOrderMove.js` applies on 設定.

完成 goes back to `/tbd`.

## 排程

The weekly schedule, after the owner's Plan sheet. **A week runs Saturday to
Friday, and both pages show two** - the week `?week=` names (any date in it is
moved to its Saturday; none, or not a date, is this week) and the one after.
`lib/schedule.js` holds the date arithmetic, done in UTC on `YYYY-MM-DD`
strings so a day can never shift; "today" is the browser's own date
(`hooks/useShownWeeks.js`). `components/layout/WeekNav.jsx` is ← 上週 · 本週 ·
下週 →, links that set `?week=`; 本週 drops it. The meal slots and their labels
come from the fixed vocabulary `meal_slots`.

**`/schedule`** (`pages/library/Schedule.jsx`) heads the page with the
fortnight's range and 編輯, which opens `/edit/schedule` on the same week.
Each week is a section titled with its range:

- **on a desktop, a table with the sheet's columns in the sheet's order** -
  星期幾 (the weekday and date), 要買?, 早退冰?, 中退冰?, 早, 中, 下午, 晚,
  晚退冰?, 水果, 備註. A meal cell shows its text, its dish linked to the
  dish, and its recipe as 食譜：… linked to the recipe;
- **on a phone, a card per day** listing only the fields that hold something,
  in the same order, and a dash when nothing is planned.

Today's row and card are marked (`aria-current="date"`, the brand tint).

**`/edit/schedule`** (`pages/edit/ScheduleForm.jsx`) is the same two weeks,
a card per day: the four meals - each 內容 (free text), a 料理 picked by
`Typeahead` over the dish library (existing dishes only), and, once a dish is
picked, a select of **that dish's** recipes (read from `GET
/api/dishes/{id}`) with 不指定食譜 first - then the six plain fields.

- **Each card saves with its own 儲存** - one `PUT` of the whole day, blanks
  as null and empty meals as null (`lib/schedule.js` `dayPayload`). Not on
  blur: a phone does not reliably blur a field, and a save that silently did
  not happen is the failure this page must not have.
- **Nothing typed is lost silently.** A changed card says 未儲存 until it is
  saved; while any card is unsaved the page counts them, the week buttons are
  disabled, 完成 reads 放棄修改, and closing the tab asks. A dish typed into
  the search but not picked refuses the save with a sentence.
- A refusal shows the server's sentence on the card and keeps what was typed;
  a save says 已儲存. A card keeps its own state, so another card's save never
  throws it away.

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
The shell is drawn through a portal on `document.body`, so a dialog opened
from a form is never inside its `<form>` (Enter in a dialog's input cannot
submit the page); Tab is kept inside it, wrapping at both ends, and focus goes
back to the opener when it closes. While `busy` - a delete, a merge, a
confirmed action on its way - neither Escape nor the backdrop closes it.

## Images

Every `<img>` lazy-loads (`lazy-images.test.js`), and every cropped
(`object-cover`) one applies its focal point with `focusStyle()` from
`lib/images.js` or opts out with `data-focus="none"`
(`focus-images.test.js`). Both guards are media's, and both read a tag with
one scanner that skips `{...}` expressions, strings and comments to find the
`>` that closes it - a regex stopping at the first `>` would end the tag
inside `onError={(e) => ...}` and never read an attribute written after it.
Each proves its scanner on fixtures before scanning the source.

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
