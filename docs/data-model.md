# Data model

What the database holds today: thirteen tables, at revision `m1images`. Module
1's six (`ingredient`, `ingredient_category`, `ingredient_alias`,
`ingredient_preservation`, `label`, `ingredient_label`), the three managed
vocabularies, `ingredient_heating`, `ingredient_link`, and the two image
tables.

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

`recipe_course`, `cooking_method` and `equipment` share one shape, declared once
in `VocabularyMixin` (`app/models/vocabulary.py`): `name_cn`, `name_en`,
`sort_order`, at least one name (`ck_<table>_has_a_name`) and a case-insensitive
unique index per name slot with default null handling, as on `ingredient`.

They are tables rather than lists in `app/constants.py` because the owner edits
them: renaming 煮 to 水煮 is one row, not a deploy. The closed lists in
constants are the ones the app's own logic branches on (storage state, rating);
these are the ones it only displays and filters by.

**The migration seeds them, and the ingredient categories and labels with
them:**

| Table | Seeded rows |
| --- | --- |
| `recipe_course` | 主食, 配菜, 湯, 小吃點心, 甜點, 飲料, 醬料 |
| `cooking_method` | 煮, 壓力鍋煮, 煎, 炒, 炸, 氣炸, 烤, 蒸, 川燙, 涼拌, 微波, 混合 |
| `equipment` | 鍋子, 壓力鍋, 平底鍋, 氣炸鍋, 烤箱, 油鍋, 果汁機, 電鍋, 微波爐, 保鮮盒, 碗 |
| `ingredient_category` | 肉類, 海鮮, 蔬菜, 菇類, 水果, 蛋豆製品, 主食穀物, 調味料, 乳製品, 乾貨 (top level) |
| `label` | 飯, 麵, 肉, 麵包, 馬鈴薯, 地瓜, 沙拉, 鍋 |

Seeded rows are ordinary rows. Every seed insert is `ON CONFLICT DO NOTHING`, so
a database where the owner already typed 肉類 or 飯 keeps that row untouched.

`cooking_method` is referenced by `ingredient_heating` today. `recipe_course` and
`equipment` have no referent until recipes exist, and report a usage count of
zero.

## `image` and `ingredient_image`

`image` is the library: one row per stored picture. `checksum` is the SHA-256 of
the *normalised* JPEG and is unique (`uq_image_checksum`), so identical pixels
are one row. `storage_key` and `thumb_key` are paths under the image directory
(`library/<sha256>.jpg`, `library/thumbs/<sha256>.jpg`), alongside
`original_filename`, `byte_size`, `width`, `height` and `uploaded_at`. The
pixels are on disk, not in the database.

**A gallery is a join table per owner type, with real foreign keys.**
`ingredient_image` is the first; recipes and kitchen notes will each add their
own. Media has one polymorphic table with an `owner_type` and an `owner_id` that
nothing constrains.

| Column | Notes |
| --- | --- |
| `ingredient_id` | `CASCADE` |
| `image_id` | `RESTRICT` |
| `position` | 0 is the cover; unique per ingredient |
| `focus` | `"X% Y%"` with each 0–100, or null for centred |

Deleting an ingredient removes its gallery rows and never the pictures. An image
that is still attached cannot be deleted: the API answers 409 naming the owners,
and the foreign key is the backstop. `focus` is per attachment, because one
picture may be cropped differently in two galleries. An image may appear once in
a gallery (`uq_ingredient_image_once`) and a position once
(`uq_ingredient_image_position`).

## `label` and `ingredient_label`

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
| category → its ingredients and child categories | `RESTRICT` |
| cooking method → the heating rows that use it | `RESTRICT` |
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
