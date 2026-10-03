"""`GET /api/edit/session` - the probe the edit pages use to reach the Access login.

The route itself checks nothing: Access answers before the app does. What it
owes is a 204 when the request got through, and - after a sign-in - a redirect
back to the edit page the browser came from, and to nowhere else.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.routing import WRITE_PREFIX

SESSION = f"{WRITE_PREFIX}/session"


def client():
    return TestClient(app, follow_redirects=False)


def test_it_sits_under_the_gated_prefix():
    """The whole point. Outside the prefix it answers 204 to everyone and
    never sends anybody to the login."""
    assert SESSION.startswith(f"{WRITE_PREFIX}/")


def test_a_bare_probe_answers_204():
    response = client().get(SESSION)
    assert response.status_code == 204
    assert response.content == b""


def test_it_sends_the_browser_back_to_the_edit_page():
    response = client().get(SESSION, params={"next": "/edit/recipes/3?tab=steps"})
    assert response.status_code == 303
    assert response.headers["location"] == "/edit/recipes/3?tab=steps"


def test_the_edit_root_is_a_destination_too():
    response = client().get(SESSION, params={"next": "/edit"})
    assert response.status_code == 303
    assert response.headers["location"] == "/edit"


def test_it_refuses_to_redirect_anywhere_but_an_edit_page():
    """An open redirect on a signed-in path is a phishing link with this
    hostname on it. The mirror of the test above, so a green here proves the
    check refused rather than that the route never redirects."""
    for target in [
        "https://example.com/edit/settings",
        "//example.com/edit/settings",
        "/\\example.com",
        "/recipes",
        "/editor",
        "/edit/settings\r\nSet-Cookie: x=1",
    ]:
        response = client().get(SESSION, params={"next": target})
        assert response.status_code == 400, target
        assert "location" not in response.headers, target
