"""The application. One process serves the API and the built bundle."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import errors, logging_config
from app.request_context import RequestIdMiddleware
from app.routers import health, ingredient, ingredient_category, label

BASE_DIR = Path(__file__).resolve().parents[1]
DIST = BASE_DIR / "frontend_dist"


def create_app(dist: Path = DIST) -> FastAPI:
    """Build the application. `dist` is a parameter so tests can mount the
    catch-all against a directory they control - nothing has built
    frontend_dist/ when the suite runs, so a test that depends on it existing
    silently tests nothing.
    """
    logging_config.configure()

    app = FastAPI(title="food")
    # Added first, so it is the OUTERMOST middleware and the id is set before
    # anything below it can log - including the error handlers installed next,
    # which are the code most likely to be logging when this matters.
    app.add_middleware(RequestIdMiddleware)
    errors.install(app)

    app.include_router(health.router)
    # Read routers and their write counterparts are registered together, so
    # that adding a resource without its gate is visible here rather than
    # discovered by the prefix test.
    app.include_router(ingredient.router)
    app.include_router(ingredient.edit)
    app.include_router(ingredient_category.router)
    app.include_router(ingredient_category.edit)
    app.include_router(label.router)
    app.include_router(label.edit)

    if dist.is_dir():
        # Conditional: a bundle small enough for Vite to inline every asset
        # has no assets/ directory, and StaticFiles raises on a missing one
        # while the app is being built - so the process would fail to start
        # because of a frontend change, with nothing in the frontend to point
        # at.
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            """Every non-API path serves the bundle, so client routing works.

            Registered AFTER the API router, which is what stops it swallowing
            a REGISTERED route: had this route been added first, it would match
            /health before the health router ever got a turn.

            A `path` converter still matches any string, registered first or
            last, so ordering alone does not stop it claiming an UNREGISTERED
            /api/... path too - a mistyped endpoint would otherwise come back
            as a misleading 200 with the SPA's HTML instead of a 404. The
            explicit prefix check below is what actually prevents that.

            `/health` is checked as well as `/api`, because this app's health
            path is /health rather than /api/health (apps.yml) - so a typo in
            it is a path the catch-all would otherwise answer with the SPA,
            and a deploy probe reading a 200 from the wrong route is the one
            lie this file must not tell.
            """
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404)
            if full_path == "health" or full_path.startswith("health/"):
                raise HTTPException(status_code=404)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
