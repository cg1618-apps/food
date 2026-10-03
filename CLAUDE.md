# CLAUDE.md — food

**The generic rules are not in this file.** Git workflow, branch and pull
request discipline, concurrent sessions, the machine-wide test lock, the
credentials rule, worktrees and documentation discipline live in
`cg1618-apps/platform`'s `CLAUDE.md`, one directory up. Claude Code loads it
first and this file second, so everything there applies here unless this says
otherwise.

## What this application is

**food** is a kitchen database. What it is meant to hold, in the owner's
words:

- an **ingredient library** — what an ingredient is, how to pick a good one,
  how to preserve it;
- **dishes** (料理) and **sauces** (醬料) — a dish in general, or a sauce or
  base used inside other dishes rather than eaten on its own — and their
  **recipes**, each one specific way of making the dish;
- a library of **what can be cooked**, with notes;
- the **cooking schedule**;
- **what is in the kitchen right now**, with notes on each thing;
- a **dessert library** — cookies, candies, sweets — carrying health
  information;
- a **random picker**, for when nothing suggests itself;
- a **restaurant library**;
- **TBD** — a page of loose notes, a name and links each, related to nothing
  else in the app.

Two shapes run through that list and are worth naming early: most of it is a
**catalogue of entities with notes**, and a little of it — the schedule, what
is in the kitchen — is **state that changes daily**. They pull in different
directions, and the second is the one that makes this app more than a
reference work.

## Status

**Modules 1 and 2 are built, with dishes, recipe templates, kitchen notes and
TBD.** The schema is at revision `t2emplates` (the head).

- **Ingredients** - names and aliases, a category tree, varieties under a
  parent, rating, labels, storage as a state x method grid with day ranges, a
  heating guide, links, galleries, the 待補 (`needs_detail`) stub backlog,
  and merge.
- **Dishes** - a dish (料理) or a sauce (醬料) in general: names and aliases,
  kind, course, region, labels, serves-as, a description and a gallery; its
  recipes, and "used in" - the recipes whose lines name it. A dish with
  recipes, or one a line names, cannot be deleted.
- **Recipes** - each one way of making a dish, with an optional name of its
  own and 其他版本 (the dish's other recipes); lines naming an ingredient, a
  dish, or a new stub or dish made by the save, and steps (each a 步驟, 可省略
  or 備註), each in groups (a 設定 材料分組 / 步驟分組 value or a one-off name,
  rows dragged within and between them), sources with an author picked or
  made by the save, a status, methods, equipment, galleries, "used in" for
  ingredients, and 常用 chips above the lines that add one in a tap. A new
  recipe starts blank, from a template, or as a copy of another recipe.
- **Recipe templates** - a named skeleton (servings, time, lines and steps in
  their groups, methods, equipment) stored as one JSONB body, made on its own
  form or from a recipe (存成範本), ordered on 設定; a reference to something
  since deleted is dropped when it is read, and counted.
- **Kitchen notes** - bookmarks with a title, a kind, a link, a body, labels
  and a gallery.
- **TBD** - a standalone page of entries, each an optional name and any
  number of links, in the owner's order; read at `/tbd`, edited in place at
  `/edit/tbd`.
- **The notebook UI** - 料理 · 食譜 · 食材 · 筆記 · TBD · 設定: the four libraries
  (search and filters in the URL, a sidebar or a phone drawer, covers or a
  table), their detail pages, their add and edit forms with the gallery
  picker, one delete dialog, ingredient merge, 設定 for every vocabulary
  (categories, labels, courses, regions, recipe statuses, source platforms, authors,
  材料分組, 步驟分組, cooking methods, equipment), for 常用食材 (the
  recipe form's chips, an ordered pick of ingredients) and for 範本 (the
  recipe templates), and 圖片, the image library.

**The starting ingredient list is loaded by `i3import`**: 194 names from the
recipe document's ingredient lists, approved by the owner, read from
`alembic/import/ingredients.csv` and inserted as 待補 stubs, skipping any name
already in the library.

`docs/frontend.md` describes the pages, `docs/data-model.md` the schema,
`docs/api.md` the routes and the error shape, `docs/testing.md` how the suite
is arranged and which tests are load-bearing, and `docs/notes/decisions.md`
why.

## The contract this app owes the platform

Four things, none of which names a framework:

1. **A container listening on port 8001**, publishing nothing to the host.
2. **A health path** that answers 200 only when the app can actually serve —
   not a route that returns 200 with the database down. It is declared in the
   platform's `apps.yml` as `/health`; change it there if this app exposes
   something else.
3. **`DATABASE_URL` read from the environment.**
4. **A `main` branch that is production**, moving only by pull request.

The platform's `docs/registry.md` and `docs/shared-stack.md` hold the detail,
including the network alias (`food-app`) the tunnel routes to.

## Stack

**FastAPI + PostgreSQL on the backend, React + Vite on the frontend** — the
same shape as the media tracker, deliberately. Four months of patterns exist to
copy from, and the platform's app contract is enforced by `apps.yml` and the
deploy pipeline rather than by every app being different.

The cost is known and accepted: a build step, a second port in development, and
a `frontend_dist/` that goes stale if you forget to rebuild. The media
tracker's `CLAUDE.md` documents each of those.

Migrations: Alembic. `deploy/migrations` — the hook the platform's rollback
calls — implements `current`, `added` and `downgrade`. Its `current` arm
answers `base` when the database has no `alembic_version` table, which is what
lets this app's first deploy through; it must stay executable (`100755` in the
commit, which `git ls-tree HEAD` is the only way to check) and LF-terminated.

## Who can see it

**Public to read. No accounts, no login, one user's data — yours.**

Anyone may read the ingredient library, the recipes and the rest. That is the
point: it is a reference you can open on a phone in a shop without signing in.

**Writes are a different question, and the answer is not "nothing".** A public
hostname with unprotected write endpoints is a public editor. So the write
surface lives under its own path prefix and Cloudflare Access protects that
prefix — the same mechanism `travel` and `art` use for their whole hostname,
applied to one part of this one. No auth code in the app, and no password to
store.

What that requires of the URL layout, from the first route:

- **`/api/...` and the pages that read** — public, no gate.
- **`/edit/...` and `/api/edit/...`** (or whatever prefix is chosen, chosen
  once) — everything that creates, updates or deletes, behind Access.

Splitting reads from writes by path is cheap now and invasive later, which is
why it is written down before there is a single route.

## Commands

```powershell
.\dev.ps1                                 # Postgres + uvicorn :8001 + Vite :5174
```

```bash
venv/Scripts/python.exe -m pytest -q      # backend tests
venv/Scripts/ruff.exe check .             # backend lint
cd frontend && npm run lint               # oxlint
cd frontend && npm test                   # vitest, colocated with the source
cd frontend && npm run build              # writes frontend_dist/ for uvicorn
```

**Take the machine-wide pytest lock around every backend run** — all four apps
share one PostgreSQL. The lock is in the platform's `CLAUDE.md`.

**Ports are box-wide.** uvicorn is 8001 (food's `apps.yml` entry) and Vite is
5174 (`5173 + (port - 8000)`). Both are `strictPort`/abort-on-taken, because
falling back to another port takes a slot another app on this laptop owns.

**After any frontend change run `npm run build`**, or :8001 serves the old
bundle while :5174 serves the new one, and the difference reads as a bug in
whichever one you looked at second.

**The health path is `/health`, not `/api/health`.** It is declared in
`apps.yml` and the deploy pipeline reads it from there.
