# Data model

What the database holds today: forty-four tables, at revision `l1abels`.
Module 1's six (`ingredient`, `ingredient_category`, `ingredient_alias`,
`ingredient_preservation`, `label`, `ingredient_label`), the nine managed
vocabularies, `ingredient_heating`, `ingredient_link`, the image library and
its four galleries (`image`, `ingredient_image`, `dish_image`, `recipe_image`,
`kitchen_note_image`), the dish family's four (`dish`, `dish_alias`,
`dish_serves_as`, `dish_label`), the recipe family's eight (`recipe`,
`recipe_method`, `recipe_equipment`, `recipe_source`, `recipe_line_group`,
`recipe_line`, `recipe_step_group`, `recipe_step`), `recipe_template`, kitchen notes' two (`kitchen_note`, `kitchen_note_label`),
`common_ingredient`, the 常用食材 list, TBD's two (`tbd_entry`,
`tbd_link`), 加熱's `heating_note`, and the schedule's three (`schedule_day`, `schedule_meal`,
`schedule_meal_item`).

## Conventions shared by every table

**Integer primary keys**, and the id in the URL is the id in the database.
There is no second public identifier — media has one because its Google Sheets
restore needs to permute ids inside a transaction, and food has no such channel.

**Names are slots, not a single column.** `name_cn` and `name_en` everywhere,
plus `name_alt` on `ingredient` and `dish`. A recipe is the exception: one
optional `name`, falling back to its dish's. At least one must be non-null, enforced by a
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

## `common_ingredient`

常用食材: the ingredients the recipe form offers as one-tap chips above its
材料, in the owner's order. `ingredient_id` is the primary key - an
ingredient is listed once or not at all - and a foreign key to `ingredient`
with `ON DELETE CASCADE`, so a deleted ingredient leaves the list.
`sort_order` (NOT NULL) is the chip's place; the API writes the whole list at
once and numbers it 0, 1, 2 … in the order sent. A merge moves the source's
row to the target in the same place, unless the target is listed already,
when the source's row goes with the source.

## `tbd_entry` and `tbd_link`

TBD: a standalone page of loose notes. Nothing references either table and
neither references anything else - no ingredient, recipe, label or image.

`tbd_entry` has an optional `name` (blank is stored as null), a NOT NULL
`sort_order` - the owner's order on the page, ties falling back to `id`; a new
entry is given the end, and a reorder renumbers every entry 0, 1, 2 … - and
`created_at` / `updated_at`.

`tbd_link` is an entry's links: `entry_id` (indexed, `ON DELETE CASCADE`), a
NOT NULL `position` (the order sent), a NOT NULL `url` and an optional
`label`. `ck_tbd_link_has_a_url` refuses a blank url. The API stores what is
typed as a web address: one with no scheme is given `https://`, and one with a
scheme must be `http` or `https`. A save replaces an entry's links wholesale,
which is why `position` has no unique constraint - one would collide with the
rows being replaced inside the same flush.

**An entry has a name or at least one link.** A CHECK cannot see the child
table, so that rule is the service's (`app/services/tbd.py`), answered as a
422 in the app's error shape.

## `heating_note`

加熱: a standalone page of notes on how to heat or reheat a food. Nothing
references the table and it references nothing - a note names its food in
words, not by pointing at an ingredient or a dish.

A NOT NULL `name` (`ck_heating_note_has_a_name` refuses a blank one), an
optional `body` (free text, line breaks kept; blank is stored as null), a NOT
NULL `sort_order` - the owner's order on the page, as `tbd_entry`'s - and
`created_at` / `updated_at`.

## The managed vocabularies

`recipe_course` (類別), `region` (地區), `recipe_status`, `source_platform`,
`cooking_method`, `equipment`, `author`, `line_group` (材料分組) and
`step_group` (步驟分組) share one shape, declared once
in `VocabularyMixin` (`app/models/vocabulary.py`): `name_cn`, `name_en`,
`sort_order`, at least one name (`ck_<table>_has_a_name`) and a case-insensitive
unique index per name slot with default null handling, as on `ingredient`.

