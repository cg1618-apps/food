# Deployment, and what a rollback costs

**If you are reading this because `bin/rollback` froze and told you to, start at
"Rolling back".** That is what the freeze message points at.

## How a deploy runs

The platform's `bin/deploy food` does it, from `~/cg1618` on the box:

1. Dumps the `food` database to `~/backups/food/pre-deploy-<timestamp>.dump`,
   keeping the five most recent. Beside each dump it writes `.revision` (the git
   revision the code was at) and `.migration` (the revision the **database**
   reported, read from the database rather than from the revision files).
2. Brings the checkout to `origin/main`.
3. `compose up -d --build`. The container runs `alembic upgrade head` on start,
   so **the migration happens during the deploy, after the dump**.
4. Probes `/health`, which answers 200 only when the database is reachable *and*
   its Alembic revision matches the one the running code expects.

`apps.yml` declares `gated_paths: ["/api/edit", "/edit"]`, and `bin/deploy`
refuses when that disagrees with this repository's `deploy/gated-paths` in
either direction. Both must name the same prefixes, and `deploy/gated-paths` is
read from the commit — not the working tree.

**Adding a gated path is three steps in a fixed order**, because each later one
fails loudly without the one before: the Access application covers the path
first (dashboard work, and the only step that makes the gate real); then the
platform's `apps.yml` declares it, which `bin/check-exposure` verifies against
the live hostname; then this app's release ships it in `deploy/gated-paths`.
Between the last two landing on `main`, `bin/deploy` refuses a food deploy —
land the release rather than removing the declaration.

## Rolling back

**`bin/rollback` never restores data.** It reverses schema through
`deploy/migrations` and swaps the image back, then prints:

```
== SCHEMA was reversed. DATA was NOT restored. Verify your data. ==
```

That is not a limitation to work around. Reversing a migration is not a
restore — undoing a dropped table recreates it empty — so a downgrade that
removes a table removes what was in it.

### What that costs for this app, concretely

`i1ngredients` creates all six tables. Downgrading it **drops every ingredient,
category, alias, preservation note and label on production**, because those
tables are where the data lives. The migration's own downgrade docstring says
so.

**The pre-deploy dump is not a gentler path.** It is taken *before* the release,
so restoring it discards everything written since. `bin/rollback` refuses to do
that automatically for exactly this reason: it would throw away every write
since the dump in order to recover from a failure that usually did not touch
data at all. So it freezes at tier 3, names the dump, and stops.

**Rolling back across the later revisions loses data in further ways.**
`i2storage`'s downgrade is lossy by design: it deletes every preservation row
whose state is not `unused` and collapses each range to its maximum, or its
minimum when there is no maximum, and it drops `ingredient.rating`, every
heating row and every link outright. `m1images`'s downgrade drops the `image` and
gallery tables but leaves the files under `data/images` where they are, so the
pictures survive on disk and nothing in the database says which ingredient they
belonged to. `r1recipes`'s downgrade drops every recipe table and every recipe
in them; the pictures a recipe gallery attached stay in `image` and on disk.
`k1notes`'s downgrade drops `kitchen_note`, its label links and its gallery,
and every note with them; the pictures stay, as for recipes.

**`i3import`'s downgrade is a deliberate no-op.** It loaded the starting
ingredient list, and downgrading past it leaves every imported ingredient in
place: the owner may have filled them in since, and deleting them is worse
than keeping them. Re-running its upgrade inserts nothing that is already
there, so a downgrade and upgrade round trip is harmless.

`v2ocabulary`'s downgrade puts `recipe.status` and `recipe_source.platform`
back as strings, mapping each row to its old key by name, and drops
`recipe_status` and `source_platform`. A status or platform the owner created
or renamed has no old key and lands on `want_to_try` or `other`.

`a1uthors`'s downgrade puts `recipe_source.creator` back as each source's
author's display name and drops `author`. A creator that was a later spelling
of a name (babish after Babish) comes back as the first spelling.

**So there is no route that keeps the data.** The real choice is:

- **roll back**, and lose everything entered since the release, or
- **fix forward** — deploy a corrected build and keep it.

For a kitchen database entered by hand, "fix forward" is usually right and
"roll back" is usually only right when the app cannot serve at all. Decide on
that basis, not on which command is easier to run.

### Where the dumps are

```
~/backups/food/pre-deploy-<timestamp>.dump
~/backups/food/pre-deploy-<timestamp>.dump.revision    # git revision of the code
~/backups/food/pre-deploy-<timestamp>.dump.migration   # revision the DB reported
```

Five are kept. The newest is the one the failing deploy took. The freeze message
prints the same paths, so what it names and what is listed here should agree; if
they ever do not, believe the box.

## What the database is at

| | |
| --- | --- |
| Before the first feature release | `0001_baseline` — one table, `alembic_version` |
| After it | `i1ngredients` — six tables |
| Vocabularies and their seeds | `v1ocabulary` |
| Storage ranges, heating, links, rating | `i2storage` |
| The image library | `m1images` — thirteen tables |
| Recipes | `r1recipes` — twenty-three tables |
| Kitchen notes | `k1notes` — twenty-six tables |
| The starting ingredient list | `i3import` — no new table |
| Statuses and source platforms as vocabularies | `v2ocabulary` — twenty-eight tables |
| Authors as a vocabulary | `a1uthors` — twenty-nine tables, the current head |

`0001_baseline` is deliberately empty; it exists so the chain could be proven to
build from nothing before there was a table to build. **So the rollback target
of the first feature release is an empty schema**, which is the sharpest version
of the section above.

Check what the database actually reports rather than trusting a revision in a
freeze message:

```bash
docker exec <postgres container> psql -U <user> -d food \
  -tAc "SELECT version_num FROM alembic_version"
```

`deploy/migrations current` answers the same question the way the platform asks
it, and answers `base` when there is no `alembic_version` table at all. That arm
is for an app's very first deploy — travel's first deploy died there — and
**food will not exercise it**, because food's database is already stamped. A
reader assuming the first migration deploy tests every path would be wrong.

## Uploaded images

Uploads are written to `IMAGE_DIR`, which defaults to `data/images` and is
`/app/data/images` in the container. `docker-compose.prod.yml` bind-mounts
`./data/images` from the checkout on the box over it, so the pictures live
outside the image and survive a rebuild. A bind mount rather than a named
volume, so a backup job would see ordinary files.

**Nothing needs creating on the box first.** The application creates the
directory when it starts (`create_app` makes it, parents included, if it is
missing), and Docker creates the host side of a bind mount if it does not
exist. The first upload then makes `library/` and `library/thumbs/` beneath it.
`tests/unit/test_prod_compose.py` asserts the mount is declared.

**It is not backed up.** `bin/deploy` dumps the database and nothing else, so
`data/images` on the box is the only copy of every uploaded photograph, and a
restored database dump refers to files a restore does not bring back. See
`docs/open-items.md`.

## Health

`/health`, not `/api/health`. Declared in `apps.yml`, and the deploy pipeline
reads the declaration rather than the code.

It answers 200 only when the database is reachable, both revisions are readable,
and the two are equal. A 503 immediately after a deploy usually means the
migration did not run or the image rolled back while the schema did not — which
is the state nothing else on the box would notice, because the site still serves
pages and row counts still look right.
