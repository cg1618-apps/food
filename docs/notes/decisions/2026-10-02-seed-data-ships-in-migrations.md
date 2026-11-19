# Seed data and the starting ingredient list ship in migrations

**The starting vocabularies (`v1ocabulary`) and the starting ingredient list
(`i3import`) are loaded by migrations**, not by a script or the API. A
production database receives them on deploy with nobody on the box, a
development database gets them from `alembic upgrade head`, and Alembic's
version table is what records that they have run. Rejected: a separate seed
script, which two machines and a box would each have to remember to run.

- **The vocabulary seeds use `ON CONFLICT DO NOTHING`**, so they land on a
  database where the owner already typed 肉類 or 飯 and keep the owner's row
  as it is.
- **The ingredient CSV lives at `alembic/import/ingredients.csv`, not under
  `data/`.** `.dockerignore` excludes `data/`, so a file there would never
  reach the image the migration runs in on the box: the upgrade would pass
  locally and fail on deploy. Beside the migrations, it ships with them.
- **The file is validated in full before anything is written.** Half a list,
  with the remainder failing on the box, is worse than none.
- **A row whose name is already taken is skipped, not merged.** The existing
  row is the owner's and may hold more than a stub would, so it is never
  modified, and a second run inserts nothing.
- **Its downgrade is a no-op.** The rows are ordinary data once landed;
  telling an untouched stub from an edited row would need a marker column
  every ingredient carries forever, for a downgrade nobody expects to run.
- **No ORM.** The migration writes SQL through the bind and copies the seeded
  category names rather than importing them: a revision must not depend on
  today's models or on another revision's module.

`docs/data-model.md`, "The starting ingredient list", has the file format and
the load's rules.
