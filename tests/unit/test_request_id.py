"""The request id: where it comes from, and what is refused.

food is `exposure: public` and cloudflared forwards client headers unmodified,
so on this hostname `X-Request-ID` arrives from the open internet. The
rejections below are the point of this file; the acceptance is here so that a
validator which refused *everything* cannot pass them all.
"""

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.request_context import (
    REQUEST_ID_HEADER,
    RequestIdMiddleware,
    current_request_id,
)

HEX32 = re.compile(r"\A[0-9a-f]{32}\Z")


@pytest.fixture
def client():
    """A minimal app, so these assert the middleware and not food's routes."""
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/echo")
    def echo():
        return {"seen": current_request_id()}

    return TestClient(app)


def test_an_id_is_generated_when_none_arrives(client):
    response = client.get("/echo")
    generated = response.json()["seen"]
    assert HEX32.match(generated), generated
    # Echoed back, so a reader who saw the failure in the browser can search
    # for it.
    assert response.headers[REQUEST_ID_HEADER] == generated


def test_a_sane_inbound_id_is_honoured(client):
    response = client.get("/echo", headers={REQUEST_ID_HEADER: "trace-abc_123"})
    assert response.json()["seen"] == "trace-abc_123"
    assert response.headers[REQUEST_ID_HEADER] == "trace-abc_123"


def test_an_id_of_exactly_sixty_four_characters_is_honoured(client):
    """The mirror case, and the reason the rejections below mean anything.

    Every rejection test asserts "a fresh id was generated". A validator that
    rejected *everything* would pass all of them. This is the boundary that
    proves it accepts, and it is on the limit rather than safely inside it.
    """
    limit = "a" * 64
    assert client.get("/echo", headers={REQUEST_ID_HEADER: limit}).json()["seen"] == limit


# ids= is not cosmetic here. pytest builds a test id from the parameter VALUE
# and exports it in PYTEST_CURRENT_TEST, and Windows refuses an environment
# variable longer than 32767 characters - so the megabyte case takes the whole
# run down in teardown with a ValueError out of os.environ that names this file
# only in passing. Naming the ids keeps the oversized value out of the id.
@pytest.mark.parametrize(
    ("label", "value"),
    [
        ("one over the limit", "a" * 65),
        ("a megabyte of it", "a" * 1024 * 1024),
        ("punctuation", "abc$%^def"),
        ("a space", "abc def"),
        ("a newline", "abc\ndef"),
        ("empty", ""),
    ],
    ids=[
        "one-over-the-limit",
        "a-megabyte-of-it",
        "punctuation",
        "a-space",
        "a-newline",
        "empty",
    ],
)
def test_an_unacceptable_inbound_id_is_replaced(client, label, value):
    """Replaced, not sanitised, and never echoed back.

    The two things being prevented: an unbounded value riding on every line of
    the request and straight into the collector's storage, and a client reusing
    another request's id so that correlation lies while still reading as
    coherent.
    """
    response = client.get("/echo", headers={REQUEST_ID_HEADER: value})
    used = response.json()["seen"]
    assert HEX32.match(used), label
    assert used != value, label
    # The response carries the id that was USED, not the one that arrived.
    assert response.headers[REQUEST_ID_HEADER] == used, label


def test_the_id_does_not_leak_between_requests(client):
    first = client.get("/echo", headers={REQUEST_ID_HEADER: "first-one"}).json()["seen"]
    second = client.get("/echo").json()["seen"]
    assert first == "first-one"
    assert second != "first-one"


def test_there_is_no_id_outside_a_request(client):
    client.get("/echo")
    assert current_request_id() is None
