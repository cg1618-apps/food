# Data model

What the database holds today: thirty-three tables, at revision `s1tepkinds`.
Module 1's six (`ingredient`, `ingredient_category`, `ingredient_alias`,
`ingredient_preservation`, `label`, `ingredient_label`), the eight managed
vocabularies, `ingredient_heating`, `ingredient_link`, the image library and
its three galleries (`image`, `ingredient_image`, `recipe_image`,
`kitchen_note_image`), the recipe family's eleven (`recipe`, `recipe_alias`,
`recipe_serves_as`, `recipe_label`, `recipe_method`, `recipe_equipment`,
`recipe_source`, `recipe_line_group`, `recipe_line`, `recipe_step_group`,
`recipe_step`), and kitchen notes' two (`kitchen_note`, `kitchen_note_label`).

## Conventions shared by every table

**Integer primary keys**, and the id in the URL is the id in the database.
There is no second public identifier — media has one because its Google Sheets
restore needs to permute ids inside a transaction, and food has no such channel.

**Names are slots, not a single column.** `name_cn` and `name_en` everywhere,
plus `name_alt` on `ingredient`. At least one must be non-null, enforced by a
`ck_<table>_has_a_name` CHECK using `num_nonnulls`.

**`name_cn` leads display**, then `name_en`, then `name_alt`. The rule lives in
`NameFallbackMixin` (`app/models/base.py`) and there is no per-row override
column.

**Unique name indexes are on `lower(<column>)` and use Postgres's default null
handling.** Any number of rows may leave a name slot empty; no two may share a
non-null value in one slot. This is the opposite of what a *multi-column* name
constraint needs, and the distinction is the easy one to get wrong — see
`docs/notes/decisions.md`.

**Timestamps are naive Taipei wall clock** via `get_taipei_now`, Python-side
defaults only, no `server_default`.

**Closed vocabularies are `String` columns validated against a Python list** in
`app/constants.py`. No Postgres `ENUM` types anywhere.

## `ingredient`

One thing you cook with.

| Column | Notes |
| --- | --- |
| `id` | |
| `name_cn`, `name_en`, `name_alt` | at least one required |
| `category_id` | **required**, `RESTRICT` |
| `parent_id` | optional self-reference, `RESTRICT` |
| `description` | what it is |
| `selection_notes` | how to pick a good one |
| `sourcing_notes` | where to get it |
| `preservation_notes` | keeping advice tied to no single method |
| `needs_detail` | the to-do flag |
| `rating` | optional grade, one of S, A, B, C, D |
| `created_at`, `updated_at` | |

**A parent ingredient is an ordinary ingredient.** 醬油 has 生抽 and 老抽
beneath it, and is itself stockable, cookable, and citable on a recipe line.
There is no "this row is only a container" flag because there are no
containers. The column exists so that a recipe line may name either level, and
so that "what can I cook" can resolve between them in both directions.

**`name_alt` is a formal alternative worth showing** — another script, a
romanisation. Anything you would merely *type* to find the row is an alias and
belongs in `ingredient_alias`. Without that line the two hold the same strings.

**`needs_detail` is explicit, never derived from "has no notes".** Salt needs no
selection guide and must be able to say so.

**`rating` grades one variety**, mostly a child — 愛文芒果 under 芒果 — and is
validated against `RATINGS` in `app/constants.py`. It is a `String`, like every
closed list here, so the grades are a one-line edit.

## `ingredient_category`

A tree, of unbounded depth. An ingredient may point at any node, not only a
leaf — you often know a thing is 醬油 without knowing which sub-type, and
demanding a leaf means inventing 其他 nodes under every branch.

There is no CHECK preventing cycles; that needs a recursive query and lives on
the write path.

**Exactly one row sets `is_fallback`**, enforced by a partial unique index.
That row is seeded by the migration as 未分類 / Uncategorised, and it is what
lets `ingredient.category_id` be `NOT NULL` without a required category
interrupting recipe writing to ask a taxonomy question. Stubs are filed there
and appear in the tidy-up pass alongside `needs_detail`.

**Sibling names are unique on `coalesce(parent_id, 0)` and `lower(name_cn)`,
where `name_cn` is not null.** The `coalesce` is load-bearing: a null parent
means "top level", and without it two root categories sharing a name would not
collide at all.

