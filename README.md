# food

Ingredients, recipes, what is cookable, and the cooking schedule.

One of the applications on the [cg1618 platform](https://github.com/cg1618-apps/platform).
It is registered in that repository's `apps.yml`, which assigns it
`food.cg1618.com`, port 8001 and the database `food`.

**The skeleton is built; there is no schema yet.** FastAPI serves a health
route and the React bundle, Alembic's chain holds one empty baseline, and the
deploy hook the platform's rollback calls is in place. The eight modules and
the entities they own are described in `docs/notes/decisions.md`.

## Running it

```powershell
.\dev.ps1            # shared Postgres + uvicorn on :8001 + Vite on :5174
```

```bash
venv/Scripts/python.exe -m pytest -q      # tests
venv/Scripts/ruff.exe check .             # backend lint
cd frontend && npm run lint && npm run build
```

`main` is production and moves only by a release pull request from `dev`.
