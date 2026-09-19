"""The engine, the session factory, and the dependency that hands one out."""

from collections.abc import Iterator
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

TAIPEI = ZoneInfo("Asia/Taipei")


def get_taipei_now() -> datetime:
    """Local wall clock, naive, for the timestamp columns.

    Naive and Taipei rather than aware and UTC because every reader of these
    columns is one person in one place, and a stored UTC value shows the wrong
    date for anything done after 8am - "when did I add this" is the only
    question they answer.

    `zoneinfo` reads the operating system's tz database, which Windows does not
    have; `tzdata` is in requirements.txt for that reason and is not optional
    on the development machines.
    """
    return datetime.now(TAIPEI).replace(tzinfo=None)

engine = create_engine(settings.sqlalchemy_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Every model inherits this; Alembic's autogenerate reads its metadata."""


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