**A category's own category is never inherited by a child ingredient.** The
form may pre-fill it; the stored value is the row's own. Inheritance would mean
re-parenting an ingredient silently re-files it.

## `ingredient_alias`

Anything you might type to find an ingredient. Never displayed.

A child table rather than an array or JSON column, so it can be indexed, joined
and constrained — media records replacing list-in-a-column with a real table
twice as a regret.

**Uniqueness is per ingredient, not global.** Two different ingredients may
legitimately answer to overlapping strings; a global constraint would refuse the
second at the moment of typing it. A likely duplicate is warned about, not
refused.

## `ingredient_preservation`

One row per *state* and *way* of keeping the thing: 未使用 冷藏 3–5 天, 已開封
冷藏 1–2 天, 熟食 冷凍 2–3 個月, 乾燥 with no time given.

`state` is `unused`, `opened` or `cooked` (`PRESERVATION_STATES`), defaulting to
`unused`. It exists because the same method lasts different lengths depending on
whether the thing has been opened, cut or cooked.

**The time is a range, and both ends are optional.** `duration_min_days` and
`duration_max_days` are each null or positive
(`ck_ingredient_preservation_duration_positive`), and when both are set the
minimum may not exceed the maximum (`ck_ingredient_preservation_duration_order`).
A row with only a maximum is "up to 3 days"; a row with neither is a note such as
"see the date".

Module 1 stored one typical number and put a range in `notes`. That was
reversed because the reference sheets state a range in almost every row, so a
single number would have been invented. See `docs/notes/decisions.md`.

**Unique on `(ingredient_id, state, method)`**
(`uq_ingredient_preservation_state_method`). The same method may appear once per
state; two 冷藏 rows for the same state are refused.

## `ingredient_heating`

How to heat or cook one ingredient quickly: a method, a temperature, a time.
Many rows per ingredient, ordered by `sort_order`.

| Column | Notes |
| --- | --- |
| `method_id` | `cooking_method`, **required**, `RESTRICT` |
| `temperature_c` | optional, positive |
| `duration` | free text — "8–10 分鐘" is not a number |
| `preheat`, `flip` | booleans |
| `notes` | |

**Not unique on method**: a sausage may be air-fried two ways. **Temperature is
stored in Celsius only**; Fahrenheit is computed in the response, because two
stored temperatures can disagree and one cannot.

## `ingredient_link`

A reference link — where the advice came from. `url` is required and the API
accepts `http` and `https` only, because a `javascript:` URL rendered as a link
is script execution. `title` is optional; rows are ordered by `sort_order`.

## The managed vocabularies

`recipe_course`, `recipe_status`, `source_platform`, `cooking_method`,
`equipment`, `author`, `line_group` (材料分組) and `step_group` (步驟分組)
share one shape, declared once
in `VocabularyMixin` (`app/models/vocabulary.py`): `name_cn`, `name_en`,
`sort_order`, at least one name (`ck_<table>_has_a_name`) and a case-insensitive
unique index per name slot with default null handling, as on `ingredient`.

They are tables rather than lists in `app/constants.py` because the owner edits
them: renaming 煮 to 水煮 is one row, not a deploy. The closed lists in
constants are the ones the app's own logic branches on (storage state, rating);
these are the ones it only displays and filters by.

**`author` is listed by name, not by hand.** Every author has `sort_order` 0,
so the shared (sort_order, name) order is name order. It grows from the recipe
form as well as from 設定: a name typed into a source that no author answers
to is created by the save (`docs/api.md`). It is not seeded; `a1uthors` filled
it from the free-text `recipe_source.creator` it replaced — one author per
distinct creator, trimmed and compared case-insensitively, the spelling of the
first source saved kept, and a name containing Han characters, kana or Hangul
filed as `name_cn`, anything else as `name_en`.

**The migration seeds them, and the ingredient categories and labels with
them:**

