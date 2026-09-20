"""The catch-all must not shadow the API.

Nothing has run `npm run build` when this suite runs - CI builds the frontend
in a later step - so `frontend_dist/` need not exist and the module-level
`app` then never mounts the catch-all at all: a test built against that
`app` would pass by finding nothing to test. These tests build
a fresh app via `create_app()` against a `tmp_path` directory that always
has an `index.html` and an `assets/` directory, so the catch-all is mounted
in every environment, built frontend or not.
"""

from fastapi.testclient import TestClient

from app.main import create_app


def _app_with_dist(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html><body>spa</body></html>")
    return create_app(dist=tmp_path)


def test_an_unknown_api_path_is_404_not_the_spa(tmp_path):
    # If the catch-all is mounted before the API routes, every mistyped
    # endpoint returns the index page with a 200, and a broken frontend call
    # looks like a rendering bug rather than a missing route.
    response = TestClient(_app_with_dist(tmp_path)).get("/api/does-not-exist")
    assert response.status_code == 404


def test_a_mistyped_health_path_is_404_not_the_spa(tmp_path):
    # This app's health path is /health, not /api/health, so the `api` prefix
    # check does not cover it. A typo under it would otherwise answer 200 with
    # the SPA's HTML - and a deploy probe pointed at the typo would call a
    # dead app healthy, which is the failure the health route exists to stop.
    response = TestClient(_app_with_dist(tmp_path)).get("/health/nope")
    assert response.status_code == 404


def test_a_registered_api_route_still_reaches_its_own_handler(tmp_path):
    # Proves the catch-all does not shadow a route that DOES exist - the
    # other half of "router before catch-all". Whatever the health route
    # itself returns (200 or 503 depending on the database), it must not be
    # the SPA's HTML.
    response = TestClient(_app_with_dist(tmp_path)).get("/health")
    assert not response.headers["content-type"].startswith("text/html")


def test_a_non_api_path_serves_the_spa_index(tmp_path):
    # Proves the catch-all is genuinely mounted and serving the bundle - the
    # other assertions would pass vacuously if it were not.
    response = TestClient(_app_with_dist(tmp_path)).get("/recipes/42")
    assert response.status_code == 200
    assert "spa" in response.text


def test_a_bundle_with_no_assets_directory_still_starts(tmp_path):
    # Vite inlines every asset when the bundle is small enough, and the build
    # then has no assets/ at all. StaticFiles raises on a missing directory
    # as the app is built, so an unguarded mount would turn that frontend
    # change into a process that will not start.
    (tmp_path / "index.html").write_text("<html><body>spa</body></html>")
    response = TestClient(create_app(dist=tmp_path)).get("/recipes/42")
    assert response.status_code == 200
    assert "spa" in response.text


def test_a_real_file_in_the_bundle_is_served_as_itself(tmp_path):
    # The catch-all used to answer EVERY non-API path with index.html, so a
    # file that genuinely sits in the bundle - favicon.svg is the one that
    # exposed this - came back as the SPA's HTML under text/html and the
    # browser discarded it. Nothing sits in front of this app in production
    # (cloudflared connects straight to uvicorn) and only /assets is mounted
    # as StaticFiles, so this handler is the only thing that can serve it.
    (tmp_path / "favicon.svg").write_text("<svg>the-real-icon</svg>")
    response = TestClient(_app_with_dist(tmp_path)).get("/favicon.svg")
    assert response.status_code == 200
    assert "the-real-icon" in response.text
    assert "spa" not in response.text


def test_a_traversal_path_cannot_escape_the_bundle(tmp_path):
    # The mirror of the test above, and the reason serving real files is not
    # simply "return whatever the path names". `full_path` is user-controlled,
    # so without the resolve-and-confine guard `/..%2F.env` reads any file
    # beside the bundle - here the app's own credentials.
    #
    # The .env file written below is LOAD-BEARING, not scenery: `is_file()`
    # is False for a path that does not exist, so without a real secret to
    # leak this test would pass on an unguarded handler and prove nothing.
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "assets").mkdir()
    (dist / "index.html").write_text("<html><body>spa</body></html>")
    secret = tmp_path / ".env"
    secret.write_text("DATABASE_URL=postgresql://never-serve-this")

    client = TestClient(create_app(dist=dist))
    for path in ("/..%2F.env", "/../.env", "/%2e%2e%2f.env"):
        response = client.get(path)
        assert "never-serve-this" not in response.text, path
        # Falling back to the SPA is the intended answer: the guard rejects
        # the candidate and the request becomes an ordinary client route.
        assert response.status_code in (200, 404), path
