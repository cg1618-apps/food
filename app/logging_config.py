"""Logging configured once, explicitly, at startup.

Media has no such file, and the consequence is worth not repeating: its root
log level is set by `logging.basicConfig` running as a side effect of importing
one router, so what gets logged depends on which module happened to be
imported, and `basicConfig` is a no-op once any handler exists. Under a
different entrypoint the level silently differs.

A dictConfig at startup is half an hour of work and is then never thought about
again.
"""

import logging
from logging.config import dictConfig

from app.config import settings


def configure() -> None:
    level = "DEBUG" if settings.is_development else "INFO"
    dictConfig(
        {
            "version": 1,
            # False, because uvicorn configures its own loggers before this
            # runs and disabling them would silence the access log and every
            # startup line with it.
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"handlers": ["console"], "level": level},
            "loggers": {
                # The app's own modules, at the chosen level.
                "app": {"level": level, "propagate": True},
                # SQLAlchemy's engine logger is WARNING even in development:
                # at INFO it prints every statement, which buries everything
                # else. Turn it up by hand when you are debugging a query.
                "sqlalchemy.engine": {"level": "WARNING", "propagate": True},
            },
        }
    )
    logging.getLogger(__name__).debug("logging configured at %s", level)