| Table | Seeded rows |
| --- | --- |
| `recipe_course` | 主食, 配菜, 湯, 小吃點心, 甜點, 飲料, 醬料 |
| `recipe_status` | 想試, 可煮, 常煮 (`v2ocabulary`) |
| `source_platform` | YouTube, Shorts, 網站, 書, 其他 (`v2ocabulary`) |
| `line_group` | 主料, 配料, 調味料 (`g1roups`) |
| `step_group` | 備料, 烹飪, 醬汁 (`g1roups`) |
| `cooking_method` | 煮, 壓力鍋煮, 煎, 炒, 炸, 氣炸, 烤, 蒸, 川燙, 涼拌, 微波, 混合 |
| `equipment` | 鍋子, 壓力鍋, 平底鍋, 氣炸鍋, 烤箱, 油鍋, 果汁機, 電鍋, 微波爐, 保鮮盒, 碗 |
| `ingredient_category` | 肉類, 海鮮, 蔬菜, 菇類, 水果, 蛋豆製品, 主食穀物, 調味料, 乳製品, 乾貨 (top level) |
| `label` | 飯, 麵, 肉, 麵包, 馬鈴薯, 地瓜, 沙拉, 鍋 |

Seeded rows are ordinary rows. Every seed insert is `ON CONFLICT DO NOTHING`, so
a database where the owner already typed 肉類 or 飯 keeps that row untouched.

### The starting ingredient list

**The first ingredients come from the owner's recipe document**, not from
typing. `i3import` loads `alembic/import/ingredients.csv` — 194 names drawn
from that document's ingredient lists and approved by the owner — as stubs:
every row it inserts has `needs_detail` true and carries only its names, its
aliases (120 across the file), its category and its parent. Notes, storage and
pictures are filled in afterwards, through the 待補 backlog.

The file's header is `name_cn,name_en,aliases,parent,category`. Aliases are
`|`-separated; `parent` names another row of the file; `category` is one of the
seeded top-level categories above, matched by name, and an empty one — or one
the owner has since renamed — files the row in the fallback category 未分類.

The load leaves what is already there alone. A row is skipped when its name_cn
or name_en matches, case-insensitively, any existing ingredient's name slot or
alias, and no existing row is modified. A skipped row's existing twin still
becomes the parent of the file's rows beneath it. A parent link that would
point at itself or close a cycle is not made.

Once loaded, the rows are ordinary data; the CSV is not read again by anything
but a fresh database's migration chain.

**A value's usage count is the number of `RESTRICT` references to it** — the
things that would stop it being deleted:

| Vocabulary | Counted |
| --- | --- |
| `recipe_course` | recipes filed in it (`recipe.course_id`); serves-as links `CASCADE` and do not count |
| `recipe_status` | recipes in it (`recipe.status_id`) |
| `source_platform` | sources naming it (`recipe_source.platform_id`) — two sources from one book count twice |
| `cooking_method` | `ingredient_heating` rows plus `recipe_method` links |
| `equipment` | `recipe_equipment` links |
| `author` | sources naming them (`recipe_source.author_id`) — counted as a platform's are |
| `line_group`, `step_group` | recipe groups naming the value (`recipe_line_group.line_group_id`, `recipe_step_group.step_group_id`) — at most one per recipe |

## `image` and its galleries

`image` is the library: one row per stored picture. `checksum` is the SHA-256 of
the *normalised* JPEG and is unique (`uq_image_checksum`), so identical pixels
are one row. `storage_key` and `thumb_key` are paths under the image directory
(`library/<sha256>.jpg`, `library/thumbs/<sha256>.jpg`), alongside
`original_filename`, `byte_size`, `width`, `height` and `uploaded_at`. The
pixels are on disk, not in the database.

**A gallery is a join table per owner type, with real foreign keys.**
`ingredient_image`, `recipe_image` and `kitchen_note_image` exist. Media has one
polymorphic table with an `owner_type` and an `owner_id` that nothing
constrains.

| Column | Notes |
| --- | --- |
| `ingredient_id` / `recipe_id` / `kitchen_note_id` | the owner, `CASCADE` |
| `image_id` | `RESTRICT` |
| `position` | 0 is the cover; unique per owner |
| `focus` | `"X% Y%"` with each 0–100, or null for centred |

The three gallery tables have the same shape. Deleting an owner removes its
gallery rows and never the pictures. An image
that is still attached cannot be deleted: the API answers 409 naming the owners,
and the foreign key is the backstop. `focus` is per attachment, because one
picture may be cropped differently in two galleries. An image may appear once in
a gallery (`uq_<owner>_image_once`) and a position once
(`uq_<owner>_image_position`).

## `recipe`

One recipe: a dish, or a base — a sauce, a stock, a dough — cooked to be used
inside other recipes.

