# food

A kitchen database: an ingredient library, dishes and sauces and their
recipes, the weekly cooking schedule, and notes on what to cook and how.

One of the applications on the [cg1618 platform](https://github.com/cg1618-apps/platform).
It is registered in that repository's `apps.yml`, which assigns it
`food.cg1618.com`, port 8001 and the database `food`. Reads are public; every
write sits under `/edit` and `/api/edit`, behind Cloudflare Access.

## What is built

- **Ingredients** - names and aliases, a category tree with notes per
  category, varieties, storage and heating guides, labels, galleries, the
  待補 stub backlog, and merge.
- **Dishes and sauces** (料理 / 醬料) and their **recipes** - lines with
  alternatives, grouped steps, sources and authors, methods, equipment,
  notes and galleries, and "used in" in both directions.
- **Authors** - a library of the people recipes come from.
- **Kitchen notes** - bookmarks with a body, labels and a gallery.
- **The weekly schedule** (排程) - four meals, fruit and the buy and thaw
  marks, per day.
- **加熱** and **TBD** - standalone pages of heating notes and loose links.
- **搜尋** - one search box across every library.
- **設定** and **未來固定設定** - the vocabularies and system options the
  libraries draw on, and 圖片, the image library.

The modules still to build, in order, are in
[`docs/to-do-next.md`](docs/to-do-next.md).

| Layer | Choice |
| --- | --- |
| Backend | FastAPI · SQLAlchemy 2 · PostgreSQL · Alembic · Python 3.13 |
| Frontend | React · Vite, built into `frontend_dist/` for uvicorn to serve |

## Running it

`.\dev.ps1` starts the platform's shared development PostgreSQL, uvicorn on
:8001 and Vite on :5174. The test, lint and build commands, and the rules
about ports and rebuilding, are in [`CLAUDE.md`](CLAUDE.md), "Commands"; the
platform's `docs/setup-local.md` sets up a development machine.

`main` is production and moves only by a release pull request from `dev`.

## Documentation

Everything is under [`docs/`](docs/README.md): the data model, every API
route and the error shape, the frontend pages, testing, logging and
deployment, and in `docs/notes/decisions/` why things are the way they are.
