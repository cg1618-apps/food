# Recipes, ingredients v2, images, kitchen notes and the UI — design

Status: **draft for owner review**. Working scaffolding: when the work it
describes has shipped, what is still true moves into `docs/` and this file is
deleted (platform `CLAUDE.md`, "Tracking work").

## Intent

The owner keeps recipes in a Google Doc and kitchen knowledge in two Google
Sheets. This work makes the app able to hold **everything in those three
references**, except nutrition (the 零食 sheet) and the weekly schedule (the
Plan sheet), which are later modules. It also rebuilds the UI, which the owner
finds unintuitive and badly structured, and proves that add, edit and delete
work for every entity.

What the owner said, settled during brainstorming:

- **Structure only for recipes.** No recipe import; recipes are typed in
  through the UI.
- **One-time import of ingredient names** taken from the recipe doc's
  ingredient lists, because no reference holds an ingredient master list. The
  sheets' storage, selection, heating and fruit rows are **not** imported; the
  schema must fit them and the owner enters them.
- **Versions of one dish are separate recipes, linked** ("a version of").
- **A small Kitchen notes library** for compilations, technique videos and
  general tips.
- **Images** for recipes, ingredients and notes, with media's image system as
  the reference.
- **Image backup:** bind mount now, file backup recorded as an open item and
  raised with the manager as a platform question.
- **UI:** notebook visual direction; filter sidebar with cover and list views
  for every library; single reading column for both detail pages.

Success: every field in the references has a home; every entity can be added,
edited and deleted from the UI, verified in the running app; the library opens
with real vocabularies instead of empty selects.

Out of scope: nutrition of any kind, the schedule, kitchen inventory, the
random picker, shopping list, restaurants, fetching images from a URL, recipe
scaling, cook mode.

## Reference → field map

Every column in the references, and where it lands. Anything not listed was
empty in every row.

| Reference | Column / feature | Lands in |
| --- | --- | --- |
| Recipe doc | title, `(YT 詹姆士)` suffix | `recipe.name_cn`; source platform + creator |
| Recipe doc | `Link:` (sometimes two) | `recipe_source` rows |
| Recipe doc | `人數` | `recipe.servings` |
| Recipe doc | ingredient list, amounts | `recipe_line` (ingredient link + `amount`) |
| Recipe doc | ingredient groups (漢堡醬, 調味料, for soup) | `recipe_line.section` |
| Recipe doc | `optional`, `自由添加`, `可省` | `recipe_line.is_optional` |
| Recipe doc | `米酒or清酒`, `味醂可代替糖` | `recipe_line.note` |
| Recipe doc | a sauce used inside a dish (蚵仔煎醬) | `recipe.kind = base`, nested via `recipe_line.sub_recipe_id` |
| Recipe doc | `Steps for 備料 / 醬汁備料 / cooking / noodles` | `recipe_step.section` |
| Recipe doc | `* tips`, `Notes:`, unit conversions inside a recipe | `recipe.notes` |
| Recipe doc | `保存期限約3天`, `放涼再裝, 冰冰箱保存` | `recipe.storage_notes` |
| Recipe doc | section headers 主食 / 配菜 / 湯 / 小吃 / 甜點 / 飲料 / 醬料 | `recipe.course_id` |
| Recipe sheets | 品項 | `recipe.name_cn` |
| Recipe sheets | first column (飯 / 麵 / 肉 / 麵包 …) | recipe labels |
| Recipe sheets | 烹調方式 | `recipe_method` → `cooking_method` |
| Recipe sheets | 器具 | `recipe_equipment` → `equipment` |
| Recipe sheets | 來源 (YT / shorts / website / book), creator, URL | `recipe_source` |
| Recipe sheets | 可當主食 / 可當配菜 / 可當點心 | `recipe_serves_as` → `recipe_course` |
| Recipe sheets | Recipe O / X | derived: has lines or steps ("written up" vs 書籤) |
| Recipe sheets | 備註, `冷藏: 1 week`, `包含醬` | `recipe.notes` / `recipe.storage_notes` / a nested base |
| Recipe sheets | 語言 | not modelled — empty in every row |
| 合輯, Tips sheets | title, creator, URL | `kitchen_note` (kind 合輯 / 技巧 / 參考) |
| 可煮 sheet | dish, time | `recipe.status = can_cook`, `recipe.time` |
| 保存期限 sheet | Unused / Opened × 常溫 / Fridge / Freeze, how-to, source | `ingredient_preservation` (state, method, range, notes) + `ingredient_link` |
| 保存期限 sheet | 熟肉 rows | `ingredient_preservation.state = cooked` |
| 挑選 sheet | criteria columns, source | `ingredient.selection_notes` + `ingredient_link` |
| 加熱 sheet | Item, Method, 預熱, 翻面, °C, °F, Time | `ingredient_heating` (°F derived) |
| Fruit sheet | Item / Specific Item | parent / child ingredient |
| Fruit sheet | Rating (S / A / B) | `ingredient.rating` |
| Fruit sheet | Buy Source, Remark | `ingredient.sourcing_notes`, `ingredient.description` |
| — | photographs | image library + per-owner galleries |

