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

## `ingredient.updated_at` does not move when only child rows change

Editing only aliases, storage, heating, links, labels or the gallery leaves
the ingredient's `updated_at` where it was, because no column on `ingredient`
itself changed. Anything that sorts or reports by "recently edited" will miss
those edits. The service would have to touch the timestamp whenever a list it
replaces was sent.

## An unknown id inside a request body is 404 in one place and 422 in another

A gallery `PUT` naming an image that does not exist answers 404; a heating row
naming a cooking method that does not exist answers 422. Both are "the body
refers to something that is not there", and one convention should cover both
before recipe lines add a third case. 422 reads more naturally - the URL
resolved, the payload was wrong - but changing the gallery route is a contract
change for its one caller.

## The detail page and category counts are stale after a save

After an ingredient is saved, its detail page and the category counts keep
showing the values from before the save until the page is reloaded. The
form's create and update mutations invalidate only the ingredient list, not
the detail query or the category tree.
