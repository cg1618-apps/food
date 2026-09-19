# Decisions

Why food is the way it is. Unlike the rest of `docs/`, this page is allowed to
talk about the past: it records what was chosen, what was rejected, and the
reasoning that is still load-bearing.

## Platform decisions this app inherits

Recorded in `cg1618-apps/platform` rather than here, and summarised only so far
as they bind this app:

- **It is its own repository**, sharing no code with the other applications. The
  platform connects them by configuration, not by git pointers.
- **It shares one PostgreSQL**, with its own database and its own role.
- **It is `public`**, because repository rulesets and environments with required
  reviewers are free only for public repositories, and both gates depend on it.
- **No `pull_request`-triggered job may run on the self-hosted runner.**

## Decisions for this application

- **FastAPI, PostgreSQL, React + Vite, Alembic** — the media tracker's stack.
  Rejected: Django, which would have suited a library-of-entities app well and
  cost far less code per app, but adds a second framework to hold in mind and a
  different deploy shape. Rejected: a server-rendered frontend with htmx, which
  would have removed the build step, the second dev port and the stale-bundle
  failure mode entirely — worth revisiting if the frontend turns out to be
  thin, and the reason it was not chosen is consistency with an app that
  already works rather than a technical defect.
- **Public to read, with writes behind Cloudflare Access on their own path
  prefix.** No accounts and no login: one user, and the reading half is meant to
  be openable on a phone without signing in. The write surface needs a gate
  regardless, and doing it at the edge means no password is stored and no auth
  code is written. This requires the URL layout to separate reads from writes
  from the first route, which is cheap now and invasive later.