## Data model

Conventions are module 1's and are not restated: integer keys, `name_cn` /
`name_en` / `name_alt` slots with a `num_nonnulls` CHECK, aliases in a child
table, naive Taipei timestamps, closed vocabularies as `String` validated
against `app/constants.py`, `passive_deletes="all"` on every relationship
across a `RESTRICT` key.

### Ingredient changes

**`ingredient`** gains `rating` — `String`, nullable, one of `S A B C D`
(`RATINGS` in `app/constants.py`). It means "how good this variety is" and is
used mostly on child ingredients (愛文芒果 under 芒果).

**`ingredient_preservation`** changes:

| Change | Detail |
| --- | --- |
| add `state` | `String NOT NULL`, one of `unused`, `opened`, `cooked` (`PRESERVATION_STATES`), displayed 未使用 / 已開封 / 熟食. Existing rows migrate to `unused`. |
| replace `duration_days` | with `duration_min_days` and `duration_max_days`, both nullable, both positive, `max >= min` when both set (CHECK). Existing values copy into both. |
| unique key | `(ingredient_id, method)` becomes `(ingredient_id, state, method)`. |

"infinite" and "see the date" are `notes`, with both durations null. This
reverses module 1's "one typical number, a range goes in notes": the sheet
states a range in almost every row, and a typical number would be invented.
The decision is recorded in `docs/notes/decisions.md` when this ships.

**`ingredient_heating`** — new. How to heat or cook one thing quickly: the
加熱 sheet.

| Column | Detail |
| --- | --- |
| `id` | |
| `ingredient_id` | `NOT NULL`, CASCADE |
| `method_id` | `NOT NULL`, → `cooking_method`, RESTRICT |
| `temperature_c` | Integer, nullable, positive. °F is computed on display, never stored. |
| `duration` | String, nullable, free text: `7 分`, `10 秒`, `1–3 分` |
| `preheat`, `flip` | Boolean, `NOT NULL`, default false |
| `notes` | Text |
| `sort_order` | Integer, default 0 |

Not unique on method: 香腸 may be air-fried two ways.

