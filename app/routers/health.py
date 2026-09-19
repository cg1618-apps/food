"""Liveness that touches the database, for the deploy ladder and the container.

Three conditions are checked - the database is reachable, both revisions are
readable, and the two are equal - and the last is the one nothing else on the
box would notice. After a failed migration-bearing deploy the database holds the
new revision while the image has rolled back to code that has never heard of
it. The site still serves pages. Row counts still look right. Only a
comparison between what the schema SAYS it is and what the code EXPECTS
catches that.

The path is public - there is no such thing as an internal path behind the
platform's ingress - and says only whether the app is serving.

The revision is read from `alembic_version.version_num` and from nowhere
else: not from an image's revision files, not from `alembic heads` against
the database. Two authoritative answers that can disagree mid-deploy is worse
than one.
"""

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(prefix="/health", tags=["Health"])

# app/routers/health.py -> app/ -> the repository root, where alembic.ini lives.
# Derived from this file rather than imported from app.main, which imports this
# module to register the router.
BASE_DIR = Path(__file__).resolve().parents[2]


def read_alembic_revision(db: Session) -> str | None:
    """The revision the DATABASE believes it is at, or None if unstamped."""
    row = db.execute(text("SELECT version_num FROM alembic_version")).first()
    return row[0] if row else None


@lru_cache(maxsize=1)
def expected_revision() -> str | None:
    """The head the RUNNING CODE expects, from the revision files it ships.

    Cached because the container's filesystem is immutable for its lifetime and
    the compose healthcheck calls this every 30 seconds; `ScriptDirectory` walks
    every revision file on each construction, which would otherwise make the
    health probe the most expensive request this app serves.

    Returns None when the chain has more than one head, which is a broken
    repository rather than a state to serve traffic in - the caller treats it as
    unhealthy.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BASE_DIR / "alembic.ini"))
    # alembic.ini's `script_location = alembic` is relative to the CURRENT
    # WORKING DIRECTORY, not to the ini file, so pointing Config at an
    # absolute ini path is not enough on its own: called from anywhere but
    # the repository root it raises `Path doesn't exist`. Overriding the
    # option is what actually makes this cwd-independent.
    cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))

    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    return heads[0] if len(heads) == 1 else None


@router.get("")
def health(response: Response, db: Session = Depends(get_db)):
    try:
        actual = read_alembic_revision(db)
        expected = expected_revision()
    except Exception:
        # Deliberately broad, and it covers both reads. Anything that stops
        # them - the database down, the table absent, a connection pool
        # exhausted, an unreadable revision directory - means the app cannot
        # serve, and a health probe that raised would be a 500 the container's
        # healthcheck reads the same way anyway. Reporting 503 keeps the
        # meaning explicit, and keeps every "cannot serve" state answering
        # with the same status.
        response.status_code = 503
        return {"status": "unavailable"}

    # `actual is None` is checked explicitly rather than relying on the
    # comparison: if expected_revision() also returned None, None == None would
    # be a MATCH and an app that could read neither side would report healthy.
    if actual is None or expected is None or actual != expected:
        response.status_code = 503
        return {"status": "unavailable"}

    return {"status": "ok"}