| Column | Notes |
| --- | --- |
| `id` | |
| `name_cn`, `name_en`, `name_alt` | at least one required (`ck_recipe_has_a_name`); **not unique** |
| `kind` | `dish` or `base` (`RECIPE_KINDS`), default `dish` |
| `course_id` | optional, → `recipe_course`, `RESTRICT` |
| `variant_of_id` | optional, → `recipe`, `SET NULL` |
| `status_id` | **required**, → `recipe_status`, `RESTRICT`. No server default: a recipe created without one is given the first status in sort order by the write path |
| `servings`, `time` | free text — `2-3 人`, `1hr` |
| `description`, `storage_notes`, `notes` | |
| `created_at`, `updated_at` | |

**Names are not unique**, unlike every other named table here, and there is no
name index: versions of one dish share its name.

**`variant_of_id` makes a recipe a version of another.** A recipe may not be a
version of itself (`ck_recipe_not_its_own_version`). Versions are one level
deep — a version has no versions and does not point at one — which needs
another row to check and so lives on the write path. Deleting the original
leaves its versions standing with `variant_of_id` cleared, because each is a
complete recipe in its own right.

**"Written up" is derived, never stored**: a recipe with at least one line or
step.

## `recipe_alias`

As `ingredient_alias`: anything you might type to find a recipe, never
displayed, unique per recipe (`uq_recipe_alias`) and looked up on
`lower(value)`.

## `recipe_serves_as`, `recipe_label`, `recipe_method`, `recipe_equipment`

Link tables, each a composite primary key of the recipe and the other side.
The key leads with `recipe_id`, so the other side's column carries its own
index (`ix_<table>_<column>`) for "which recipes use this" and for the
`CASCADE` or `RESTRICT` check when that row is deleted. The recipe side always
`CASCADE`s. The other side differs:

| Table | Other side |
| --- | --- |
| `recipe_serves_as` | `recipe_course`, `CASCADE` — the other courses a dish can stand in for |
| `recipe_label` | `label`, `CASCADE`, as `ingredient_label` |
| `recipe_method` | `cooking_method`, `RESTRICT` |
| `recipe_equipment` | `equipment`, `RESTRICT` |

A serves-as link may repeat the recipe's own course.

## `recipe_source`

Where the recipe came from. `platform_id` is required (→ `source_platform`,
`RESTRICT`); `author_id` (→ `author`, `RESTRICT`, indexed), `url` and `title`
are each optional — a book has no URL, a page may have no author worth
naming — but at least one must be set (`ck_recipe_source_has_content`).
Ordered by `sort_order`.

## `recipe_line_group` and `recipe_step_group`

One group of a recipe's ingredient lines (主料, 醬汁) or of its steps (備料,
烹飪): a real row, not a label repeated on each line, so a group exists on its
own — an empty one is kept — has its own place, and is renamed in one place.

| Column | Notes |
| --- | --- |
| `recipe_id` | the owner, `CASCADE` |
| `position` | the group's place among the recipe's groups, unique per recipe (`uq_recipe_line_group_position`, `uq_recipe_step_group_position`) |
| `line_group_id` / `step_group_id` | → `line_group` / `step_group`, `RESTRICT`, indexed — the 設定 value the group is |
| `name` | a one-off name, for a group that is no 設定 value |

**Exactly one of the value and `name` is set** (`ck_recipe_line_group_one_name`,
`ck_recipe_step_group_one_name`); the write path stores a name matching a
value — trimmed, either name slot, any case — as that value. **A recipe holds
a group once**: unique on `(recipe_id, value)` (`uq_recipe_line_group_value`,
`uq_recipe_step_group_value`), and on `(recipe_id, lower(name))`
(`uq_recipe_line_group_name`, `uq_recipe_step_group_name`). Both are NULLS
DISTINCT, so the rows using the other arm never collide on the null. A
group's `display_name` is the value's, else its `name`.

## `recipe_line`

One ingredient line.

| Column | Notes |
| --- | --- |
| `recipe_id` | the owner, `CASCADE` |
| `position` | required, unique per recipe (`uq_recipe_line_position`); runs through the whole recipe in display order — the ungrouped lines, then group by group |
| `group_id` | → `recipe_line_group`, `SET NULL`, indexed; null is ungrouped |
| `ingredient_id` | → `ingredient`, `RESTRICT` |
| `sub_recipe_id` | → `recipe`, `RESTRICT` — another recipe used as an ingredient, usually a base; any `kind` is accepted |
| `amount`, `note` | free text |
| `is_optional` | default false |

