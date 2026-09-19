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
- **recipes**, and **general recipes** — a sauce or a base that is used inside
  other dishes rather than eaten on its own;
- a library of **what can be cooked**, with notes;
- the **cooking schedule**;
- **what is in the kitchen right now**, with notes on each thing;
- a **dessert library** — cookies, candies, sweets — carrying health
  information;
- a **random picker**, for when nothing suggests itself;
- a **restaurant library**.

Two shapes run through that list and are worth naming early: most of it is a
**catalogue of entities with notes**, and a little of it — the schedule, what
is in the kitchen — is **state that changes daily**. They pull in different
directions, and the second is the one that makes this app more than a
reference work.

## Status

**The skeleton is built; there is no schema.** FastAPI serves `/health` and
the React bundle, Alembic's chain holds one empty baseline revision, and
`deploy/migrations` is in place. Nothing food-shaped exists yet: no tables, no
endpoints beyond the health route, no pages.

The next step is module 1 of the eight in `docs/notes/decisions.md` — design
it into `docs/superpowers/specs/` immediately before building it, not now.

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
cd frontend && npm run build              # writes frontend_dist/ for uvicorn
```

**Ports are box-wide.** uvicorn is 8001 (food's `apps.yml` entry) and Vite is
5174 (`5173 + (port - 8000)`). Both are `strictPort`/abort-on-taken, because
falling back to another port takes a slot another app on this laptop owns.

**After any frontend change run `npm run build`**, or :8001 serves the old
bundle while :5174 serves the new one, and the difference reads as a bug in
whichever one you looked at second.

**The health path is `/health`, not `/api/health`.** It is declared in
`apps.yml` and the deploy pipeline reads it from there.