**`ingredient_link`** — new. Reference links (the sheets' source columns).
`id`, `ingredient_id` (CASCADE), `url` (`NOT NULL`, http/https only, validated
in the schema), `title` (nullable), `sort_order`.

### Shared vocabularies

Three new tables with one shape — `id`, `name_cn`, `name_en`, `sort_order` —
a has-a-name CHECK, and unique `lower(name_cn)` / `lower(name_en)` indexes:

- **`recipe_course`** — seeded 主食, 配菜, 湯, 小吃點心, 甜點, 飲料, 醬料.
- **`cooking_method`** — seeded 煮, 壓力鍋煮, 煎, 炒, 炸, 氣炸, 烤, 蒸, 川燙,
  涼拌, 微波, 混合. Shared by recipes and `ingredient_heating`.
- **`equipment`** — seeded 鍋子, 壓力鍋, 平底鍋, 氣炸鍋, 烤箱, 油鍋, 果汁機,
  電鍋, 微波爐, 保鮮盒, 碗.

The schema migration also seeds a starter **ingredient category** tree —
肉類, 海鮮, 蔬菜, 菇類, 水果, 蛋豆製品, 主食穀物, 調味料, 乳製品, 乾貨 — and
starter **labels** from the sheets' first column: 飯, 麵, 肉, 麵包, 馬鈴薯,
地瓜, 沙拉, 鍋. Everything seeded is ordinary editable data. The migration's
downgrade deletes seeded rows only where nothing references them.

Seeding in the migration rather than a script is so production receives the
same starting vocabulary on deploy with nobody touching the box. Tests use
`create_all`, which does not run seeds; fixtures create what they need, as
`fallback_category` already does.

### Recipes

**`recipe`**

| Column | Detail |
| --- | --- |
| `id` | |
| `name_cn`, `name_en`, `name_alt` | at least one; **not unique** — versions share names |
| `kind` | `NOT NULL`, `dish` or `base` (`RECIPE_KINDS`), default `dish` |
| `course_id` | nullable, → `recipe_course`, RESTRICT |
| `variant_of_id` | nullable, → `recipe`, **SET NULL** |
| `status` | `NOT NULL`, `want_to_try` / `can_cook` / `regular` (`RECIPE_STATUSES`), displayed 想試 / 可煮 / 常煮, default `want_to_try` |
| `servings` | String, free text |
| `time` | String, free text (`1hr`, `30m`) |
| `description` | Text |
| `storage_notes` | Text |
| `notes` | Text |
| `created_at`, `updated_at` | |

`variant_of_id` is **one level deep**: a recipe that is a version of
something may not itself have versions, and may not point at a recipe that is
itself a version. Enforced on the write path (422). SET NULL rather than
RESTRICT because the other versions are complete recipes in their own right.

"Written up" is **derived**, never stored: a recipe with at least one line or
step. A stored flag would disagree with the content the first time someone
forgot to tick it.

**`recipe_alias`** — as `ingredient_alias`: unique per recipe, lookup index on
`lower(value)`, never displayed.

**`recipe_serves_as`** — `(recipe_id, course_id)` composite key, both CASCADE.
May include the recipe's own course; the UI does not offer it.

**`recipe_label`**, **`recipe_method`**, **`recipe_equipment`** — link tables
with composite keys. Recipe side CASCADE; vocabulary side RESTRICT for method
and equipment (deleting a method in use is a 409 naming the count) and CASCADE
for labels (module 1's label behaviour, kept uniform across both owners).

**`recipe_source`**

| Column | Detail |
| --- | --- |
| `id`, `recipe_id` (CASCADE), `sort_order` | |
| `platform` | `NOT NULL`, `youtube` / `shorts` / `website` / `book` / `other` (`SOURCE_PLATFORMS`) |
| `creator` | String, nullable, free text. Distinct values are served for suggestions and filtering. |
| `url` | nullable (a book has none); http/https when set |
| `title` | nullable |

At least one of `creator`, `url`, `title` (CHECK).

**`recipe_line`**

| Column | Detail |
| --- | --- |
| `id`, `recipe_id` (CASCADE) | |
| `position` | Integer `NOT NULL`; unique `(recipe_id, position)` |
| `section` | String, nullable |
| `ingredient_id` | nullable, → `ingredient`, **RESTRICT** |
| `sub_recipe_id` | nullable, → `recipe`, **RESTRICT** |
| `amount` | String, nullable |
| `note` | String, nullable |
| `is_optional` | Boolean `NOT NULL`, default false |

CHECK `num_nonnulls(ingredient_id, sub_recipe_id) = 1`. A line may not name its
own recipe (CHECK `sub_recipe_id <> recipe_id`), and the nesting graph may not
cycle (write path, recursive query, as `app/services/hierarchy.py` guards
categories). The same ingredient may appear twice in one recipe — once for the
meat, once for the sauce — so there is no uniqueness on it.

**`recipe_step`** — `id`, `recipe_id` (CASCADE), `position` (unique per
recipe), `section` (nullable), `body` (Text `NOT NULL`).

### Kitchen notes

**`kitchen_note`** — `id`, `title` (`NOT NULL`), `kind` (`compilation` /
`technique` / `reference`, `KITCHEN_NOTE_KINDS`, displayed 合輯 / 技巧 / 參考),
`url` (nullable, http/https), `body` (Text), `created_at`, `updated_at`.
**`kitchen_note_label`** links labels (both CASCADE). A note has one title, not
name slots: it is a bookmark, not a catalogue entity, and nothing will ever
need to find it by an English name it does not have.

### Images

Adapted from media's image library (`media/app/models/image.py`,
`media/app/services/integrations/image_library.py`).

**`image`** — one stored picture.

| Column | Detail |
| --- | --- |
| `id` | |
| `checksum` | SHA-256 of the normalised JPEG bytes, unique |
| `storage_key` | `library/<checksum>.jpg`, relative to `IMAGE_DIR` |
| `thumb_key` | `library/thumbs/<checksum>.jpg` |
| `original_filename` | |
| `byte_size`, `width`, `height` | of the normalised image |
| `uploaded_at` | |

**Attachments are one join table per owner**, not media's polymorphic
`owner_type` / `owner_id`: `recipe_image`, `ingredient_image`,
`kitchen_note_image`, each `(id, <owner>_id, image_id, position, focus)`.

- Owner side **CASCADE**: deleting a recipe removes its attachments, never the
  image.
- Image side **RESTRICT**: an attached image cannot be deleted; the API answers
  409 and says where it is used.
- `position` unique per owner; position 0 is the cover.
- `focus` is `"X% Y%"` (0–100 each) or null for centred, validated as media's
  `app/schemas/image_focus.py` does.
- One image may be attached to several owners.

Media records that its polymorphic owner "has nothing in the database stopping
an attachment outliving its owner", and has orphan gaps because of it. food has
three owner types; real foreign keys cost three small tables and remove the
whole class.

**Upload pipeline** (media's, carried over):

1. Stream the multipart field `file` in 1 MB chunks; refuse past
   `MAX_IMAGE_UPLOAD_MB` (default 10) with 413, checking both the declared
   size and the bytes actually read.
2. Ignore the extension and Content-Type. Pillow `verify()`, then reopen;
   failure is 422.
3. Re-encode: flatten alpha onto white, cap the long edge at 2000 px, JPEG
   quality 88, plus a 400 px thumbnail. **The re-encode is the security
   control** — it strips EXIF (including GPS) and any payload riding in the
   file.
4. Checksum the normalised bytes. An existing checksum returns the existing
   row (200); a new one is written and returns 201.

**Storage** is `IMAGE_DIR`, a setting (default `data/images` in development,
`/app/data/images` in the container). Media hard-codes a relative path, and its
own decisions page records that leaving the path implicit produced a wrong
spec. Files are written via a `.part` file and an atomic rename.

**Serving** is a `StaticFiles` mount at `/images` over `IMAGE_DIR`. Reads are
public in this app and filenames are content hashes, so a replaced image is a
new URL and caches never serve the old one — the reason media built a library
at all. The SPA catch-all refuses `/images/...` alongside `/api/...` and
`/health/...`, or a missing image answers 200 with `index.html`. Vite proxies
`/images` in development.

**Production** bind-mounts `./data/images:/app/data/images` in
`docker-compose.prod.yml` (pinned by the existing prod-compose test);
`.gitignore` and `.dockerignore` exclude `data/`. **There is no file backup**:
`docs/open-items.md` records it, and the manager session is asked for a
platform-level answer, because media, food and art each needing their own
rclone timer is three answers to one question. Dish photographs cannot be
re-fetched from anywhere, which is why this is an open item and not a footnote.

New dependencies: `Pillow`, `python-multipart`.

### Deletion summary

| Relationship | Behaviour |
| --- | --- |
| recipe → aliases, lines, steps, sources, serves-as, label/method/equipment links, image attachments | CASCADE |
| recipe ← lines in other recipes (`sub_recipe_id`) | RESTRICT → 409 naming the recipes |
| recipe ← its versions (`variant_of_id`) | SET NULL |
| ingredient ← recipe lines | RESTRICT → 409 naming the recipes |
| ingredient → heating, links, image attachments | CASCADE |
| course ← recipes (`course_id`), method / equipment ← links or heating rows | RESTRICT → 409 with a count |
| course ← serves-as links, label ← any link | CASCADE |
| image ← any attachment | RESTRICT → 409 naming the owners |

## Behaviour

### Recipe lines resolve three ways

A line names `ingredient_id`, `sub_recipe_id`, or `new_ingredient`
(`{name_cn?, name_en?}`) — exactly one, else 422. An id that names no row is a
**404**, not a 422 (module 1's hand-over). The stored discriminator comes from
which column is set, never from a payload field.

`new_ingredient` creates a **stub** in the same transaction: filed in the
fallback category, `needs_detail = true`. If the typed name equals an existing
ingredient's name slot or alias (case-insensitive), the existing row is used
instead of creating a duplicate — so the same new name typed in two lines of
one save yields one stub, not a unique-violation. A near match is the UI's job
(the typeahead shows it before the user chooses "new").

### Saving a recipe

`POST` takes the whole recipe. `PATCH` takes any subset; `lines`, `steps`,
`sources`, `aliases`, `serves_as_ids`, `label_ids`, `method_ids`,
`equipment_ids` each **replace** the stored list wholesale when present and are
untouched when absent. Positions are assigned from list order. One request is
one transaction, so a failed stub or a cycle leaves nothing half-written.

The cycle guard runs on the merged graph: adding line `B` to recipe `A` is
refused (422) if `A` is reachable from `B` through sub-recipe lines.

### "Used in"

- **For an ingredient**: distinct recipes with a line naming the ingredient
  **or any of its descendants**, at unbounded depth (recursive CTE over
  `ingredient.parent_id`). 生抽 in one line and 老抽 in another is one recipe
  using 醬油. Lines inside nested base recipes do **not** count the outer dish
  — depth through `sub_recipe_id` is zero, stated here because the module 1
  hand-over requires the depth to be explicit.
- **For a base recipe**: distinct recipes with a line naming it directly.

The ingredient list filter `GET /api/recipes?ingredient_id=` uses the same
query, so the count and the list cannot disagree.

### Ingredient merge

`GET /api/ingredients/{id}/merge-preview?into={target}` and
`POST /api/edit/ingredients/{id}/merge` with `{"into": target}`. The source
row is folded into the target and deleted:

- recipe lines, child ingredients, links, image attachments (appended after the
  target's) and labels (union) move to the target;
- the source's name slots and aliases become target aliases, skipping any the
  target already answers to;
- preservation rows move unless the target already has that
  `(state, method)`; heating rows always move; **the target wins every
  conflict**, and the preview lists each row that would be dropped;
- the source's prose fields are dropped when the target's are non-empty and
  moved when the target's are empty; the preview lists which;
- merging into itself, or into one of its own descendants, is 422.

### Delete

Every delete keeps module 1's shape: `GET .../{id}/cascade` returns the counts
the UI echoes back, and a delete whose counts have moved is a 409 carrying
`expected` and `actual`. A RESTRICT refusal is a 409 whose body lists what
blocks it (recipe names, owner names, a count for vocabularies).

## API

Reads under `/api`, writes under `/api/edit`; one router file per resource;
inputs `extra="forbid"`; errors `{"detail": ...}` with `CONSTRAINT_MESSAGES`
gaining one sentence per new named constraint.

| Resource | Read | Write |
| --- | --- | --- |
| recipes | `GET /api/recipes` · `GET /api/recipes/{id}` · `GET /api/recipes/{id}/cascade` · `GET /api/recipe-creators` | `POST /api/edit/recipes` · `PATCH`/`DELETE /api/edit/recipes/{id}` · `PUT /api/edit/recipes/{id}/images` · `PATCH /api/edit/recipes/{id}` with only `status` is the in-place status change |
| ingredients (additions) | detail gains `rating`, `heating`, `links`, `images`, `used_in`; `GET /api/ingredients/{id}/merge-preview?into=` | `PUT /api/edit/ingredients/{id}/images` · `POST /api/edit/ingredients/{id}/merge`; create/update accept `rating`, `heating`, `links` (wholesale replace, as `preservation` already is) |
| vocabularies | `GET /api/recipe-courses` · `/api/cooking-methods` · `/api/equipment`, each with a usage count | `POST`, `PATCH`, `DELETE` under `/api/edit/...`, one factory |
| kitchen notes | `GET /api/kitchen-notes` (`q`, `kind`, `label_id`) · `GET /api/kitchen-notes/{id}` | `POST`/`PATCH`/`DELETE /api/edit/kitchen-notes/...` · `PUT .../{id}/images` |
| images | `GET /api/images` (`unused`, paged) · `GET /api/images/{id}` (with owners) | `POST /api/edit/images` (multipart) · `DELETE /api/edit/images/{id}` |
| enums | `GET /api/vocabularies/fixed` — preservation methods and states, ratings, recipe kinds and statuses, source platforms, note kinds, each with its display label | — |

The fixed-enum endpoint ends the duplicated `METHODS` list in
`IngredientForm.jsx`: the frontend reads every closed list from the backend.

`GET /api/recipes` filters: `q` (name slots and aliases), `course_id`,
`status`, `kind`, `label_id`, `method_id`, `equipment_id`, `creator`,
`ingredient_id`, `written_up` (true/false). Multi-valued filters accept
repeated parameters and mean "any of". Results are a bare array, as the
ingredient list is today; summaries carry what both library views need — cover
image (thumb URL and focus), course, status, creators, methods, written-up.

`PUT .../images` takes `[{"image_id": n, "focus": "50% 30%" | null}]` in order
and replaces the owner's gallery.

`deploy/gated-paths` is unchanged: every write is already under `/api/edit`.
`/images` is a read path and is public by design.

## UI

**Visual direction: notebook.** Warm paper canvas, serif headings
(Noto Serif TC, loaded with `font-display: swap`, falling back to system
serif), sans for metadata and controls, terracotta accent. Implemented by
redefining the existing semantic tokens in `src/index.css` — `canvas`,
`surface`, `border`, `text`, `text-muted`, `brand`, `brand-soft`, `danger`,
`warn-soft` — plus whatever new semantic tokens the design needs, light and dark
(a warm dark brown, not grey). `theme-tokens.test.js` keeps refusing raw hex and
numbered greys in components.

**Navigation:** 食譜 · 食材 · 筆記 · 設定. A top bar on desktop, a bottom bar
on a phone. `/` goes to the recipe library. Edit links stay visible to everyone;
Cloudflare Access is the gate.

**Libraries** — recipes, ingredients, kitchen notes — share one shape:

- filter sidebar on desktop, a drawer on a phone;
- a 封面 / 清單 toggle, remembered per library in `localStorage` (wrapped in
  try/catch);
- every filter and the search term live in the URL query, so a filtered view
  is bookmarkable and links such as the detail page's category link work;
- cover view: cover image (or a placeholder), name, one line of metadata,
  badges — 書籤 (not written up), 待補 (stub), rating;
- list view: a table — recipes show course, methods, time, creator, status;
  ingredients show category or parent, fridge storage, used-in count, rating;
- loading, error and empty states everywhere; the empty state of an empty
  library offers the add button.

Recipe sidebar: course, status, kind, method, equipment, creator, label,
written up / bookmark only. Ingredient sidebar: category tree with counts,
labels, only stubs, only varieties, rating. Notes sidebar: kind, label.

**Recipe page, single reading column:** hero image and thumbnail strip;
course and names; a meta line (servings, time, methods, equipment, storage); a
status control changeable in place; sources as links; other versions; then
ingredients grouped by section, each line linked to its ingredient or
sub-recipe, optional lines greyed; steps grouped by section; notes; and, for a
base, "used in".

**Ingredient page, single column:** header (image, category, names, used-in
count, variety count); description; 挑選; 品種 (children with rating and where
bought); 保存 as a state × method grid; 加熱 with °C and computed °F; links;
used in. A section with nothing in it is hidden; a stub shows its header and a
待補 note linking to the form.

**Forms**, one page per entity, in sections:

- recipe lines: a typeahead over ingredients **and** recipes (names and
  aliases); when nothing matches, 「新增 'xxx'」 makes the line a stub, shown with
  a 待補 marker until saved; amount, note, optional toggle; section picked from
  the recipe's sections or typed; up / down to reorder;
- steps: the same row editor, plus "paste several lines" which splits on
  newlines and strips leading numbering;
- sources, aliases, labels, methods, equipment, serves-as;
- an image gallery picker modelled on media's `ImagePicker`: upload, choose
  from library (unused first), reorder, focus point, remove; every `<img>`
  lazy-loads and applies its focus;
- delete through the existing inline cascade dialog.

**設定** — one page, a section each for ingredient categories (tree), labels,
courses, cooking methods and equipment: add, **rename**, reorder, delete, with
the 409 explanation shown inline when a value is in use. **圖片** — the image
library: grid, unused filter, delete for unused images.

**Merge** — 「合併到…」 on the ingredient page opens a picker, shows the
preview, then merges and navigates to the target.

Known defects fixed along the way: the library ignored `?category=`; ingredient
mutations invalidated only the list query, so detail pages and category counts
stayed stale; `METHODS` duplicated in the form; `className` on `Input` /
`Select` replaced the base classes instead of extending them; `Vocabularies`
showed no error state.

## One-time ingredient import

1. Extract every ingredient name from the recipe doc's ingredient lists.
2. Draft `data/import/ingredients.csv` — `name_cn, name_en, aliases, parent,
   category` — folding prep forms into their base ingredient as aliases
   (蒜末 / 蒜泥 / 蒜片 → 蒜頭), English duplicates into the Chinese row
   (garlic → 蒜頭), and setting obvious parents (柴魚醬油 → 醬油).
3. **The owner reviews the CSV before anything is loaded.**
4. A data migration loads it: every row `needs_detail = true`, categories by
   name from the seeded tree (unknown → 未分類), parents resolved within the
   file. A row whose name already exists is skipped, so the load is idempotent.
   Its downgrade is a deliberate no-op — deleting rows the owner may since have
   edited is worse than leaving them — and says so in its docstring.

The CSV sits in the repository: ingredient names are not sensitive, and the
migration must be able to read it on the box.

## Testing

- Backend tests per new route: create, read, update, delete, and each refusal,
  with every refusal paired with its permitted mirror and its set made
  non-empty (platform "Rule"). Module 1's own CRUD gets HTTP tests too — today
  only its constraint statuses are tested.
- Load-bearing cases named up front: a line naming a missing ingredient is 404;
  a payload claiming a type cannot change the stored one; a two-recipe cycle
  and a self-reference are refused; "used in" counts a recipe once when it uses
  two children of one parent; a stub typed twice in one save is one row;
  merge-preview and merge agree; an attached image refuses deletion and an
  unattached one deletes its files; an upload that is not an image is 422 and
  one over the cap is 413; a re-uploaded identical image returns the same row.
- Image tests point `IMAGE_DIR` at `tmp_path`. The upload code reads the
  setting at call time, never at import time — media's cover route imports its
  directory by value, which is why patching it there does nothing.
- `test_migrations_build_the_schema.py` keeps proving the chain from zero;
  `test_there_is_exactly_one_head` is updated to the new head.
- Frontend: vitest for the pure pieces (URL-state filters, line-editor
  reducer, step paste-splitter, °F conversion, focus parsing), plus the
  existing endpoint and theme-token tests.
- **Done means driven in the running app**: for every entity, add, edit and
  delete performed in a browser against `:8001` after `npm run build`.

## Delivery

Five branches, each off `dev` and merged into `dev` before the next is cut — no
stacking:

1. `feat/ingredient-storage-heating-images` — ingredient changes,
   vocabularies and seeds, the image backend, module 1 CRUD tests, the
   bind mount, `docs/open-items.md`.
2. `feat/recipes` — recipe model, API, stubs, cycle guard, used-in, merge.
3. `feat/kitchen-notes` — kitchen notes backend.
4. `feat/notebook-ui` — the redesign and every page above.
5. `feat/ingredient-import` — CSV (after owner review) and data migration.

Each lands its docs in the same commit as its behaviour: `data-model.md`,
`api.md`, `frontend.md`, `testing.md`, `notes/decisions.md`, and `CLAUDE.md`'s
status section. The manager is asked about file backup before branch 1 merges.
When branch 5 merges, this spec and its plan are deleted in the same change
that moves what survives into `docs/`.