**A line names exactly one of `ingredient_id` and `sub_recipe_id`**
(`ck_recipe_line_one_target`). Which kind of line it is comes from which column
is set; there is no stored discriminator to disagree with them.

**A line may not name its own recipe** (`ck_recipe_line_not_itself`). Longer
cycles through nested recipes need a recursive query and are refused on
the write path.

The same ingredient may appear on two lines — once for the meat, once for the
sauce — so nothing is unique on it.

**A line's group belongs to the same recipe.** The write path only ever
builds them together; a single-column foreign key cannot say so, and a
composite one could not be `SET NULL` without nulling `recipe_id` with it.

## `recipe_step`

One step of the method: `position` (unique per recipe,
`uq_recipe_step_position`, running through the recipe as a line's does),
`group_id` (→ `recipe_step_group`, `SET NULL`, null is ungrouped), `kind`
and a required `body`.

`kind` is a `String NOT NULL`, server default `'step'`, validated by the API
against `STEP_KINDS` in `app/constants.py` rather than by a Postgres enum:
`step` (步驟, an ordinary step), `optional` (可省略, one that may be skipped)
or `note` (備註, a note among the steps). Only a `step` is numbered, so a
step's number is not its position plus one; it is counted by whoever draws
the steps and never stored (`s1tepkinds`).

## `kitchen_note`

A bookmark to something worth keeping that is not a recipe: a compilation video
of twenty dishes, one technique, a page to look things up in.

| Column | Notes |
| --- | --- |
| `title` | `NOT NULL`, and not blank once trimmed (`ck_kitchen_note_has_a_title`). Not unique |
| `kind` | `compilation` / `technique` / `reference` (`KITCHEN_NOTE_KINDS`, shown 合輯 / 技巧 / 參考); server default `reference` |
| `url` | nullable; http or https only, checked by the API |
| `body` | nullable free text |
| `created_at`, `updated_at` | as every table |

A note has one title, not the name slots a catalogue entity has: nothing will
ever look one up by an English name it does not have. Its `display_name` - what
an image's owner list shows - is the title.

`kitchen_note_label` links labels, both sides `CASCADE`, with `label_id`
indexed on its own. Its gallery is `kitchen_note_image`, above.

## `label`, `ingredient_label`, `recipe_label` and `kitchen_note_label`

Cross-cutting tags — 辛, 素, 常備, 貴. A label is not a category: a category
says where a thing sits in one taxonomy and every ingredient has exactly one, a
label says something that cuts across the tree and an ingredient may carry any
number or none.

Labels have two name slots, not three; a tag has no formal alternative form.

## Deletion, and why it differs per relationship

| Relationship | Behaviour |
| --- | --- |
| ingredient → its aliases, preservation rows, heating rows, links, label links, gallery rows | `CASCADE` |
| ingredient → its children | `RESTRICT` |
| ingredient → the recipe lines that name it | `RESTRICT` |
| category → its ingredients and child categories | `RESTRICT` |
| recipe → its aliases, sources, line and step groups, lines, steps, gallery rows, and serves-as, label, method and equipment links | `CASCADE` |
| line or step group → the lines or steps in it | `SET NULL` — they become ungrouped |
| recipe → the lines in other recipes that name it as a base | `RESTRICT` |
| recipe → its versions | `SET NULL` |
| kitchen note → its label links and gallery rows | `CASCADE` |
| course → the recipes filed in it | `RESTRICT` |
| status → the recipes in it; source platform or author → the sources naming it | `RESTRICT` |
| course → its serves-as links; label → any link | `CASCADE` |
| cooking method → the heating rows and recipe links that use it | `RESTRICT` |
| equipment → the recipe links that use it | `RESTRICT` |
| 材料分組 or 步驟分組 value → the recipe groups naming it | `RESTRICT` |
| image → the gallery rows that attach it | `RESTRICT` |

The asymmetry is the point and it is the kind that reads as uniform: an alias
has no life without its ingredient, but a child ingredient does, a category
full of ingredients is not something to empty by accident, and a photograph
outlives any one place it was shown. The cascade runs from the owner down to the
gallery row and stops there; the picture and its file stay in the library.

**The ORM must not undo this.** Relationships across a `RESTRICT` foreign key
set `passive_deletes="all"`, because SQLAlchemy otherwise nulls the child's
foreign key before issuing the DELETE and the database never gets to refuse.
A delete the schema forbids then succeeds through the ORM and fails only
through raw SQL.

## Where the owner's references land

The owner kept recipes in a Google Doc and kitchen knowledge in Google Sheets
before this app existed. Every column in those references has a home here, so
entering them is typing, not designing. Columns that were empty in every row
are not listed. Nutrition (the 零食 sheet) and the weekly schedule (the Plan
sheet) are later modules and are not modelled yet.

Only the ingredient names were imported (`i3import`, above); recipes and the
sheets' storage, selection, heating and fruit rows are entered through the
pages.

| Reference | Column / feature | Lands in |
| --- | --- | --- |
| Recipe doc | title, `(YT 詹姆士)` suffix | `recipe.name_cn`; source platform + author |
| Recipe doc | `Link:` (sometimes two) | `recipe_source` rows |
| Recipe doc | `人數` | `recipe.servings` |
| Recipe doc | ingredient list, amounts | `recipe_line` (ingredient link + `amount`) |
| Recipe doc | ingredient groups (漢堡醬, 調味料, for soup) | `recipe_line_group` (a `line_group` value or a one-off name) |
| Recipe doc | `optional`, `自由添加`, `可省` | `recipe_line.is_optional` |
| Recipe doc | `米酒or清酒`, `味醂可代替糖` | `recipe_line.note` |
| Recipe doc | a sauce used inside a dish (蚵仔煎醬) | `recipe.kind = base`, nested via `recipe_line.sub_recipe_id` |
| Recipe doc | `Steps for 備料 / 醬汁備料 / cooking / noodles` | `recipe_step_group` (a `step_group` value or a one-off name) |
| Recipe doc | `* tips`, `Notes:`, unit conversions inside a recipe | `recipe.notes` |
| Recipe doc | `保存期限約3天`, `放涼再裝, 冰冰箱保存` | `recipe.storage_notes` |
| Recipe doc | section headers 主食 / 配菜 / 湯 / 小吃 / 甜點 / 飲料 / 醬料 | `recipe.course_id` |
| Recipe sheets | 品項 | `recipe.name_cn` |
| Recipe sheets | first column (飯 / 麵 / 肉 / 麵包 …) | recipe labels |
| Recipe sheets | 烹調方式 | `recipe_method` → `cooking_method` |
| Recipe sheets | 器具 | `recipe_equipment` → `equipment` |
| Recipe sheets | 來源 (YT / shorts / website / book), creator, URL | `recipe_source` → `source_platform`, `author` |
| Recipe sheets | 可當主食 / 可當配菜 / 可當點心 | `recipe_serves_as` → `recipe_course` |
| Recipe sheets | Recipe O / X | derived: has lines or steps ("written up" vs 書籤) |
| Recipe sheets | 備註, `冷藏: 1 week`, `包含醬` | `recipe.notes` / `recipe.storage_notes` / a nested base |
| Recipe sheets | 語言 | not modelled — empty in every row |
| 合輯, Tips sheets | title, creator, URL | `kitchen_note` (kind 合輯 / 技巧 / 參考) |
| 可煮 sheet | dish, time | `recipe.status_id` → 可煮, `recipe.time` |
| 保存期限 sheet | Unused / Opened × 常溫 / Fridge / Freeze, how-to, source | `ingredient_preservation` (state, method, range, notes) + `ingredient_link` |
| 保存期限 sheet | 熟肉 rows | `ingredient_preservation.state = cooked` |
| 挑選 sheet | criteria columns, source | `ingredient.selection_notes` + `ingredient_link` |
| 加熱 sheet | Item, Method, 預熱, 翻面, °C, °F, Time | `ingredient_heating` (°F derived) |
| Fruit sheet | Item / Specific Item | parent / child ingredient |
| Fruit sheet | Rating (S / A / B) | `ingredient.rating` |
| Fruit sheet | Buy Source, Remark | `ingredient.sourcing_notes`, `ingredient.description` |
| — | photographs | image library + per-owner galleries |
