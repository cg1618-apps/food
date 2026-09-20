"""The logging contract: what a line looks like, and who emits it.

The platform's `docs/logging.md` is the contract these assert. It is shared by
every app on the box, so a change here is a change to what the collector can
index - not a change to this app's taste.

Deliberately the same shape as media's `tests/unit/test_logging_config.py`. Two
apps asserting one contract differently is how the contract stops being one.
"""

import ast
import json
import logging
import pathlib

import pytest

from app import logging_config
from app.logging_config import APP_NAME, JsonFormatter, RequestIdFilter, TextFormatter
from app.request_context import reset_request_id, set_request_id

APP_DIR = pathlib.Path(__file__).resolve().parents[2] / "app"
LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical", "log"}


@pytest.fixture(autouse=True)
def restore_root_logging():
    """configure() is global. Put the suite's logging back afterwards.

    Without this, the first test here leaves every later test in the run
    emitting production JSON through a handler this module installed - which is
    harmless until the day it is not, and impossible to attribute when it
    happens.
    """
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    saved_uvicorn = {
        name: (
            logging.getLogger(name).handlers[:],
            logging.getLogger(name).propagate,
            logging.getLogger(name).level,
        )
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access")
    }
    yield
    root.handlers[:], root.level = saved
    for name, (handlers, propagate, level) in saved_uvicorn.items():
        restored = logging.getLogger(name)
        restored.handlers[:] = handlers
        restored.propagate = propagate
        restored.level = level


def make_record(message="hello", args=(), level=logging.INFO, exc_info=None):
    record = logging.LogRecord(
        name="app.something",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=args,
        exc_info=exc_info,
    )
    RequestIdFilter().filter(record)
    return record


@pytest.fixture
def request_id():
    """Enter a request, and leave it however the test ends."""
    token = set_request_id("abc123")
    yield "abc123"
    reset_request_id(token)


# ---------------------------------------------------------------------------
# The JSON line
# ---------------------------------------------------------------------------


def test_json_line_carries_every_contract_field():
    line = json.loads(JsonFormatter().format(make_record()))
    assert set(line) == {"timestamp", "level", "logger", "message", "app"}
    assert line["level"] == "INFO"
    assert line["logger"] == "app.something"
    assert line["message"] == "hello"
    assert line["app"] == APP_NAME == "food"
    # ISO 8601, UTC, milliseconds, explicit offset - the contract picks one
    # spelling so a reader of the aggregated stream never has to notice which
    # app chose which.
    assert line["timestamp"].endswith("+00:00")


def test_json_line_interpolates_lazy_arguments():
    """%s args, not an f-string: the formatter renders them."""
    line = json.loads(JsonFormatter().format(make_record("picked %s from %s", ("salt", "shelf"))))
    assert line["message"] == "picked salt from shelf"


def test_json_request_id_is_present_inside_a_request(request_id):
    line = json.loads(JsonFormatter().format(make_record()))
    assert line["request_id"] == request_id


def test_json_request_id_is_absent_outside_a_request():
    """Absent, not null.

    The mirror of the test above, and the one that matters: writing null would
    put an empty field on every startup, migration and background line, and
    would make "request_id is present" stop meaning "inside a request".
    """
    assert "request_id" not in json.loads(JsonFormatter().format(make_record()))


def test_json_line_carries_the_traceback():
    try:
        raise ValueError("no such ingredient")
    except ValueError:
        import sys

        record = make_record(level=logging.ERROR, exc_info=sys.exc_info())
    line = json.loads(JsonFormatter().format(record))
    assert "ValueError: no such ingredient" in line["exc_info"]


def test_json_line_survives_an_unserialisable_argument():
    """A log call is not the place to discover that an argument is exotic."""

    class Exotic:
        def __str__(self):
            return "<exotic>"

    line = json.loads(JsonFormatter().format(make_record("got %s", (Exotic(),))))
    assert line["message"] == "got <exotic>"


def test_json_line_is_one_line():
    """One object per line, whatever the message contains.

    A newline in a message would otherwise split one record into two, and the
    second half would not parse as JSON at all.
    """
    rendered = JsonFormatter().format(make_record("first\nsecond"))
    assert "\n" not in rendered
    assert json.loads(rendered)["message"] == "first\nsecond"


# ---------------------------------------------------------------------------
# The development line
# ---------------------------------------------------------------------------


def test_text_line_names_the_request(request_id):
    assert f"[request_id={request_id}]" in TextFormatter("%(message)s").format(make_record())


def test_text_line_says_nothing_outside_a_request():
    assert "request_id" not in TextFormatter("%(message)s").format(make_record())


# ---------------------------------------------------------------------------
# Which format, and who is taken over
# ---------------------------------------------------------------------------


def formatter_in_use():
    return type(logging.getLogger().handlers[0].formatter)


def test_production_gets_json(monkeypatch):
    monkeypatch.setattr(logging_config.settings, "app_env", "production")
    logging_config.configure()
    assert formatter_in_use() is JsonFormatter


def test_development_gets_text(monkeypatch):
    monkeypatch.setattr(logging_config.settings, "app_env", "development")
    logging_config.configure()
    assert formatter_in_use() is TextFormatter


def test_uvicorns_own_loggers_are_taken_over(monkeypatch):
    """The failure this exists for is a half-structured stream.

    uvicorn installs handlers on these three and sets propagate False, so a
    dictConfig that touches only root leaves every access line in plain text
    while the app's own lines turn JSON - invisible in `docker logs`, and the
    unparsed half is the highest-volume part of the stream.

    Asserted by IDENTITY against the root handler, not by "has some handler":
    uvicorn's own handler would satisfy the weaker check.
    """
    monkeypatch.setattr(logging_config.settings, "app_env", "production")
    logging_config.configure()

    console = logging.getLogger().handlers[0]
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        assert logger.handlers == [console], name
        # propagate True plus this handler emits every access line twice.
        assert logger.propagate is False, name


def test_sqlalchemy_statements_stay_quiet_in_development(monkeypatch):
    """At INFO the engine logger prints every statement and buries the rest."""
    monkeypatch.setattr(logging_config.settings, "app_env", "development")
    logging_config.configure()
    assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING


# ---------------------------------------------------------------------------
# %s arguments, never f-strings
# ---------------------------------------------------------------------------


def f_string_log_calls(tree: ast.AST) -> list[int]:
    """Line numbers of log calls whose message is an f-string.

    An f-string renders at the call site, so `record.msg` holds a finished
    sentence and `record.args` is empty: the template stops being a grouping
    key for the collector, and the arguments can never be promoted to fields
    later without rewriting every call site. See the platform's docs/logging.md.
    """
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr not in LOG_METHODS:
            continue
        if node.args and isinstance(node.args[0], ast.JoinedStr):
            found.append(node.lineno)
    return found


def test_no_log_call_formats_its_own_message():
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders += [f"{path.name}:{line}" for line in f_string_log_calls(tree)]
    assert offenders == [], offenders


def test_the_f_string_guard_can_actually_fail():
    """The mirror, and it is not decoration.

    `test_no_log_call_formats_its_own_message` walks a tree and asserts it
    found nothing. A detector that never matches anything passes it exactly as
    well as a working one - and would go on passing through the change that
    fills this app with f-string log calls. This proves the detector fires.
    """
    bad = ast.parse('logger.info(f"picked {name}")\n')
    good = ast.parse('logger.info("picked %s", name)\n')
    assert f_string_log_calls(bad) == [1]
    assert f_string_log_calls(good) == []