They are tables rather than lists in `app/constants.py` because the owner edits
them: renaming 煮 to 水煮 is one row, not a deploy. The closed lists in
constants are the ones the app's own logic branches on (storage state, rating,
dish kind);
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
| `region` | 台式, 中式, 日式, 韓式, 泰式, 西式 (`d1ishes`), hand-ordered |
| `recipe_status` | 想試, 可煮, 常煮 (`v2ocabulary`) |
| `source_platform` | YouTube, Shorts, 網站, 書, 其他 (`v2ocabulary`) |
| `line_group` | 主料, 配料, 調味料 (`g1roups`) |
| `step_group` | 備料, 烹飪, 醬汁 (`g1roups`) |
| `cooking_method` | 煮, 壓力鍋煮, 煎, 炒, 炸, 氣炸, 烤, 蒸, 川燙, 涼拌, 微波, 混合 |
| `equipment` | 鍋子, 壓力鍋, 平底鍋, 氣炸鍋, 烤箱, 油鍋, 果汁機, 電鍋, 微波爐, 保鮮盒, 碗 |
| `ingredient_category` | 肉類, 海鮮, 蔬菜, 菇類, 水果, 蛋豆製品, 主食穀物, 調味料, 乳製品, 乾貨 (top level) |
| `label` | 飯, 麵, 肉, 麵包, 馬鈴薯, 地瓜, 沙拉, 鍋 — deleted again by `l1abels`, which deletes every label nothing carries |

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
| `recipe_course` | dishes filed in it (`dish.course_id`); serves-as links `CASCADE` and do not count |
| `region` | dishes from it (`dish.region_id`) |
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
`ingredient_image`, `dish_image`, `recipe_image` and `kitchen_note_image`
exist. Media has one
polymorphic table with an `owner_type` and an `owner_id` that nothing
constrains.

| Column | Notes |
| --- | --- |
| `ingredient_id` / `dish_id` / `recipe_id` / `kitchen_note_id` | the owner, `CASCADE` |
| `image_id` | `RESTRICT` |
| `position` | 0 is the cover; unique per owner |
| `focus` | `"X% Y%"` with each 0–100, or null for centred |

The four gallery tables have the same shape. Deleting an owner removes its
gallery rows and never the pictures. An image
that is still attached cannot be deleted: the API answers 409 naming the owners,
and the foreign key is the backstop. `focus` is per attachment, because one
picture may be cropped differently in two galleries. An image may appear once in
a gallery (`uq_<owner>_image_once`) and a position once
(`uq_<owner>_image_position`).

## `dish`

A dish or a sauce in general - 照燒雞腿排, 照燒醬 - whoever cooks it. Its
recipes are the specific ways of making it.

| Column | Notes |
| --- | --- |
| `id` | |
| `name_cn`, `name_en`, `name_alt` | at least one required (`ck_dish_has_a_name`); **not unique** |
| `kind` | `dish` (料理) or `sauce` (醬料) (`DISH_KINDS`), server default `dish` |
| `course_id` | optional, → `recipe_course`, `RESTRICT`, indexed |
| `region_id` | optional, → `region`, `RESTRICT`, indexed |
| `description` | |
| `created_at`, `updated_at` | |

**One table holds both kinds.** A dish and a sauce carry the same fields at
the same level; `kind` files them, so the libraries can be filtered now and
split later without a migration.

**Names are not unique**, unlike every other named table but the recipe's,
and there is no name index: two unrelated recipes of one name became two
dishes of one name when the table was created. A name typed into the recipe
form reuses the oldest dish answering to it exactly (a name slot or an alias,
any case), which keeps the ordinary case to one row.

`dish_alias` is as `ingredient_alias`: anything you might type to find a dish,
never displayed, unique per dish (`uq_dish_alias`) and looked up on
`lower(value)`. `dish_serves_as` (→ `recipe_course`) and `dish_label`
(→ `label`) are link tables keyed on the dish and the other side, `CASCADE`
on both sides, the other side's column indexed on its own. A serves-as link
is a hint, not where the dish is filed, so it never refuses deleting a
course. Its gallery is `dish_image`, above.

