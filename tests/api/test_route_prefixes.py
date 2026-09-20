"""No mutation may live outside the gated prefix.

This app has no authentication code. The gate on writes is Cloudflare Access,
which is all-or-nothing per path, so "every write sits under /api/edit" is not
a tidiness rule - it is the entire security boundary. A POST added under
/api/ingredients would be publicly writable the moment it deployed, and nothing
in the platform repository would notice: `bin/check-exposure` probes the
hostname root and asserts a public app answers ungated, which stays true while
an unprotected write endpoint sits below it.

So this check has to live here, where it fails on the pull request that
scatters a write rather than after the deploy that exposes it.
"""

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.main import create_app
from app.routing import WRITE_PREFIX

READ_METHODS = {"GET", "HEAD", "OPTIONS"}


def mutating_routes_outside_the_prefix(app: FastAPI) -> list[str]:
    """Every non-read route that does not sit under the write prefix.

    Shared by the assertion below and by its mirror, so that the two cannot
    drift into checking different things - which would leave the mirror
    passing while the real check was broken.
    """
    escaped = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = set(route.methods or set()) - READ_METHODS
        if not methods:
            continue
        if not route.path.startswith(WRITE_PREFIX):
            escaped.append(f"{sorted(methods)} {route.path}")
    return escaped


def test_every_write_route_sits_under_the_write_prefix():
    assert mutating_routes_outside_the_prefix(create_app()) == []


def test_the_app_actually_has_write_routes_to_check():
    """Without this, the assertion above is vacuous.

    An empty route table has no mutations to scatter, so the real check passes
    on a fresh application and would keep passing through the change that
    breaks it. This is the fixture that makes the negative bite: it asserts
    there is something to be wrong about.
    """
    app = create_app()
    mutations = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and set(route.methods or set()) - READ_METHODS
    ]
    assert len(mutations) >= 5, [r.path for r in mutations]


def test_a_write_route_outside_the_prefix_is_caught():
    """The mirror: the check must FAIL on a deliberately misplaced route.

    A green from the real assertion says either "nothing escaped" or "the
    check does not work". Only this test distinguishes them. It is
    load-bearing and it looks like decoration - do not delete it because it
    tests a route that does not exist in the app.
    """
    app = create_app()

    @app.post("/api/ingredients/oops")
    def misplaced():  # pragma: no cover - never called, only registered
        return None

    escaped = mutating_routes_outside_the_prefix(app)
    assert escaped == ["['POST'] /api/ingredients/oops"], escaped


def test_read_routes_are_allowed_outside_the_prefix():
    """The other mirror. A check that refused every route outside the prefix
    would pass the test above and break the entire public read surface, which
    is the point of the app."""
    app = create_app()
    public_reads = [
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        and set(route.methods or set()) <= READ_METHODS
        and route.path.startswith("/api/")
        and not route.path.startswith(WRITE_PREFIX)
    ]
    assert "/api/ingredients" in public_reads
    assert mutating_routes_outside_the_prefix(app) == []
