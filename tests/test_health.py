"""The health probe must fail in the three ways that matter."""

from fastapi.testclient import TestClient

from app.main import app
from app.routers import health


def test_it_reports_ok_when_the_schema_matches_the_code(monkeypatch):
    monkeypatch.setattr(health, "read_alembic_revision", lambda db: "abc123")
    monkeypatch.setattr(health, "expected_revision", lambda: "abc123")
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_it_reports_503_when_the_database_cannot_be_read(monkeypatch):
    def boom(db):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(health, "read_alembic_revision", boom)
    response = TestClient(app).get("/health")
    assert response.status_code == 503


def test_it_reports_503_when_the_schema_and_the_code_disagree(monkeypatch):
    # The state a half-rolled-back deploy leaves behind: the database holds the
    # new revision, the image has rolled back to code that never heard of it.
    # Pages still serve. Only this comparison notices.
    monkeypatch.setattr(health, "read_alembic_revision", lambda db: "new456")
    monkeypatch.setattr(health, "expected_revision", lambda: "old123")
    assert TestClient(app).get("/health").status_code == 503


def test_two_unreadable_sides_are_not_a_match(monkeypatch):
    # None == None would be a MATCH, and an app that can read neither side
    # would report healthy. The media tracker checks this explicitly for that
    # reason; so does this.
    monkeypatch.setattr(health, "read_alembic_revision", lambda db: None)
    monkeypatch.setattr(health, "expected_revision", lambda: None)
    assert TestClient(app).get("/health").status_code == 503


def test_an_unreadable_revision_directory_is_503_not_500(monkeypatch):
    # The other half of the same fix: expected_revision() is inside the try,
    # so a broken revision directory answers the way every other "cannot
    # serve" state does instead of escaping as an unhandled 500.
    monkeypatch.setattr(health, "read_alembic_revision", lambda db: "abc123")

    def boom():
        raise RuntimeError("Path doesn't exist")

    monkeypatch.setattr(health, "expected_revision", boom)
    assert TestClient(app).get("/health").status_code == 503


def test_expected_revision_reads_the_real_alembic_ini():
    # Every test above monkeypatches expected_revision() itself, so the real
    # code path - reading alembic.ini through ScriptDirectory - is otherwise
    # exercised by nothing. lru_cache means a stale cached value from before
    # alembic.ini existed would poison this; clear it first so the assertion
    # proves the real read, not a leftover.
    health.expected_revision.cache_clear()
    assert health.expected_revision() == "0001_baseline"


def test_expected_revision_does_not_depend_on_the_working_directory(
    monkeypatch, tmp_path
):
    # alembic.ini's `script_location = alembic` resolves against the cwd, so
    # an absolute path to the ini does not make this portable on its own:
    # from any other directory it raised `Path doesn't exist`. The call now
    # sits inside the handler's try as well, so even a future version of this
    # failure is a 503 rather than an unhandled 500.
    monkeypatch.chdir(tmp_path)
    health.expected_revision.cache_clear()
    assert health.expected_revision() == "0001_baseline"