## `recipe`

One specific way of making a dish - 照燒雞腿排 as one author makes it.

| Column | Notes |
| --- | --- |
| `id` | |
| `dish_id` | **required**, → `dish`, `RESTRICT`, indexed |
| `name` | optional - what tells this recipe from its dish's others |
| `status_id` | **required**, → `recipe_status`, `RESTRICT`. No server default: a recipe created without one is given the first status in sort order by the write path |
| `servings`, `time` | free text — `2-3 人`, `1hr` |
| `storage_notes`, `notes` | |
| `created_at`, `updated_at` | |

**A recipe's `display_name` is its own `name`, else its dish's display name**
(`Recipe.display_name`, `app/models/recipe.py`). The dish's names, kind,
course, region, labels, serves-as and description are the dish's; a recipe
reads them through `dish_id`.

**Deleting a recipe never deletes its dish**, even the last one: a dish is
worth keeping on its own.

**"Written up" is derived, never stored**: a recipe with at least one line or
step.

## `recipe_method`, `recipe_equipment`

Link tables, each a composite primary key of the recipe and the other side.
The key leads with `recipe_id`, so the other side's column carries its own
index (`ix_<table>_<column>`) for "which recipes use this" and for the
`RESTRICT` check when that row is deleted. The recipe side `CASCADE`s; the
other side - `cooking_method`, `equipment` - is `RESTRICT`.

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
| `sub_dish_id` | → `dish`, `RESTRICT`, indexed — a dish used as an ingredient, usually a 醬料; any `kind` is accepted |
| `amount`, `note` | free text |
| `is_optional` | default false |

**A line names exactly one of `ingredient_id` and `sub_dish_id`**
(`ck_recipe_line_one_target`). Which kind of line it is comes from which column
is set; there is no stored discriminator to disagree with them. A line names
the dish, never one recipe of it: 照燒醬 is used, however it is made.

**A line may not name its own recipe's dish, and dishes may not nest in a
loop** - dish A uses dish B when a recipe of A has a line naming B. A CHECK
sees one row and cannot see the recipe's dish, so both are refused on the
write path.

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

## `recipe_template`

A named skeleton a new recipe starts from: a NOT NULL `name`, refused when
blank (`ck_recipe_template_has_a_name`) and unique whatever its case
(`uq_recipe_template_name`, on `lower(name)`); a NOT NULL `sort_order`, the
owner's order on 設定 and in the new-recipe chooser - a new template is given
the end, and a reorder renumbers every template 0, 1, 2 …, ties falling back
to the name; a NOT NULL JSONB `body`; and `created_at` / `updated_at`.

`body` is one document in the recipe payload's own shapes, always stored in
this canonical form:

```json
{"servings": null, "time": null,
 "lines": [{"ingredient_id": 1, "sub_dish_id": null, "amount": null, "note": null, "is_optional": false}],
 "line_groups": [{"line_group_id": 5, "name": null, "lines": []}],
 "steps": [{"body": "…", "kind": "step"}],
 "step_groups": [{"step_group_id": null, "name": "收尾", "steps": []}],
 "method_ids": [], "equipment_ids": []}
```

A line names exactly one of an ingredient and a dish, and a group exactly one
of a 設定 value and a one-off name, as a recipe's do; a template never names
an ingredient or a dish that does not exist yet.

**Nothing in the body is a foreign key**, and nothing references the table.
An ingredient, a dish, a method, a piece of equipment or a group value a body
names can be deleted without a refusal; the API leaves the missing reference
out when it reads the template, and counts it. An ingredient merge rewrites the
merged ingredient's id to the target's in every body. Why JSONB rather than
tables mirroring the recipe's is in `notes/decisions.md`.

## `schedule_day`, `schedule_meal` and `schedule_meal_item`

The weekly schedule (排程), from the owner's Plan sheet: per calendar date,
the day's plain fields and its four meals, each meal free text and any number
of items.

