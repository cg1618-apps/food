# Open items

Known defects and unmade decisions nobody is working on. Everything here is
open by definition; an item is closed by deleting it in the change that fixes
it.

## Uploaded images have no backup

`data/images` on the box is bind-mounted and is the only copy of every
uploaded photograph. Nothing copies it anywhere. A dish photograph cannot be
re-fetched, unlike a cover image an API supplies again. media solves the same
problem with its own rclone-to-R2 timer; whether food copies that or the
platform defines one file-backup contract for every app is a platform decision,
raised with the manager session.

## A failed commit after an upload leaves orphan files

`store_upload` writes the full image and its thumbnail to `data/images` before
it inserts the `image` row. If that commit fails, the files stay on disk with
no row naming them, and nothing sweeps them. The reverse order would leave a
row pointing at no file, which is worse; the fix is a sweep that removes files
under `library/` whose checksum has no row.

## Two identical uploads at once share one temporary file name

The temporary name is the final key plus `.part`, so two concurrent uploads of
the same picture write the same `.part` file. Both write identical bytes, so
the likely outcome is harmless, but one `os.replace` can find the file already
moved and fail the request. A unique temporary name per write closes it.

## The decompression-bomb check changes a process-wide warning filter

`_open` escalates Pillow's `DecompressionBombWarning` to an error inside
`warnings.catch_warnings()`, which mutates global state and is not
thread-safe. FastAPI runs the sync upload handler in a thread pool, so two
uploads at once can see each other's filter. An explicit `width * height`
check against the ceiling after opening would be deterministic and need no
filter at all.

## Labels cannot be reordered in 設定

A label has no `sort_order` column, so the API lists labels by name and the
設定 page draws their rows without the ▲ / ▼ the other vocabularies have.
Every other vocabulary is ordered by hand. If an order other than the
alphabet is wanted, the label table needs the column (a migration), its
`PATCH` the field, and `NameRow` the arrows it already draws elsewhere.

## The image library reads one detail per tile to show owners

`GET /api/images` carries only `attachment_count`, not who the image is
attached to, so `/edit/images` fetches `GET /api/images/{id}` for each tile
that has any attachment - up to 30 requests for a page. It is fine at a
kitchen's scale and slow over the tunnel on a phone. The list could return
the owners itself (one query joining the three gallery tables), and the page
would drop the per-tile reads.

## `updated_at` does not move when only child rows change

Editing only an ingredient's aliases, storage, heating, links, labels or
gallery leaves its `updated_at` where it was, because no column on
`ingredient` itself changed. Recipes have the same gap: a `PATCH` sending only
lists (aliases, lines, steps, sources, labels, methods, equipment, courses
served as) and the gallery `PUT` leave `recipe.updated_at` untouched. Kitchen
notes too: a `PATCH` sending only `label_ids`, and the gallery `PUT`, leave
`kitchen_note.updated_at` where it was. Anything that sorts or reports by "recently edited" will miss
those edits. The service would have to touch the timestamp whenever a list it
replaces was sent.
