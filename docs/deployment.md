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

`apps.yml` declares `gated_paths: ["/api/edit"]`, and `bin/deploy` refuses when
that disagrees with this repository's `deploy/gated-paths` in either direction.
Both must name the same prefix, and `deploy/gated-paths` is read from the
commit — not the working tree.

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

## Health

`/health`, not `/api/health`. Declared in `apps.yml`, and the deploy pipeline
reads the declaration rather than the code.

It answers 200 only when the database is reachable, both revisions are readable,
and the two are equal. A 503 immediately after a deploy usually means the
migration did not run or the image rolled back while the schema did not — which
is the state nothing else on the box would notice, because the site still serves
pages and row counts still look right.