`schedule_day` is keyed by its `date` (DATE, the primary key). It holds four
marks, each Boolean NOT NULL with a server default of false - `to_buy` (要買?),
`thaw_morning` (早退冰?), `thaw_noon` (中退冰?), `thaw_evening` (晚退冰?) -
and two nullable Text fields, `fruit` (水果) and `note` (備註).

| `schedule_meal` column | Notes |
| --- | --- |
| `id` | |
| `date` | → `schedule_day.date`, `CASCADE` |
| `slot` | `breakfast` 早 / `lunch` 中 / `afternoon` 下午 / `dinner` 晚 (`MEAL_SLOTS`), checked by the API |
| `text` | nullable free text, unrelated to any dish or recipe |

| `schedule_meal_item` column | Notes |
| --- | --- |
| `id` | |
| `meal_id` | → `schedule_meal.id`, `CASCADE`, indexed |
| `position` | the item's place in its meal, from 0; unique per meal (`uq_schedule_meal_item_position`) |
| `dish_id` | required, → `dish`, `RESTRICT`, indexed |
| `recipe_id` | optional, → `recipe`, `SET NULL`, indexed |

One meal per slot per date (`uq_schedule_meal_slot`). **A date with nothing
planned has no row, and neither does an empty meal**: the API answers every
date in a range and fills the missing ones, and a save that empties a meal or
a whole day deletes the row. So `schedule_day` never holds a row with every
mark false and both texts null and no meal, and `schedule_meal` never holds
one with no text and no item.

**An item's recipe is one of its dish's recipes, and a meal holds a given
dish and recipe once.** The first rule spans two tables and the second
treats a NULL recipe as a value, so neither is a constraint; the service
enforces both, and fills the dish from the recipe when only the recipe is
sent. The same dish may appear twice in a meal with two different recipes.
An item names a dish and a recipe, it owns neither: the dish is `RESTRICT`,
so a scheduled dish cannot be deleted from under the plan, and the recipe is
`SET NULL`, so deleting one way of making the dish leaves the item saying
which dish was planned.

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

## `label`, `ingredient_label`, `dish_label` and `kitchen_note_label`

Cross-cutting tags — 辛, 素, 常備, 貴. A label is not a category: a category
says where a thing sits in one taxonomy and every ingredient has exactly one, a
label says something that cuts across the tree and an ingredient may carry any
number or none. A recipe has no labels of its own: it shows its dish's.

Labels have two name slots, not three; a tag has no formal alternative form.

**Every label belongs to exactly one library**: `label.scope`, a NOT NULL
String holding one of `LABEL_SCOPES` in `app/constants.py` - `ingredient`,
`dish` or `note` - with no default, since a label is always added inside the
library it is for. It is a String validated by the API, not a Postgres enum,
as every closed list here. **`uq_label_name_cn` and `uq_label_name_en` are
unique on `(scope, lower(name))`**, so 辣 may be an ingredient label and a
dish label at once, and not two ingredient labels. Like every name index
here they are NULLS DISTINCT: any number of labels may have no English name.

The database does not know which link table goes with which scope. The API
keeps a link inside its label's library: an owner refuses a label of another
scope, and a label in use cannot change scope (`docs/api.md`, "Labels").
`l1abels` scoped the labels that existed by the one library linking each,
deleted the ones nothing linked, and refused to run on a label two libraries
shared.

## Deletion, and why it differs per relationship

