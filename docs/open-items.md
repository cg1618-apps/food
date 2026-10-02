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
