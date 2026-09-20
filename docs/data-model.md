# Data model

What the database holds today. Six tables, all of them module 1's.

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

One row per *way* of keeping the thing: 冷藏 21 天, 冷凍 90 天, 乾燥 with no
time given. Unique on `(ingredient_id, method)`.

`duration_days` is a single typical number and must be positive or null. A
range goes in `notes` ("3–5 天, less once cut"): the integer is what a future
"what is about to go off" view can compute with, the prose is what is actually
true.

## `label` and `ingredient_label`

Cross-cutting tags — 辛, 素, 常備, 貴. A label is not a category: a category
says where a thing sits in one taxonomy and every ingredient has exactly one, a
label says something that cuts across the tree and an ingredient may carry any
number or none.

Labels have two name slots, not three; a tag has no formal alternative form.

## Deletion, and why it differs per relationship

| Relationship | Behaviour |
| --- | --- |
| ingredient → its aliases, preservation rows, label links | `CASCADE` |
| ingredient → its children | `RESTRICT` |
| category → its ingredients and child categories | `RESTRICT` |

The asymmetry is the point and it is the kind that reads as uniform: an alias
has no life without its ingredient, but a child ingredient does, and a category
full of ingredients is not something to empty by accident.

**The ORM must not undo this.** Relationships across a `RESTRICT` foreign key
set `passive_deletes="all"`, because SQLAlchemy otherwise nulls the child's
foreign key before issuing the DELETE and the database never gets to refuse.
A delete the schema forbids then succeeds through the ORM and fails only
through raw SQL.