| Relationship | Behaviour |
| --- | --- |
| ingredient → its aliases, preservation rows, heating rows, links, label links, gallery rows | `CASCADE` |
| ingredient → its 常用食材 row | `CASCADE` |
| ingredient → its children | `RESTRICT` |
| ingredient → the recipe lines that name it | `RESTRICT` |
| category → its ingredients and child categories | `RESTRICT` |
| dish → its aliases, gallery rows, and serves-as and label links | `CASCADE` |
| dish → its recipes | `RESTRICT` |
| dish → the recipe lines that name it | `RESTRICT` |
| recipe → its sources, line and step groups, lines, steps, gallery rows, and method and equipment links | `CASCADE` |
| recipe → its dish | none — deleting a recipe leaves the dish |
| schedule day → its meals | `CASCADE` |
| schedule meal → its items | `CASCADE` |
| dish → the meal items on the schedule that name it | `RESTRICT` |
| recipe → the meal items on the schedule that name it | `SET NULL` — the item keeps its dish |
| recipe template → what its body names | none — not a foreign key; a missing reference is left out when the template is read |
| line or step group → the lines or steps in it | `SET NULL` — they become ungrouped |
| kitchen note → its label links and gallery rows | `CASCADE` |
| TBD entry → its links | `CASCADE` |
| course or region → the dishes filed in it | `RESTRICT` |
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
are not listed. Nutrition (the 零食 sheet) is a later module and is not
modelled yet.

Only the ingredient names were imported (`i3import`, above); recipes and the
sheets' storage, selection, heating and fruit rows are entered through the
pages.

| Reference | Column / feature | Lands in |
| --- | --- | --- |
| Recipe doc | title, `(YT 詹姆士)` suffix | `dish.name_cn`, `recipe.name` when one dish has several; source platform + author |
| Recipe doc | `Link:` (sometimes two) | `recipe_source` rows |
| Recipe doc | `人數` | `recipe.servings` |
| Recipe doc | ingredient list, amounts | `recipe_line` (ingredient link + `amount`) |
| Recipe doc | ingredient groups (漢堡醬, 調味料, for soup) | `recipe_line_group` (a `line_group` value or a one-off name) |
| Recipe doc | `optional`, `自由添加`, `可省` | `recipe_line.is_optional` |
| Recipe doc | `米酒or清酒`, `味醂可代替糖` | `recipe_line.note` |
| Recipe doc | a sauce used inside a dish (蚵仔煎醬) | `dish.kind = sauce`, named by `recipe_line.sub_dish_id` |
| Recipe doc | `Steps for 備料 / 醬汁備料 / cooking / noodles` | `recipe_step_group` (a `step_group` value or a one-off name) |
| Recipe doc | `* tips`, `Notes:`, unit conversions inside a recipe | `recipe.notes` |
| Recipe doc | `保存期限約3天`, `放涼再裝, 冰冰箱保存` | `recipe.storage_notes` |
| Recipe doc | section headers 主食 / 配菜 / 湯 / 小吃 / 甜點 / 飲料 / 醬料 | `dish.course_id` |
| Recipe sheets | 品項 | `dish.name_cn` |
| Recipe sheets | first column (飯 / 麵 / 肉 / 麵包 …) | dish labels |
| Recipe sheets | 烹調方式 | `recipe_method` → `cooking_method` |
| Recipe sheets | 器具 | `recipe_equipment` → `equipment` |
| Recipe sheets | 來源 (YT / shorts / website / book), creator, URL | `recipe_source` → `source_platform`, `author` |
| Recipe sheets | 可當主食 / 可當配菜 / 可當點心 | `dish_serves_as` → `recipe_course` |
| Recipe sheets | Recipe O / X | derived: has lines or steps ("written up" vs 書籤) |
| Recipe sheets | 備註, `冷藏: 1 week`, `包含醬` | `recipe.notes` / `recipe.storage_notes` / a line naming a sauce |
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
| Plan sheet | 星期幾 (星期六 … 星期五, this week and 下星期 next) | `schedule_day.date` — a real date; weeks run Saturday to Friday |
| Plan sheet | 要買?, 早退冰?, 中退冰?, 晚退冰? | `schedule_day.to_buy`, `thaw_morning`, `thaw_noon`, `thaw_evening` — true or false, not the sheet's text |
| Plan sheet | 水果, 備註 | `schedule_day.fruit`, `note` |
| Plan sheet | 早, 中, 下午, 晚 | `schedule_meal` (one row per slot: free text) and its `schedule_meal_item`s (each a dish, optionally a recipe of it) |
| Plan sheet | `-` (nothing planned) | no row |
| — | photographs | image library + per-owner galleries |
